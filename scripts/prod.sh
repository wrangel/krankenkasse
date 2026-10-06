#!/bin/bash
# Abbild für die Synology bauen und auf Docker Hub schieben.
#
# Gebaut wird linux/amd64 - die Architektur der Synology. Auf einem
# Apple-Rechner ist dieses Abbild nicht lauffähig; das ist in Ordnung, es ist
# nicht für hier gedacht. Zum örtlichen Prüfen scripts/test.sh.
set -e

cd "$(dirname "$0")/.."
ABBILD="$(grep -E '^\s*image:' docker-compose.yml | head -1 | awk '{print $2}')"

echo "Starte Docker, falls nötig..."
open --background -a Docker 2>/dev/null || true
while ! docker info >/dev/null 2>&1; do
  echo "warte auf Docker..."
  sleep 2
done

echo "Prüfe die Rechnung, bevor etwas veröffentlicht wird..."
VENV="${VENV:-$HOME/.venvs/krankenkasse}"
"$VENV/bin/python" test_berechnung.py

echo "Baue $ABBILD für linux/amd64..."
docker build --platform linux/amd64 -t "$ABBILD" .

echo "Anmeldung bei Docker Hub (falls nötig)..."
docker login

echo "Schiebe $ABBILD..."
docker push "$ABBILD"

echo
echo "Fertig. Auf der Synology holen mit:"
echo "    docker pull $ABBILD"
