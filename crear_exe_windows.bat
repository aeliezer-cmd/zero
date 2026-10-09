@echo off
setlocal enabledelayedexpansion
title Compilador de Zero para Windows (.EXE)
cd /d "%~dp0"

echo =======================================================
echo          COMPILADOR DE ZERO PARA WINDOWS (.EXE)
echo =======================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    set PYCMD=py
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set PYCMD=python
    ) else (
        echo [ERROR] No se encontro Python en este sistema.
        echo Por favor instala Python 3 desde https://www.python.org/downloads/
        echo Asegurate de marcar la casilla "Add Python to PATH" durante la instalacion.
        echo.
        pause
        exit /b 1
    )
)

echo [*] Verificando e instalando PyInstaller...
%PYCMD% -m pip install --upgrade pip >nul 2>&1
%PYCMD% -m pip install --upgrade pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al instalar PyInstaller.
    pause
    exit /b 1
)

echo.
echo Seleccione el tipo de ejecutable a compilar:
echo   [1] Unico archivo EXE portable (Recomendado - Zero.exe unico)
echo   [2] Carpeta con dependencias (Inicio instantaneo)
set /p TIPO="Opcion (1 o 2, por defecto 1): "
if "%TIPO%"=="" set TIPO=1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [*] Compilando Zero para Windows...

if "%TIPO%"=="2" (
    %PYCMD% -m PyInstaller --noconfirm --clean --onedir --name Zero --add-data "static;static" app.py
    if %errorlevel% neq 0 (echo [ERROR] Fallo la compilacion.&pause&exit /b 1)
    if not exist "dist\Zero\data" mkdir "dist\Zero\data"
    if not exist "dist\Zero\respaldos" mkdir "dist\Zero\respaldos"
    if exist "data\zero.sqlite3" copy /y "data\zero.sqlite3" "dist\Zero\data\zero.sqlite3" >nul
    echo.
    echo =======================================================
    echo  COMPILACION EXITOSA (Modo Carpeta)
    echo  Ubicacion: dist\Zero\Zero.exe
    echo =======================================================
) else (
    %PYCMD% -m PyInstaller --noconfirm --clean --onefile --name Zero --add-data "static;static" app.py
    if %errorlevel% neq 0 (echo [ERROR] Fallo la compilacion.&pause&exit /b 1)
    if not exist "dist\data" mkdir "dist\data"
    if not exist "dist\respaldos" mkdir "dist\respaldos"
    if exist "data\zero.sqlite3" copy /y "data\zero.sqlite3" "dist\data\zero.sqlite3" >nul
    copy /y Iniciar.bat dist\ >nul 2>&1
    copy /y Iniciar-intranet.bat dist\ >nul 2>&1
    copy /y Respaldar.bat dist\ >nul 2>&1
    echo.
    echo =======================================================
    echo  COMPILACION EXITOSA (Modo Portable)
    echo  Ubicacion: dist\Zero.exe
    echo =======================================================
)

echo.
echo Al ejecutar Zero.exe, el servidor arrancara y abrira
echo automaticamente tu navegador en http://127.0.0.1:8000
echo.
pause
