#!/usr/bin/env bash
# Create a timestamped backup of data/ and PostgreSQL dump with SHA-256 verification.

set -euo pipefail
export LC_ALL=C

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_PATH="${BACKUP_DIR}/logistics_backup_${TIMESTAMP}.tar.gz"
CHECKSUM_PATH="${ARCHIVE_PATH}.sha256"

mkdir -p "${BACKUP_DIR}"

if command -v docker >/dev/null 2>&1 && docker compose ps --status running 2>/dev/null | grep -q "db"; then
    echo "[INFO] Exporting PostgreSQL database dump..."
    docker compose exec -T db pg_dump -U "${POSTGRES_USER:-logistics}" "${POSTGRES_DB:-logistics_db}" \
        > "${BACKUP_DIR}/db_${TIMESTAMP}.sql"
fi

echo "[INFO] Archiving data directory into ${ARCHIVE_PATH}..."
tar -czf "${ARCHIVE_PATH}" data sql

sha256sum "${ARCHIVE_PATH}" > "${CHECKSUM_PATH}"
sha256sum -c "${CHECKSUM_PATH}"

echo "[INFO] Backup completed and verified: ${ARCHIVE_PATH}"
