#!/bin/bash
# Dump the dipti_portal database to a timestamped gzipped SQL file.
# Usage: DB_PASSWORD=... ./scripts/backup-db.sh [output-dir]
set -euo pipefail
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_USER="${DB_USER:-dipti}"
DB_NAME="${DB_NAME:-dipti_portal}"
OUT_DIR="${1:-backups}"

: "${DB_PASSWORD:?DB_PASSWORD not set}"

mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
FILE="$OUT_DIR/${DB_NAME}-${STAMP}.sql.gz"

mysqldump -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" | gzip > "$FILE"
echo "Backup written: $FILE ($(du -h "$FILE" | cut -f1))"
# keep the last 30 backups
ls -1t "$OUT_DIR"/${DB_NAME}-*.sql.gz | tail -n +31 | xargs -r rm --
