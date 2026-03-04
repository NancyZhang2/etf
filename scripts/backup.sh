#!/usr/bin/env bash
# ===========================================
# 数据库备份脚本
# 保留最近7天日备份 + 4周周备份
# ===========================================

set -euo pipefail

# ---------- 配置 ----------
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-etf_user}"
PG_DATABASE="${PG_DATABASE:-etf_quant}"
BACKUP_DIR="${BACKUP_DIR:-/data/etf/backups}"

DATE=$(date +%Y%m%d)
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday

DAILY_DIR="${BACKUP_DIR}/daily"
WEEKLY_DIR="${BACKUP_DIR}/weekly"

# ---------- 准备目录 ----------
mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}"

# ---------- 执行备份 ----------
BACKUP_FILE="${DAILY_DIR}/${PG_DATABASE}-${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup: ${PG_DATABASE} -> ${BACKUP_FILE}"

pg_dump \
    -h "${PG_HOST}" \
    -p "${PG_PORT}" \
    -U "${PG_USER}" \
    -d "${PG_DATABASE}" \
    --no-password \
    --format=plain \
    --no-owner \
    --no-privileges \
    | gzip > "${BACKUP_FILE}"

FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date)] Backup completed: ${BACKUP_FILE} (${FILESIZE})"

# ---------- 周日创建周备份 ----------
if [ "${DAY_OF_WEEK}" = "7" ]; then
    WEEKLY_FILE="${WEEKLY_DIR}/${PG_DATABASE}-week-${DATE}.sql.gz"
    cp "${BACKUP_FILE}" "${WEEKLY_FILE}"
    echo "[$(date)] Weekly backup created: ${WEEKLY_FILE}"
fi

# ---------- 清理旧备份 ----------
# 日备份保留7天
echo "[$(date)] Cleaning daily backups older than 7 days..."
find "${DAILY_DIR}" -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true

# 周备份保留4周
echo "[$(date)] Cleaning weekly backups older than 28 days..."
find "${WEEKLY_DIR}" -name "*.sql.gz" -mtime +28 -delete 2>/dev/null || true

echo "[$(date)] Backup process completed"
