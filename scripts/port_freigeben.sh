#!/bin/bash
# Macht den Port frei, auf dem die App laufen soll - aber nur, wenn ihn etwas
# belegt, das zu diesem Projekt gehört. Fremde Prozesse werden nicht abgeschossen;
# dann bricht das Skript lieber ab und sagt, was im Weg steht.
port_freigeben() {
  local port="$1"

  # Container aus diesem Projekt zuerst, sonst meldet lsof gleich den Docker-Proxy.
  if docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo "Stoppe den Container dieses Projekts..."
    docker compose down --remove-orphans >/dev/null 2>&1 || true
  fi

  local pids
  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0

  local fremd=0
  for pid in $pids; do
    # Nur die eigene Streamlit-Instanz beenden.
    if ps -p "$pid" -o command= 2>/dev/null | grep -q "streamlit run app.py"; then
      echo "Beende die örtliche App auf Port $port (PID $pid)..."
      kill "$pid" 2>/dev/null || true
    else
      echo "Port $port ist belegt von: $(ps -p "$pid" -o command= 2>/dev/null | cut -c1-70)"
      fremd=1
    fi
  done

  if [[ "$fremd" == "1" ]]; then
    echo
    echo "Dieser Prozess gehört nicht zu diesem Projekt und wird nicht beendet."
    echo "Entweder ihn selbst stoppen, oder einen anderen Port wählen:"
    echo "    PORT=8502 make test"
    return 1
  fi

  for _ in $(seq 1 20); do
    lsof -ti tcp:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.5
  done
  echo "Port $port wird immer noch gehalten."
  return 1
}
