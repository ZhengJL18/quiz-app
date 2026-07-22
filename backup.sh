#!/usr/bin/env bash
# ==============================================================================
# backup.sh — 一课一练 Quiz App — Daily SQLite backup
# ==============================================================================
# Creates consistent snapshots of the SQLite database using .backup command.
# Keeps daily backups (7 days) + weekly backups (4 weeks).
#
# Usage:
#   chmod +x backup.sh
#   ./backup.sh                    # Run once manually
#   ./backup.sh --install-cron     # Install daily cron job
# ==============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
DB_PATH="/app/data/quiz.db"
CONTAINER="quiz-backend"
DATE=$(date +%Y%m%d)
WEEK=$(date +%Y-W%U)

mkdir -p "$BACKUP_DIR"

# ── Run backup ────────────────────────
echo "Backing up quiz.db ..."
docker exec "$CONTAINER" sqlite3 "$DB_PATH" ".backup /tmp/quiz-backup.db"
docker cp "${CONTAINER}:/tmp/quiz-backup.db" "${BACKUP_DIR}/quiz-${DATE}.db"
docker exec "$CONTAINER" rm /tmp/quiz-backup.db

# Weekly snapshot
cp "${BACKUP_DIR}/quiz-${DATE}.db" "${BACKUP_DIR}/quiz-${WEEK}.db"

# Cleanup: keep 7 daily, 4 weekly
find "$BACKUP_DIR" -name "quiz-????????.db" -mtime +7 -delete
OLD_WEEKLIES=$(find "$BACKUP_DIR" -name "quiz-????-W??.db" | sort -r | tail -n +5)
if [ -n "$OLD_WEEKLIES" ]; then
    echo "$OLD_WEEKLIES" | xargs rm -f
fi

echo "Backup saved: ${BACKUP_DIR}/quiz-${DATE}.db ($(du -h "${BACKUP_DIR}/quiz-${DATE}.db" | cut -f1))"
echo "Total backups: $(find "$BACKUP_DIR" -name 'quiz-????????.db' | wc -l) daily + $(find "$BACKUP_DIR" -name 'quiz-????-W??.db' | wc -l) weekly"

# ── Install cron (if requested) ───────
if [ "${1:-}" = "--install-cron" ]; then
    CRON_CMD="0 4 * * * ${SCRIPT_DIR}/backup.sh >> ${BACKUP_DIR}/backup.log 2>&1"
    if ! (crontab -l 2>/dev/null | grep -q "backup.sh"); then
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo "Cron job installed: daily backup at 4 AM."
    else
        echo "Cron job already exists."
    fi
fi
