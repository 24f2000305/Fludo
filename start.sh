#!/bin/sh
# Railway startup script - properly handles PORT environment variable

# Use PORT environment variable or default to 8080
PORT="${PORT:-8080}"

echo "Starting uvicorn on port $PORT..."
exec uvicorn app.server:app --host 0.0.0.0 --port "$PORT"
