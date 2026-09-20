#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo "================================================================="
echo "   BHOOMI INTELLIGENCE - LAND RECORD MODERNIZATION PLATFORM"
echo "================================================================="

# Start Backend
echo "🚀 Starting FastAPI Backend on http://localhost:8000..."
cd "$DIR/backend"
PYTHONPATH=. "$DIR/backend/venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start Frontend
echo "🚀 Starting Vite Frontend on http://localhost:5173..."
cd "$DIR/frontend"
npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT

echo ""
echo "✅ Systems Online:"
echo "   - Frontend UI:  http://localhost:5173"
echo "   - Backend API:  http://localhost:8000"
echo "   - Swagger Docs: http://localhost:8000/docs"
echo "================================================================="
wait
