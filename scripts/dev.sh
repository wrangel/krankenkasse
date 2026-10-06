#!/bin/bash
# Entwickeln ohne Container: startet die App direkt aus der virtuellen Umgebung.
set -e

VENV="${VENV:-$HOME/.venvs/krankenkasse}"
cd "$(dirname "$0")/.."

if [[ ! -x "$VENV/bin/streamlit" ]]; then
  echo "Virtuelle Umgebung fehlt unter $VENV."
  echo "Anlegen mit: python3 -m venv $VENV && $VENV/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Beende eine allenfalls laufende Instanz..."
pkill -f "streamlit run app.py" 2>/dev/null || true

echo "Starte die App auf http://localhost:8501"
exec "$VENV/bin/streamlit" run app.py --server.port 8501
