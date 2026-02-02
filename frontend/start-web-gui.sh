#!/bin/bash

echo "Starting Evolving AI Web GUI..."
echo "================================"
echo ""

# Check if backend is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✓ Backend already running on port 8000"
else
    echo "Starting backend on port 8000..."
    python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload &
    BACKEND_PID=$!
    echo "✓ Backend started (PID: $BACKEND_PID)"
fi

echo ""
echo "Starting frontend on port 3000..."
cd frontend && npm run dev

