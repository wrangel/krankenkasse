#!/bin/bash
# Entwickeln ohne Container: startet die App direkt aus der virtuellen Umgebung.
set -e

VENV="${VENV:-$HOME/.venvs/krankenkasse}"
cd "$(dirname "$0")/.."
source scripts/port_freigeben.sh

PORT="${PORT:-8501}"

if [[ ! -x "$VENV/bin/streamlit" ]]; then
  echo "Virtuelle Umgebung fehlt unter $VENV."
  echo "Anlegen mit: python3 -m venv $VENV && $VENV/bin/pip install -r requirements.txt"
  exit 1
fi

port_freigeben "$PORT" || exit 1

echo "Starte die App auf http://localhost:$PORT"
exec "$VENV/bin/streamlit" run app.py --server.port "$PORT"
