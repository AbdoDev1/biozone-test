#!/bin/bash
# سكريبت نسخ احتياطي لقاعدة بيانات Biozone.
#
# بيعمل pg_dump كامل لقاعدة البيانات (من داخل حاوية db بتاعة docker-compose)،
# يضغطه (gzip)، ويحفظه في مجلد backups/ جوه المشروع بتاريخ ووقت في اسم الملف.
# وبعدين بيمسح تلقائيًا أي نسخة أقدم من RETENTION_DAYS يوم عشان القرص متمتلاش.
#
# الاستخدام (لازم تشغّله من نفس مجلد المشروع، جنب docker-compose.yml):
#   ./scripts/backup_db.sh
#
# للتشغيل التلقائي اليومي، ضيفه في crontab (راجع docs/تجهيز-النشر-للسيرفر-الحقيقي.md).

set -euo pipefail

# --- الإعدادات ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env.production"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"   # عدد الأيام اللي بنحتفظ فيها بالنسخ قبل ما نمسحها
LOG_FILE="$PROJECT_DIR/logs/backup.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $1" | tee -a "$LOG_FILE"
}

mkdir -p "$BACKUP_DIR" "$PROJECT_DIR/logs"

if [ ! -f "$ENV_FILE" ]; then
    log "خطأ: ملف $ENV_FILE مش موجود. لازم تشغّل السكريبت من مجلد المشروع."
    exit 1
fi

# قراءة بيانات القاعدة من .env.production (نفس الملف اللي Django بيستخدمه)
DB_NAME=$(grep -E '^DB_NAME=' "$ENV_FILE" | cut -d '=' -f2-)
DB_USER=$(grep -E '^DB_USER=' "$ENV_FILE" | cut -d '=' -f2-)
DB_PASSWORD=$(grep -E '^DB_PASSWORD=' "$ENV_FILE" | cut -d '=' -f2-)

if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    log "خطأ: DB_NAME أو DB_USER مش موجودين في $ENV_FILE."
    exit 1
fi

TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')
BACKUP_FILE="$BACKUP_DIR/biozone_${TIMESTAMP}.sql.gz"

log "== بدء النسخ الاحتياطي: $DB_NAME =="

cd "$PROJECT_DIR"
if docker compose exec -T -e PGPASSWORD="$DB_PASSWORD" db \
        pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "تم بنجاح: $BACKUP_FILE ($SIZE)"
else
    log "فشل النسخ الاحتياطي!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# مسح النسخ الأقدم من RETENTION_DAYS يوم
DELETED=$(find "$BACKUP_DIR" -name "biozone_*.sql.gz" -mtime "+$RETENTION_DAYS" -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
    log "تم مسح $DELETED نسخة قديمة (أقدم من $RETENTION_DAYS يوم)."
fi

log "== انتهى =="
