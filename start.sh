#!/bin/bash
echo "Starting GodView..."
echo ""
echo "Starting databases..."
cd E:\_Workspace\Godview
docker compose up -d
sleep 8
echo ""
echo "Starting backend..."
 \
    python -m uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo ""
echo "Starting frontend..."
cd E:\_Workspace\Godview/frontend && npm run dev &
FRONTEND_PID=$!
echo ""
echo "========================================"
echo "  GodView 已启动!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "========================================"
echo "  数据库: PostgreSQL:5432 Qdrant:6333 NebulaGraph:9669"
echo "========================================"
echo "Press Ctrl+C to stop"
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker compose down" EXIT
wait
