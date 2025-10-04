# app.py (or any name you prefer for a single Flask file)

from collections.abc import Callable
from typing import Iterator, Dict, Optional, Any, List
from uuid import uuid4
import os
from pathlib import Path
import asyncio

# Flask specific imports
from flask import Flask, request, jsonify, Response, render_template, abort, send_from_directory
from flask_cors import CORS

# Pydantic for request body validation (still useful even in Flask for schema definition)
from pydantic import BaseModel, ValidationError

# Strands imports
from strands import Agent, tool
from strands_tools import http_request
from strands.session.file_session_manager import FileSessionManager
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models.litellm import LiteLLMModel

# --- 0. Base Directory Setup & Environment Variables ---
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# --- 1. Configuration & Constants ---

# Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
PORT = int(os.getenv("PORT", 8000))

# Paths
SESSIONS_BASE_PATH: Path = BASE_DIR / "sessions"
# For Flask's static_folder, usually a 'static' subfolder is used.
# If index.html is in BASE_DIR directly, adjust Flask app setup or serve it directly.
STATIC_FILES_DIR: Path = BASE_DIR # Assuming index.html is in BASE_DIR, adjust if in a 'static' folder
INDEX_HTML_PATH: Path = BASE_DIR / "index.html"

# Agent Configuration
SLIDING_WINDOW_SIZE: int = 20

# CORS Origins
CORS_ORIGINS: List[str] = [
    "*", # For broad access during development, tighten in production
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "null",  # For file:// requests (browser's origin for local files)
    "https://rickkk856.pythonanywhere.com", # Example production domain
    # Add any other specific origins your frontend might run on
]

# System Prompt
CARBON_SYSTEM_PROMPT: str = """You are an AI Agent specialized in carbon footprint analysis of architectural projects.

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

# Pydantic Model for incoming request data
class PromptRequest(BaseModel):
    prompt: str
    user_id: str
    session_id: str

# --- 2. Strands Session & Conversation Managers ---

def create_session_manager(user_id: str, session_id: str) -> FileSessionManager:
    """
    Creates and returns a FileSessionManager instance for a given user and session.
    Sessions are stored in SESSIONS_BASE_PATH/{user_id}/{session_id}.
    """
    session_dir = SESSIONS_BASE_PATH / user_id
    session_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists
    session_manager = FileSessionManager(
        session_id=session_id,
        storage_dir=session_dir
    )
    return session_manager

sliding_window_conversation_manager = SlidingWindowConversationManager(
    window_size=SLIDING_WINDOW_SIZE,
    should_truncate_results=True,
)

# --- 3. Strands LLM Model ---
# This is initialized once globally
llm_model = LiteLLMModel(
    client_args={
        "api_key": GEMINI_API_KEY,
    },
    model_id="gemini/gemini-2.0-flash",
    params={
        "max_tokens": 1000,
        "temperature": 0.7,
    }
)

# --- 4. Strands Agent Tools ---
@tool
def ready_to_summarize_signal_tool():
    """
    A tool called by the agent to signal that it's about to start summarizing its response.
    """
    return "Agent is now ready to provide the summary."

# --- 5. Agent Factory Function ---
def create_carbon_agent(
    user_id: str,
    session_id: str,
    is_streaming_mode: bool = False
) -> Agent:
    """
    Factory function to create and configure an Agent instance for carbon footprint analysis.
    """
    agent_tools: List[Any] = [http_request]

    if is_streaming_mode:
        agent_tools.append(ready_to_summarize_signal_tool)

    return Agent(
        model=llm_model,
        system_prompt=CARBON_SYSTEM_PROMPT,
        state={"user_id": user_id, "session_id": session_id},
        tools=agent_tools,
        session_manager=create_session_manager(user_id, session_id),
        conversation_manager=sliding_window_conversation_manager,
        callback_handler=None
    )

# --- 6. Flask Application Setup ---
app = Flask(__name__, static_folder=str(STATIC_FILES_DIR), static_url_path='/static')
CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

# --- 7. Flask Endpoints ---

@app.route('/')
def read_root():
    """
    Serves the index.html file from the base directory.
    """
    if not INDEX_HTML_PATH.exists():
        abort(404, description=f"'{INDEX_HTML_PATH.name}' not found at {INDEX_HTML_PATH.parent}")
    
    # Flask provides send_file for serving files directly, which is generally better.
    return send_from_directory(INDEX_HTML_PATH.parent, INDEX_HTML_PATH.name)

@app.route('/health')
def health_check():
    """Health check endpoint for the load balancer."""
    return jsonify({"status": "healthy"})

@app.route('/carbon', methods=['POST'])
def get_carbon():
    """
    Endpoint to get carbon footprint information from the AI agent without streaming.
    The full response is returned once the agent has completed its processing.
    """
    try:
        request_data = PromptRequest(**request.get_json())
    except ValidationError as e:
        return jsonify({"detail": e.errors()}), 400
    except Exception:
        return jsonify({"detail": "Invalid JSON request body."}), 400

    if not request_data.prompt:
        return jsonify({"detail": "No prompt provided in the request."}), 400

    try:
        carbon_agent = create_carbon_agent(
            user_id=request_data.user_id,
            session_id=request_data.session_id,
            is_streaming_mode=False
        )
        #agent_result = asyncio.run(carbon_agent(request_data.prompt))
        agent_result = carbon_agent(request_data.prompt)

        # --- CRUCIAL CHANGE HERE: Extract the text content ---
        # AgentResult.message is a dict, message['content'] is a list of dicts.
        # We assume the first item in content has the 'text' key.
        response_text = ""
        if agent_result and agent_result.message and agent_result.message.get('content'):
            for item in agent_result.message['content']:
                if 'text' in item:
                    response_text += item['text']
                    # If you only expect one text block, you can break here:
                    # break
        else:
            # Fallback if content structure is unexpected
            response_text = str(agent_result) # or an appropriate error message
        # --- END CRUCIAL CHANGE ---

        return Response(response_text, mimetype="text/plain")
    except Exception as e:
        app.logger.exception("Error in /carbon endpoint") # Use Flask's logger for better debugging
        return jsonify({"detail": f"An error occurred: {str(e)}"}), 500

@app.route('/carbon-streaming', methods=['POST'])
def get_carbon_streaming():
    """
    Endpoint to 'stream' the carbon footprint summary.
    Due to WSGI's synchronous nature and Strands's async streaming, this collects
    all data first using asyncio.run() and then yields it in chunks.
    It does NOT provide real-time streaming from the LLM.
    """
    try:
        request_data = PromptRequest(**request.get_json())
    except ValidationError as e:
        return jsonify({"detail": e.errors()}), 400
    except Exception:
        return jsonify({"detail": "Invalid JSON request body."}), 400

    if not request_data.prompt:
        return jsonify({"detail": "No prompt provided in the request."}), 400

    def generate_streaming_response():
        """
        Helper generator function for the streaming endpoint.
        It runs the async agent stream and yields collected chunks.
        """
        carbon_agent = create_carbon_agent(
            user_id=request_data.user_id,
            session_id=request_data.session_id,
            is_streaming_mode=True
        )

        all_events = []
        async def collect_events():
            async for event in carbon_agent.stream_async(request_data.prompt):
                all_events.append(event)
        
        try:
            asyncio.run(collect_events())
        except Exception as e:
            # Yield error message if the agent stream fails
            yield f"\n\nError during streaming agent processing: {str(e)}"
            return

        is_summarizing = False
        for event in all_events:
            if "current_tool_use" in event and event["current_tool_use"].get("name"):
                tool_name = event["current_tool_use"]["name"]
                if tool_name == ready_to_summarize_signal_tool.__name__:
                    is_summarizing = True
                    yield "\n\n--- Agent is generating summary ---\n\n"
                else:
                    yield (f"\n\n🔧 Using tool: {tool_name}")
            elif "data" in event:
                # --- CRUCIAL CHANGE HERE: 'data' event already contains the text ---
                # 'data' events from agent.stream_async() are designed to yield
                # the raw text chunks directly from the LLM. So, we just yield it.
                yield event['data']
            # You can handle other event types here if needed, e.g., "observation"

    return Response(generate_streaming_response(), mimetype="text/plain")

# --- 8. Run Flask Application (for local development) ---
if __name__ == '__main__':
    # Ensure sessions directory exists on startup
    SESSIONS_BASE_PATH.mkdir(parents=True, exist_ok=True)
    app.run(host='0.0.0.0', port=PORT, debug=True) # debug=True for development