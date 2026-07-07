#!/bin/bash
# سكريبت اختياري: رفع نسخة من آخر backup لمكان تاني برّه السيرفر (S3، Backblaze
# B2، Google Drive، أو أي حاجة rclone بيدعمها).
#
# ده طبقة حماية إضافية فوق backup_db.sh — لو السيرفر نفسه راح بالكامل (اتسرق،
# القرص باظ)، النسخة الاحتياطية المحلية (backups/) بتروح معاه. النسخة هنا
# بتبقى في مكان تاني تمامًا.
#
# **مش لازم تشغّله دلوقتي.** ده معمول عشان يبقى جاهز لما تحدد مكان الرفع
# (تفعيله = تشغّل الإعداد مرة واحدة تحت + تفتح التعليق (uncomment) على آخر سطر).
#
# --- خطوات التفعيل (مرة واحدة بس) ---
# 1. تثبيت rclone على السيرفر:
#      curl https://rclone.org/install.sh | sudo bash
# 2. تجهيز الحساب البعيد (مثال Backblaze B2، أرخص خيار لنسخ احتياطي):
#      rclone config
#    (هيسألك أسئلة تفاعلية: اسم الـ remote، نوع الخدمة، مفاتيح API)
# 3. بعد ما تجهز remote باسم مثلاً "biozone-backup"، شغّل السكريبت ده بنفس
#    الاسم:
#      RCLONE_REMOTE=biozone-backup:biozone-db-backups ./scripts/backup_upload.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"   # مثال: biozone-backup:biozone-db-backups

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $1" | tee -a "$LOG_FILE"
}

if [ -z "$RCLONE_REMOTE" ]; then
    log "تخطي الرفع الخارجي: RCLONE_REMOTE مش متحدد. راجع تعليقات الملف عشان تفعّله."
    exit 0
fi

if ! command -v rclone >/dev/null 2>&1; then
    log "خطأ: rclone مش متثبت. راجع تعليقات الملف (خطوة 1)."
    exit 1
fi

# نرفع بس أحدث ملف backup (اللي backup_db.sh عمله في نفس التشغيلة دي عادةً)
LATEST=$(ls -t "$BACKUP_DIR"/biozone_*.sql.gz 2>/dev/null | head -n1)
if [ -z "$LATEST" ]; then
    log "مفيش ملفات backup موجودة أصلًا في $BACKUP_DIR — شغّل backup_db.sh الأول."
    exit 1
fi

log "== رفع $LATEST إلى $RCLONE_REMOTE =="
if rclone copy "$LATEST" "$RCLONE_REMOTE"; then
    log "تم الرفع بنجاح."
else
    log "فشل الرفع الخارجي (النسخة المحلية لسه موجودة وسليمة)."
    exit 1
fi
