@echo off
chcp 65001 >nul
cd /d "%~dp0"
where ffmpeg >nul 2>nul || (echo Instalando ffmpeg... & winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements)
where deno >nul 2>nul || where node >nul 2>nul || (echo Instalando Deno, necesario para YouTube... & winget install -e --id DenoLand.Deno --accept-package-agreements --accept-source-agreements)
if not exist .venv (
  echo Preparando el programa por primera vez, espera unos minutos...
  python -m venv .venv || (echo Necesitas instalar Python desde https://www.python.org/downloads/ marcando "Add python.exe to PATH" & pause & exit /b)
)
call .venv\Scripts\activate
pip install -q -U -r requirements.txt
start "" http://localhost:5000
python app.py
pause
