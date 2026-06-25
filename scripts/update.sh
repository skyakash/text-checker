#!/usr/bin/env bash
# Zero-downtime update for the Docker Compose single-replica deployment.
# Pulls latest code, rebuilds the image, and restarts the service.
#
# Usage (run from the project root):
#   ./scripts/update.sh

set -euo pipefail

echo "=== [1/4] Backing up data ==="
bash scripts/backup.sh

echo "=== [2/4] Pulling latest code ==="
git pull --ff-only

echo "=== [3/4] Building new image ==="
docker build -t text-checker:latest .

echo "=== [4/4] Restarting service ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d service

echo ""
echo "=== Waiting for /readyz ==="
for i in {1..20}; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/readyz)
    if [ "$STATUS" = "200" ]; then
        echo "Service is ready (HTTP 200)"
        break
    fi
    echo "  attempt $i: HTTP $STATUS — retrying in 3s..."
    sleep 3
done

if [ "$STATUS" != "200" ]; then
    echo "Service did not become ready after 60s. Check logs:" >&2
    echo "  docker compose logs service --tail=50" >&2
    exit 1
fi
