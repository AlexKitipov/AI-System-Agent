@echo off
REM run_all.bat
REM Starts the AI System Agent Gateway on 127.0.0.1:8765.

cd /d "%~dp0"

echo ============================================
echo  AI System Agent Gateway
echo  Listening on http://127.0.0.1:8765
echo  Logs: logs\agent.log
echo ============================================

REM Use the Python launcher (py) because python.exe is not in PATH
py -m uvicorn gateway.server:app --host 127.0.0.1 --port 8765

pause
