#!/bin/bash
set -e

# Set PYTHONPATH to include backend folder
export PYTHONPATH="$(pwd)/backend:$(pwd):$PYTHONPATH"

# Start FastAPI backend in background from backend directory
(cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000) &

# Give FastAPI backend a moment to boot
sleep 2

# Start Streamlit frontend on Railway's assigned $PORT
exec streamlit run frontend/app.py --server.port ${PORT:-8501} --server.address 0.0.0.0
