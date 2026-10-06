#!/bin/bash
set -e

# Auf der Synology auszuführen (Aufgabenplaner, benutzerdefiniertes Skript):
#
#   bash /volume1/homes/Matthias/Drive/Programming/krankenkasse/scripts/syno-deploy.sh
#
# Gebaut und veröffentlicht wird auf dem Mac mit "make prod". Dieses Skript holt
# nur und startet neu - es baut nie. Auf der Synology fehlt dafür auch alles
# Nötige.
#
# Die Datei erreicht die NAS über Synology Drive, nicht über git. Sie kann also
# älter sein als die Fassung auf dem Mac; die Zeile unten sagt, welche gelaufen
# ist.
SCRIPT_VERSION="2026-10-06"

GRUEN='\033[0;32m'
GELB='\033[1;33m'
ROT='\033[0;31m'
NC='\033[0m'

PROJEKT_DIR="${PROJEKT_DIR:-/volume1/homes/Matthias/Drive/Programming/krankenkasse}"
COMPOSE_DATEI="${PROJEKT_DIR}/docker-compose.yml"
ABBILD="wrangel/krankenkasse"
DIENST="krankenkasse-app-1"

echo -e "${GRUEN}syno-deploy.sh ${SCRIPT_VERSION}${NC}"
[[ -f "$COMPOSE_DATEI" ]] || { echo -e "${ROT}Keine Compose-Datei unter $COMPOSE_DATEI${NC}"; exit 1; }

# Compose v2 ist ein Unterbefehl von docker, v1 war ein eigenes Programm. Erst v2
# versuchen, damit das über Aktualisierungen des Container Managers hinweg läuft.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi
echo "   verwendet: $COMPOSE"
COMPOSE_BEFEHL=($COMPOSE -f "$COMPOSE_DATEI")

# ==============================================================================
# Holen
#
# "compose pull" liest die Compose-Datei und holt genau die Marke, die dort
# steht. Kein Raten über die Markenliste von Docker Hub - bei abstractaltitudes
# hatte das dazu geführt, dass eine beliebige sha-Marke geholt wurde, während
# die tatsächlich verwendete nie aufgefrischt wurde.
# ==============================================================================
echo -e "${GRUEN}Hole das Abbild aus der Compose-Datei...${NC}"
"${COMPOSE_BEFEHL[@]}" pull

# down + up statt restart: Das baut das Netz neu auf. Auf dieser NAS ist die
# Bridge wiederholt ohne ihre iptables-FORWARD-Regeln zurückgekommen, womit die
# Container keinen Weg nach draussen mehr hatten. Für diese App ist das
# besonders heikel - sie holt ihre Prämiendaten beim BAG.
echo -e "${GRUEN}Stapel neu aufsetzen...${NC}"
"${COMPOSE_BEFEHL[@]}" down
docker network prune -f >/dev/null 2>&1 || true
# --no-build: Auf der NAS wird nicht gebaut. Fehlt das Abbild, soll das Skript
# scheitern und nicht anfangen, pandas zu übersetzen.
"${COMPOSE_BEFEHL[@]}" up -d --no-build

# HINWEIS: Hier stand bei abstractaltitudes einmal "docker volume prune -f". Das
# löscht jedes unbenutzte Volume auf der NAS, also auch fremde Daten. Hier wäre
# es zusätzlich selbstschädigend: Im Volume praemien-cache liegt die 12-MB-Datei
# des BAG. Ohne sie kostet jeder Start den vollen Download.

# ==============================================================================
# Prüfen
#
# "Container läuft" heisst hier nicht "App antwortet": Streamlit hört, bevor es
# die Prämiendaten geladen hat. Der Gesundheitsendpunkt unterscheidet das.
# ==============================================================================
echo -e "${GRUEN}Warte, bis die App antwortet...${NC}"
bereit=false
for _ in $(seq 1 45); do
  sleep 2
  if docker exec "$DIENST" python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" \
      >/dev/null 2>&1; then
    bereit=true
    break
  fi
done

if [[ "$bereit" != "true" ]]; then
  echo -e "${ROT}Die App ist in 90 Sekunden nicht bereit geworden.${NC}"
  echo -e "${GELB}   Protokoll ansehen mit: docker logs $DIENST${NC}"
  exit 1
fi
echo -e "${GRUEN}App antwortet.${NC}"

# Diese App ist ohne Internet wertlos - sie holt die Prämiendaten beim BAG. Nach
# dem Neuaufbau des Netzes lohnt sich die ausdrückliche Probe.
echo -e "${GRUEN}Prüfe, ob der Container nach draussen kommt...${NC}"
if docker exec "$DIENST" python -c \
    "import urllib.request; urllib.request.urlopen('https://opendata.bagnet.ch', timeout=20)" \
    >/dev/null 2>&1; then
  echo -e "${GRUEN}Verbindung zum BAG steht.${NC}"
else
  echo -e "${GELB}Der Container erreicht opendata.bagnet.ch nicht.${NC}"
  echo -e "${GELB}   Die App läuft, kann aber keine Prämiendaten holen. Meist ist das${NC}"
  echo -e "${GELB}   das Netz nach dem Neuaufbau - oder die Namensauflösung. Zum Prüfen:${NC}"
  echo -e "${GELB}     docker exec $DIENST python -c \"import socket; print(socket.gethostbyname('opendata.bagnet.ch'))\"${NC}"
fi

# ==============================================================================
# Aufräumen - zuletzt, damit ein Fehlschlag oben jeden Rückfallpunkt stehen lässt.
#
# Nur Abbilder dieses Projekts. "docker system prune -af" würde jedes unbenutzte
# Abbild auf der NAS entfernen, auch die anderer Container. "docker rmi" ohne -f
# weigert sich, ein benutztes Abbild zu löschen - die laufende Fassung ist damit
# von selbst sicher.
# ==============================================================================
echo -e "${GRUEN}Räume alte Abbilder auf...${NC}"
echo "   vorher:"
docker images --format '     {{.Repository}}:{{.Tag}}  {{.Size}}  ({{.CreatedSince}})' \
  | grep krankenkasse || echo "     (keine)"

# Die abgelöste Fassung verliert beim Holen der neuen ihre Marke und wird
# hängend. Dort liegt der meiste Platz.
befreit=$(docker image prune -f 2>/dev/null | tail -1)
echo "     ${befreit:-nichts freizugeben}"

echo "   nachher:"
docker images --format '     {{.Repository}}:{{.Tag}}  {{.Size}}  ({{.CreatedSince}})' \
  | grep krankenkasse || echo "     (keine)"

echo -e "${GRUEN}Fertig. Die App läuft auf Port ${PORT:-8501} der NAS.${NC}"
