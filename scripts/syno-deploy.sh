#!/bin/bash
set -e

# To be run on the Synology (Task Scheduler, user-defined script):
#
#   bash /volume1/homes/Matthias/Drive/Programming/grundversicherungsrechner/scripts/syno-deploy.sh
#
# Building and publishing happen on the Mac via "make prod". This script only
# pulls and restarts - it never builds. The Synology lacks everything needed for
# that anyway.
#
# The file reaches the NAS through Synology Drive, not through git. It can
# therefore be older than the version on the Mac; the line below says which one
# actually ran.
SCRIPT_VERSION="2026-10-06c"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="${PROJECT_DIR:-/volume1/homes/Matthias/Drive/Programming/grundversicherungsrechner}"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"
IMAGE="wrangel/grundversicherungsrechner"
# The container name comes from the project name pinned in
# docker-compose.yml, so it no longer depends on the folder name.
SERVICE="grundversicherungsrechner-app-1"

echo -e "${GREEN}syno-deploy.sh ${SCRIPT_VERSION}${NC}"
[[ -f "$COMPOSE_FILE" ]] || { echo -e "${RED}No compose file at $COMPOSE_FILE${NC}"; exit 1; }

# Compose v2 is a subcommand of docker, v1 was a program of its own. Try v2
# first, so this survives updates to the Container Manager.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi
echo "   using: $COMPOSE"
COMPOSE_CMD=($COMPOSE -f "$COMPOSE_FILE")

# ==============================================================================
# Pull
#
# "compose pull" reads the compose file and fetches exactly the tag written
# there. No guessing against Docker Hub's tag list - with abstractaltitudes that
# had led to some arbitrary sha tag being pulled while the one actually in use
# was never refreshed.
# ==============================================================================
echo -e "${GREEN}Pulling the image named in the compose file...${NC}"
"${COMPOSE_CMD[@]}" pull

# down + up rather than restart: that rebuilds the network. On this NAS the
# bridge has repeatedly come back without its iptables FORWARD rules, leaving
# the containers with no route out. For this app that is especially awkward - it
# fetches its premium data from the BAG.
echo -e "${GREEN}Bringing the stack back up...${NC}"
"${COMPOSE_CMD[@]}" down
docker network prune -f >/dev/null 2>&1 || true
# --no-build: nothing is built on the NAS. If the image is missing, the script
# should fail rather than start compiling pandas.
"${COMPOSE_CMD[@]}" up -d --no-build

# NOTE: abstractaltitudes once had "docker volume prune -f" here. That deletes
# every unused volume on the NAS, other people's data included. Here it would
# also be self-defeating: the premium-cache volume holds the BAG's 12 MB file.
# Without it, every start pays for the full download.

# ==============================================================================
# Check
#
# "container is running" does not mean "app responds": Streamlit listens before
# it has loaded the premium data. The health endpoint tells the two apart.
# ==============================================================================
echo -e "${GREEN}Waiting for the app to respond...${NC}"
ready=false
for _ in $(seq 1 45); do
  sleep 2
  if docker exec "$SERVICE" python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" \
      >/dev/null 2>&1; then
    ready=true
    break
  fi
done

if [[ "$ready" != "true" ]]; then
  echo -e "${RED}The app did not become ready within 90 seconds.${NC}"
  echo -e "${YELLOW}   Look at the log with: docker logs $SERVICE${NC}"
  exit 1
fi
echo -e "${GREEN}App responds.${NC}"

# This app is worthless without internet - it fetches the premium data from the
# BAG. After the network has been rebuilt, an explicit probe is worth it.
echo -e "${GREEN}Checking that the container can reach the outside...${NC}"
if docker exec "$SERVICE" python -c \
    "import urllib.request; urllib.request.urlopen('https://opendata.bagnet.ch', timeout=20)" \
    >/dev/null 2>&1; then
  echo -e "${GREEN}Connection to the BAG is up.${NC}"
else
  echo -e "${YELLOW}The container cannot reach opendata.bagnet.ch.${NC}"
  echo -e "${YELLOW}   The app runs but cannot fetch premium data. Usually this is${NC}"
  echo -e "${YELLOW}   the network after the rebuild - or name resolution. To check:${NC}"
  echo -e "${YELLOW}     docker exec $SERVICE python -c \"import socket; print(socket.gethostbyname('opendata.bagnet.ch'))\"${NC}"
fi

# ==============================================================================
# Clean up - last, so that a failure above leaves every fallback standing.
#
# This project's images only. "docker system prune -af" would remove every
# unused image on the NAS, including other containers'. "docker rmi" without -f
# refuses to delete an image in use - the running version is therefore safe by
# itself.
# ==============================================================================
echo -e "${GREEN}Clearing out old images...${NC}"
echo "   before:"
docker images --format '     {{.Repository}}:{{.Tag}}  {{.Size}}  ({{.CreatedSince}})' \
  | grep grundversicherungsrechner || echo "     (none)"

# The superseded version loses its tag when the new one is pulled and becomes
# dangling. That is where most of the space sits.
reclaimed=$(docker image prune -f 2>/dev/null | tail -1)
echo "     ${reclaimed:-nothing to reclaim}"

echo "   after:"
docker images --format '     {{.Repository}}:{{.Tag}}  {{.Size}}  ({{.CreatedSince}})' \
  | grep grundversicherungsrechner || echo "     (none)"

echo -e "${GREEN}Done. The app is running on port ${PORT:-8501} of the NAS.${NC}"
