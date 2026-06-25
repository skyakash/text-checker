#!/usr/bin/env bash
# Backup the knowledge base (glossary + RAG vector store) to a timestamped tarball.
# The data/ directory is the complete persistent state of the service.
#
# Usage:
#   ./scripts/backup.sh                     # backs up ./data to ./backups/
#   ./scripts/backup.sh /path/to/backups    # custom backup destination
#
# Restore:
#   tar -xzf backups/text-checker-data-2026-06-25T10-30-00.tar.gz

set -euo pipefail

DEST="${1:-./backups}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H-%M-%S")
ARCHIVE="${DEST}/text-checker-data-${TIMESTAMP}.tar.gz"
SOURCE="./data"

mkdir -p "$DEST"

if [ ! -d "$SOURCE" ]; then
    echo "No data directory found at $SOURCE — nothing to back up." >&2
    exit 0
fi

tar -czf "$ARCHIVE" -C "$(dirname "$SOURCE")" "$(basename "$SOURCE")"
echo "Backed up to: $ARCHIVE"

# Prune backups older than 30 days
find "$DEST" -name "text-checker-data-*.tar.gz" -mtime +30 -delete
