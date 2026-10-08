#!/bin/bash
# Developing without a container: starts the app straight from the virtual
# environment.
set -e

VENV="${VENV:-$HOME/.venvs/viaprima}"
cd "$(dirname "$0")/.."
source scripts/free_port.sh

PORT="${PORT:-8501}"

if [[ ! -x "$VENV/bin/streamlit" ]]; then
  echo "No virtual environment at $VENV."
  echo "Create it with: python3 -m venv $VENV && $VENV/bin/pip install -r requirements.txt"
  exit 1
fi

free_port "$PORT" || exit 1

echo "Starting the app on http://localhost:$PORT"
exec "$VENV/bin/streamlit" run app.py --server.port "$PORT"
