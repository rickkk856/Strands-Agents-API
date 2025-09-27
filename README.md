# Setup / Usage

1 - Create Virtual Environment `python -m venv .venv`

2 - Activate Virtual Environment `.venv\Scripts\Activate`

3 - Install requirements `pip install -r requirements.txt`

4 - Create a `.env` file with the proper api keys, example at `.env_example` [Generate Gemini API Keys Here](https://aistudio.google.com/app/api-keys)

5 - run `python app.py`

6 - open `localhost:8000` and interact with the agent to get streaming responses

7 - Open `localhost:8000/docs` to see the API Documentation 


## Query Examples

```
curl -X 'POST' \
  'http://localhost:8000/carbon' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "prompt": "Analyze the carbon footprint of this project: https://www.archdaily.com.br/br/776950/casa-vila-matilde-terra-e-tuma-arquitetos"
  "user_id": "demo-user"
  "session_id": "chat-session"
}'

curl -X 'POST' \
  'http://localhost:8000/carbon-streaming' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "prompt": "Analyze the carbon footprint of this project: https://www.archdaily.com.br/br/776950/casa-vila-matilde-terra-e-tuma-arquitetos"
  "user_id": "demo-user"
  "session_id": "chat-session"
}'
```

## Session Manager

Files get stored at the following path:
```
./sessions/
  └── user_id/
      └── session_<session_id>/
          ├── session.json                # Session metadata
          └── agents/
              └── agent_<agent_id>/
                  ├── agent.json          # Agent metadata and state
                  └── messages/
                      ├── message_<message_id>.json
                      └── message_<message_id>.json
```
There are other alternatives for session management, please check: [Session Management Documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/session-management/#session-management)


## Project Roadmap

See the [TODO list](./TODO.md) for pending tasks and ideas


## Useful Sources
https://github.com/davidshtian/Learning-Strands-Agents/tree/hand
