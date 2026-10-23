@echo off
cd /d "%~dp0"
if not exist pyproject.toml (
  echo ERROR: este archivo debe estar dentro de la carpeta medguia-win, junto a pyproject.toml.
  pause
  exit /b 1
)

rem Busca Python 3.12 o 3.13 con el lanzador "py". Las versiones mas nuevas (3.14, 3.15) suelen no tener
rem todavia paquetes compilados de PyMuPDF, PySide6 o sqlite-vec.
set PYEXE=
py -3.12 --version >nul 2>&1 && set PYEXE=py -3.12
if "%PYEXE%"=="" py -3.13 --version >nul 2>&1 && set PYEXE=py -3.13
if "%PYEXE%"=="" (
  echo ERROR: no encuentro Python 3.12 ni 3.13.
  echo Instala Python 3.12 desde https://www.python.org/downloads/ ^(puedes dejar instalada tu version actual^).
  echo En el instalador deja marcada la opcion "py launcher". Despues vuelve a ejecutar este archivo.
  echo.
  echo Versiones de Python que veo en este equipo:
  py -0p
  pause
  exit /b 1
)
echo Usando %PYEXE%

if exist .venv rmdir /s /q .venv
%PYEXE% -m venv .venv
if errorlevel 1 (
  echo ERROR: no se pudo crear el entorno virtual.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[ui,dev]"
if errorlevel 1 (
  echo ERROR: fallo la instalacion. Copia el texto de arriba y enviaselo a Claude.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pytest -q
echo.
echo Instalacion terminada. Haz doble clic en INICIAR.bat
pause
