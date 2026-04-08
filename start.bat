@echo off
chcp 65001 >nul
echo Starting GodView...
echo.
echo Starting databases...
cd /d E:\_Workspace\Godview
docker compose up -d
timeout /t 8 /nobreak >nul
echo.
echo Starting backend...
start "GodView Backend" cmd /k "E:\_Workspace\Godview\venv\Scripts\python.exe -m uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo Starting frontend...
cd /d E:\_Workspace\Godview\frontend
start "GodView Frontend" cmd /k "npm run dev"
echo.
echo ========================================
echo   GodView 已启动!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ========================================
echo   数据库: PostgreSQL:5432 Qdrant:6333 NebulaGraph:9669
echo ========================================
pause
