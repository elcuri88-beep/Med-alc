@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\instalar.ps1
echo.
echo Instalacion terminada. Ahora abre scripts\iniciar.bat
pause
