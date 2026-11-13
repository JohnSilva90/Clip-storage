#!/usr/bin/env bash
# Clip Storage: liga o servidor no Linux/Mac
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "Instale o FFmpeg primeiro."; exit 1; }
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
pip install -q -r requirements-ia.txt || echo "Sem faster-whisper: cortes sem legenda."
[ -f .env ] || cp configuracao-exemplo.txt .env
uvicorn app.main:app --reload
