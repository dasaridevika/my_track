#!/bin/bash
uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port 8000 &
streamlit run frontend/app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 &
nginx -c $(pwd)/nginx.conf -g "daemon off;"
