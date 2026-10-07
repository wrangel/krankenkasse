#!/bin/bash
# Frees the port the app is meant to run on - but only if what holds it belongs
# to this project. Other processes are not killed; the script would rather stop
# and say what is in the way.
free_port() {
  local port="$1"

  # This project's container first, otherwise lsof reports the Docker proxy.
  if docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo "Stopping this project's container..."
    docker compose down --remove-orphans >/dev/null 2>&1 || true
  fi

  local pids
  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0

  local foreign=0
  for pid in $pids; do
    # Only end our own Streamlit instance.
    if ps -p "$pid" -o command= 2>/dev/null | grep -q "streamlit run app.py"; then
      echo "Ending the local app on port $port (PID $pid)..."
      kill "$pid" 2>/dev/null || true
    else
      echo "Port $port is held by: $(ps -p "$pid" -o command= 2>/dev/null | cut -c1-70)"
      foreign=1
    fi
  done

  if [[ "$foreign" == "1" ]]; then
    echo
    echo "That process does not belong to this project and will not be ended."
    echo "Either stop it yourself, or choose another port:"
    echo "    PORT=8502 make test"
    return 1
  fi

  for _ in $(seq 1 20); do
    lsof -ti tcp:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.5
  done
  echo "Port $port is still being held."
  return 1
}
