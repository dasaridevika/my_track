#!/bin/bash
set -e
# Start FastAPI backend in background on port 8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
# Give FastAPI backend 2 seconds to boot
sleep 2
# Start Streamlit frontend on Railway's assigned $PORT
exec streamlit run frontend/app.py --server.port ${PORT:-8501} --server.address 0.0.0.0
