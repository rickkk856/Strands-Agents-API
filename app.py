from collections.abc import Callable
from typing import Iterator, Dict, Optional, Any
from uuid import uuid4
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
import uvicorn
from strands import Agent, tool
from strands_tools import http_request
import os
from fastapi.responses import HTMLResponse


#%% --- Environment Variables
import os
from dotenv import load_dotenv

load_dotenv(".env")
GEMINI_API = os.getenv("GEMINI_API_KEY")
#OPENROUTER_API = os.getenv("OPENROUTER_API_KEY") Not Being Used


#%% --- Session Manager
# Register messages that have been previously added
# Enables the model to remember about previous messages but increase context window
from strands.session.file_session_manager import FileSessionManager
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent

def create_session_manager(user_id, session_id):
    session_dir = BASE_PATH / "sessions" / user_id
    session_manager = FileSessionManager(
        session_id=f"{session_id}",
        storage_dir=session_dir
    )
    return session_manager

#%% --- Conversation Manager
# Create a conversation manager with custom window size
# Enables the model to remember about previous messages but increase context window
from strands.agent.conversation_manager import SlidingWindowConversationManager

sliding_window_conversation_manager = SlidingWindowConversationManager(
    window_size=20,  # Maximum number of messages to keep
    should_truncate_results=True, # Enable truncating the tool result when a message is too large for the model's context window 
)


#%% --- System Prompt
# Instructions given to the model to set the behavior of the agent
# You can modify this prompt to change the agent's behavior
CARBON_SYSTEM_PROMPT = """You are an AI Agent specialized in carbon footprint analysis of architectural projects.

Your main task is to analyze the contents of a given URL (which may include text, images, PDFs, BIM models, or other documents) describing an architectural project and then:

Extract relevant information such as:

Project type (residential, commercial, industrial, etc.)
Location (country, climate zone, urban/rural setting)
Building size (floor area, height, number of floors)
Construction materials and quantities (concrete, steel, wood, glass, insulation, finishes, etc.)
Energy systems (HVAC, lighting, renewable sources, fossil-fuel use)
Water and waste management systems
Transportation or mobility considerations (e.g., parking, bike storage, public transit proximity)

Estimate carbon footprint for each stage of the building lifecycle:

Embodied carbon (extraction, manufacturing, transport, and construction of materials)
Operational carbon (heating, cooling, electricity, water use, lighting, appliances over the building’s lifespan)
End-of-life carbon (demolition, disposal, recycling potential)

Provide outputs in a structured format, including:

Total estimated carbon footprint (in kgCO₂e or tCO₂e)
Breakdown by lifecycle stage (embodied, operational, end-of-life)
Key drivers of emissions (e.g., high cement use, inefficient HVAC, lack of renewable energy)
Suggested alternatives or mitigation strategies (e.g., use of low-carbon concrete, more insulation, renewable energy integration, timber instead of steel, passive design strategies).

Communicate clearly, using:

Numerical estimates with clear units (kgCO₂e/m², total tCO₂e)
Tables or bullet points where appropriate
A short plain-language summary for non-experts

Constraints:

If the URL lacks sufficient data, state assumptions clearly and explain uncertainties.
Follow recognized frameworks such as IPCC guidelines, LEED, BREEAM, or RICS Whole Life Carbon Assessment whenever possible.
Be transparent about data sources, assumptions, and calculation methods.

Your goal is to provide a reliable, structured, and actionable carbon footprint analysis to help architects, engineers, and stakeholders make informed decisions about sustainability.
"""

class PromptRequest(BaseModel):
    prompt: str
    user_id: str
    session_id: str

#%% --- Models
# For custom model configuration check following links:
# Strands Docs: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/litellm/
# LiteLLM Docs: https://docs.litellm.ai/docs/
# Gemini  Docs: https://docs.litellm.ai/docs/providers/gemini 
from strands.models.litellm import LiteLLMModel
model = LiteLLMModel(
    client_args={
        "api_key": os.getenv("GEMINI_API_KEY"),
    },
    # **model_config
    #model_id="anthropic/claude-3-7-sonnet-20250219", 
    #model_id="google/gemini-2.5-pro", # Error 500
    model_id="gemini/gemini-2.0-flash",
    params={
        "max_tokens": 1000,
        "temperature": 0.7,
    }
)


#%% --- API Endpoints
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Carbon Footprint API")

# --- ADD CORS MIDDLEWARE HERE ---
origins = [
    "*",
    "http://localhost",
    "http://localhost:8000",  # Your local FastAPI default port
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    # The browser sends Origin: null for file:// requests.
    "null",
    # Add any other specific origins your frontend might run on, e.g.,
    # "http://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

#%% --- Serve index.html
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse 

app.mount("/static", StaticFiles(directory="."), name="static") 

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

#%% --- Agent Enpoints (Non-Streaming and Streaming)
@app.get('/health')
def health_check():
    """Health check endpoint for the load balancer."""
    return {"status": "healthy"}

@app.post('/carbon')
async def get_carbon(request: PromptRequest):
    """Endpoint to get carbon footprint information."""
    prompt = request.prompt
    
    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")

    try:
        carbon_agent = Agent(
            model=model,
            system_prompt=CARBON_SYSTEM_PROMPT,
            state={"user_id": request.user_id, "session_id": request.session_id},
            tools=[http_request],
            session_manager=create_session_manager(request.user_id, request.session_id),
            conversation_manager=sliding_window_conversation_manager
        )
        response = carbon_agent(prompt)
        content = str(response)
        return PlainTextResponse(content=content)
    except Exception as e:
        return PlainTextResponse(content=f"Error: {str(e)}", status_code=500)


async def run_carbon_agent_and_stream_response(prompt: str, request: Any):
    """
    A helper function to yield summary text chunks one by one as they come in, allowing the web server to emit
    them to caller live
    """
    is_summarizing = False

    @tool
    def ready_to_summarize():
        """
        A tool that is intended to be called by the agent right before summarize the response.
        """
        nonlocal is_summarizing
        is_summarizing = True
        return "Ok - continue providing the summary!"

    try:
        carbon_agent = Agent(
            model=model,
            system_prompt=CARBON_SYSTEM_PROMPT,
            state={"user_id": request.user_id, "session_id": request.session_id},
            tools=[http_request, ready_to_summarize],
            session_manager=create_session_manager(request.user_id, request.session_id),
            conversation_manager=sliding_window_conversation_manager,
            callback_handler=None
        )

        async for event in carbon_agent.stream_async(prompt):
            if "current_tool_use" in event and event["current_tool_use"].get("name"):
                tool_name = event["current_tool_use"]["name"]
                if tool_name == "ready_to_summarize":
                    is_summarizing = True
                    yield "\n" # Skip a to split reasoning & summary
                else:
                    yield (f"\n\n🔧 Using tool: {tool_name}") 

            # Only yield data when summarizing - Can be problematic if model doesn't call the tool
            #if not is_summarizing:
            #    continue

            elif "data" in event:
                yield event['data']

    except Exception as e:
        yield f"Error: {str(e)}"


@app.post('/carbon-streaming')
async def get_carbon_streaming(request: PromptRequest):
    """Endpoint to stream the carbon footprint summary as it comes it, not all at once at the end."""
    try:
        prompt = request.prompt

        if not prompt:
            raise HTTPException(status_code=400, detail="No prompt provided")

        return StreamingResponse(
            run_carbon_agent_and_stream_response(prompt, request),
            media_type="text/plain"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    # Get port from environment variable or default to 8000
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)