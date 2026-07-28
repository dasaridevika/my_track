#!/bin/bash
set -e

export PYTHONPATH="$(pwd)/backend:$(pwd):$PYTHONPATH"

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

sleep 3
echo "Railway PORT=$PORT"

exec streamlit run frontend/app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
