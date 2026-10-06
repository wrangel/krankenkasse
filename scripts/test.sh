#!/bin/bash
# Örtliche Probe im Container - gebaut für die Architektur dieses Rechners.
#
# Wichtig: Nicht für linux/amd64 bauen. Auf einem Apple-Rechner liefe ein solches
# Abbild nur emuliert, und pandas stürzt darin mit "qemu: uncaught target
# signal 11" ab. Für die Synology baut scripts/prod.sh.
set -e

cd "$(dirname "$0")/.."

echo "Starte Docker, falls nötig..."
open --background -a Docker 2>/dev/null || true
while ! docker info >/dev/null 2>&1; do
  echo "warte auf Docker..."
  sleep 2
done

ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64) ZIELPLATTFORM="linux/arm64" ;;
  *)             ZIELPLATTFORM="linux/amd64" ;;
esac
export ZIELPLATTFORM
echo "Baue für $ZIELPLATTFORM (Architektur dieses Rechners)."

docker compose down --remove-orphans 2>/dev/null || true
docker compose up --build -d

echo "Warte auf die App..."
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8501/_stcore/health >/dev/null 2>&1; then
    echo "Läuft auf http://localhost:8501"
    open http://localhost:8501 2>/dev/null || true
    exit 0
  fi
  sleep 2
done

echo "Die App ist nicht hochgekommen. Protokoll:"
docker compose logs --tail 40
exit 1
