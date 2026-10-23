@echo off
cd /d "%~dp0"
if not exist pyproject.toml (
  echo ERROR: este archivo debe estar dentro de la carpeta medguia-win, junto a pyproject.toml.
  pause
  exit /b 1
)
python --version
if errorlevel 1 (
  echo ERROR: Python no esta instalado o no esta en el PATH. Instala Python 3.12 o superior desde python.org
  echo y marca "Add Python to PATH". Despues cierra esta ventana y vuelve a ejecutar.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[ui,dev]"
if errorlevel 1 (
  echo ERROR: fallo la instalacion. Copia el texto de arriba y enviaselo a Claude.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pytest -q
echo.
echo Instalacion terminada. Para abrir la app, haz doble clic en INICIAR.bat
pause
