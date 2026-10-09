@echo off
cd /d "%~dp0"
if not exist respaldos mkdir respaldos
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set FECHA=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set HORA=%%a%%b
python app.py --backup "respaldos\zero-%FECHA%-%HORA%.sqlite3"
pause
