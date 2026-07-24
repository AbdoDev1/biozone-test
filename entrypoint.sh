#!/bin/bash
set -e

echo "== انتظار قاعدة البيانات =="
until python manage.py migrate --check 2>/dev/null || python manage.py migrate --noinput; do
  echo "قاعدة البيانات لسه مش جاهزة، بحاول تاني بعد 2 ثانية..."
  sleep 2
done

echo "== تطبيق الميجريشن =="
python manage.py migrate --noinput

echo "== تجميع الملفات الثابتة =="
python manage.py collectstatic --noinput --clear

# تأكيد وجود حساب الأدمن تلقائيًا لو متغيرات البيئة متحددة في .env.production.
# آمن يتنفذ كل مرة (get_or_create + تحديث) — مش هيبوّظ حساب موجود ولا يعمل تكرار.
if [ -n "${DJANGO_ADMIN_USERNAME:-}" ] && [ -n "${DJANGO_ADMIN_PASSWORD:-}" ]; then
    echo "== التأكد من وجود حساب الأدمن =="
    python manage.py ensure_admin
fi

# عدد الـ workers: لو GUNICORN_WORKERS متحدد صراحة في .env.production بنستخدمه
# زي ما هو (تحكم يدوي كامل). لو مش متحدد، بنحسبه تلقائيًا من عدد أنوية
# المعالج الفعلية للحاوية بمعادلة gunicorn المعتمدة: (2 × الأنوية) + 1.
# ده بيحل مشكلة الرقم الثابت (3) اللي كان مش مبني على سيرفر حقيقي.
if [ -n "${GUNICORN_WORKERS:-}" ]; then
    WORKERS="$GUNICORN_WORKERS"
else
    CORES=$(nproc 2>/dev/null || echo 1)
    WORKERS=$((2 * CORES + 1))
fi
echo "== تشغيل gunicorn بعدد workers: $WORKERS (أنوية متاحة: $(nproc 2>/dev/null || echo '؟')) =="

# config.asgi:application بدل config.wsgi:application، و worker class بقى
# uvicorn (عبر حزمة uvicorn-worker) بدل الـ worker المتزامن الافتراضي —
# ده اللي بيخلي gunicorn يقدر يستضيف اتصالات WebSocket (جرس الإشعارات
# اللحظي) جنب طلبات HTTP العادية في نفس الوقت، مع الاحتفاظ بنفس منطق
# gunicorn لإدارة عدد الـ workers وإعادة التشغيل عند الأعطال.
exec gunicorn config.asgi:application \
    --worker-class uvicorn_worker.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --workers "$WORKERS" \
    --timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
