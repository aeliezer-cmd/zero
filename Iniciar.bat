@echo off
cd /d "%~dp0"
start "Zero" http://127.0.0.1:8000/
python app.py
pause
