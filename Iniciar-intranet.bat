@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python iniciar_red.py) else (py -3 iniciar_red.py)
pause
