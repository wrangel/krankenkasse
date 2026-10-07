#!/bin/bash
# Local trial in a container - built for this machine's architecture.
#
# Important: do not build for linux/amd64. On an Apple machine such an image
# would only run emulated, and pandas crashes inside it with "qemu: uncaught
# target signal 11". For the Synology, use scripts/prod.sh.
set -e

cd "$(dirname "$0")/.."
source scripts/free_port.sh

PORT="${PORT:-8501}"
export PORT

echo "Starting Docker if needed..."
open --background -a Docker 2>/dev/null || true
while ! docker info >/dev/null 2>&1; do
  echo "waiting for Docker..."
  sleep 2
done

ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64) TARGET_PLATFORM="linux/arm64" ;;
  *)             TARGET_PLATFORM="linux/amd64" ;;
esac
export TARGET_PLATFORM
echo "Building for $TARGET_PLATFORM (this machine's architecture)."

free_port "$PORT" || exit 1

docker compose up --build -d

echo "Waiting for the app..."
for _ in $(seq 1 60); do
  if curl -sf http://localhost:$PORT/_stcore/health >/dev/null 2>&1; then
    echo "Running on http://localhost:$PORT"
    open "http://localhost:$PORT" 2>/dev/null || true
    exit 0
  fi
  sleep 2
done

echo "The app did not come up. Log:"
docker compose logs --tail 40
exit 1
