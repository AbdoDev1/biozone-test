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

echo "== تشغيل gunicorn =="
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
