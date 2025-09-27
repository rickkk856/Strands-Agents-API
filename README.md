# Setup
1 - Create .venv `python -m venv .venv`

2 - Activate .venv `.venv\Scripts\Activate`

3 - Install requirements `pip install -r requirements.txt`

4 - run `python app.py`

5 - Open `localhost:8000/docs` to see the API Documentation 

Example:

```
curl -X 'POST' \
  'http://localhost:8000/weather' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "prompt": "What is the weather in Miami Today?"
}'
```

## Useful Sources
https://github.com/davidshtian/Learning-Strands-Agents/tree/hand
