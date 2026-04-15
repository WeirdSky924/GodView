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

echo Waiting for backend to be ready...
set MAX_WAIT=6
set WAIT_COUNT=0

:check_backend
timeout /t 2 /nobreak >nul
set /a WAIT_COUNT+=2
powershell -Command "try { Invoke-WebRequest -Uri 'http://localhost:8000/docs' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo Backend is ready!
    goto start_frontend
)
if %WAIT_COUNT% geq %MAX_WAIT% (
    echo Warning: Backend health check timeout, starting frontend anyway...
    goto start_frontend
)
echo   Waiting... (%WAIT_COUNT%/%MAX_WAIT% seconds)
goto check_backend

:start_frontend
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
