#!/bin/bash
set -e

export PYTHONPATH="$(pwd)/backend:$(pwd):$PYTHONPATH"

# Start FastAPI backend in background on port 8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# Give FastAPI backend a moment to boot
sleep 3

# Start Streamlit frontend on Railway's assigned $PORT with headless flags
exec streamlit run frontend/app.py \
  --server.port ${PORT:-8501} \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
