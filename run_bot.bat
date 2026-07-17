@echo off
title Jane Street Trading Bot - Autostart Loop
color 0a

:loop
echo ===================================================
echo   STARTING JANE STREET TRADING BOT ENGINE...
echo ===================================================
python -u main.py
echo ===================================================
echo   BOT STOPPED OR CRASHED!
echo   Restarting automatically in 5 seconds...
echo ===================================================
timeout /t 5
goto loop
