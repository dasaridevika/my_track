#!/bin/bash
set -e

APP_PORT="${PORT:-8501}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

if [ "$BACKEND_PORT" = "$APP_PORT" ]; then
  BACKEND_PORT=8001
fi

export PYTHONPATH="$(pwd)/backend:$(pwd):$PYTHONPATH"
export API_URL="${API_URL:-http://127.0.0.1:${BACKEND_PORT}/crawl}"
export PLAYWRIGHT_BROWSERS_PATH="/app/.bin/ms-playwright"
playwright install

python -m uvicorn backend.main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

sleep 3
echo "Starting Streamlit on port $APP_PORT"
echo "Backend API URL=$API_URL"

exec streamlit run frontend/app.py \
  --server.port "$APP_PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
