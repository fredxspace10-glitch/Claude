#!/usr/bin/env bash
# macOS / Linux: doble clic o ./iniciar.sh
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { command -v brew >/dev/null && brew install ffmpeg || echo "Instala ffmpeg (sudo apt install ffmpeg)"; }
command -v deno >/dev/null || command -v node >/dev/null || { command -v brew >/dev/null && brew install deno || curl -fsSL https://deno.land/install.sh | sh; }
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -U -r requirements.txt
( sleep 3; (command -v open >/dev/null && open http://localhost:5000) || xdg-open http://localhost:5000 ) >/dev/null 2>&1 &
python app.py
