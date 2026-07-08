@echo off
echo Starting Jane Street Trading System...

:: Start API Server
cd /d "D:\google antigravity\jane_street_trading_system\trading\bot\Street-Trade-Executer"
start "API Server" run-api.bat

:: Start Dashboard
start "Dashboard UI" run-dashboard.bat

:: Start Python Bot
cd /d "D:\google antigravity\jane_street_trading_system\trading\bot"
start "Python Bot" python main.py

echo.
echo ====================================================
echo All services started in separate windows!
echo Open http://localhost:24210/ in your browser.
echo ====================================================
echo.
pause
