#!/usr/bin/env bash
# =============================================================================
# DTCK Automated Database Backup (PostgreSQL/TimescaleDB)
# Spec §46 / docs/DEPLOYMENT_vi.md §4.6
#
# Usage:
#   ./scripts/backup_db.sh               # Backs up to backups/dtck_YYYYMMDD_HHMMSS.sql.gz
#   BACKUP_DIR=/custom ./scripts/backup_db.sh
#   RETENTION_DAYS=7 ./scripts/backup_db.sh  # Auto-prunes backups older than N days
# =============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARGET_FILE="${BACKUP_DIR}/dtck_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Starting database backup: ${TARGET_FILE}"

# Execute pg_dump inside the db container (supports running via docker compose)
if docker compose ps -q db >/dev/null 2>&1; then
    docker compose exec -T db pg_dump -U dtck -d dtck --clean --if-exists | gzip > "${TARGET_FILE}"
else
    echo "[ERROR] Docker container 'db' is not running!" >&2
    exit 1
fi

SIZE="$(du -h "${TARGET_FILE}" | cut -f1)"
echo "[INFO] Backup completed successfully: ${TARGET_FILE} (${SIZE})"

# Retention policy: remove backups older than RETENTION_DAYS
if [[ "${RETENTION_DAYS}" -gt 0 ]]; then
    find "${BACKUP_DIR}" -name "dtck_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \; || true
    echo "[INFO] Pruned backups older than ${RETENTION_DAYS} days."
fi
