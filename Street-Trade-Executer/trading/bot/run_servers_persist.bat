@echo off
echo Starting Jane Street Trading System Servers...

:: Start API Server
cd /d "%~dp0Street-Trade-Executer"
start "API Server" cmd /c "run-api.bat"

:: Start Dashboard
start "Dashboard UI" cmd /c "run-dashboard.bat"

:: Start Python Bot
cd /d "%~dp0"
start "Python Bot" cmd /c "python main.py"

echo ====================================================
echo All services started and kept alive in background!
echo Open http://localhost:24210/ in your browser.
echo ====================================================

:loop
ping -n 60 127.0.0.1 > nul
goto loop

