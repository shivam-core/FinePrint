# FinePrint

FinePrint: Explainable Detection and Auditing of Potentially Unfair Terms-of-Service Clauses.

## Running Locally

1. Create a virtual environment and install dependencies:
   ```
   uv venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Start the server:
   ```
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## Render Deployment

This app is configured to be deployed on Render as a Python Web Service.
Deployment is pending user testing.
