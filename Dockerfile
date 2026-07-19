# --- مرحلة 1: بناء Tailwind CSS ---
# مرحلة منفصلة بس عشان نبني tailwind.css من التمبليتس الحالية وقت الـ build.
# مفيش Node في الصورة النهائية خالص — الناتج (ملف CSS واحد) بس اللي بيتنقل.
FROM node:20-slim AS css-builder
WORKDIR /build
COPY package.json tailwind.config.js ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./frontend/
COPY templates/ ./templates/
COPY staff/templates/ ./staff/templates/
COPY staff/templatetags/ ./staff/templatetags/
COPY orders/templates/ ./orders/templates/
COPY accounts/templates/ ./accounts/templates/
COPY invoices/templates/ ./invoices/templates/
COPY notifications/templates/ ./notifications/templates/
COPY store/templates/ ./store/templates/
RUN npx tailwindcss -i ./frontend/input.css -o ./static/css/tailwind.css --minify

# --- مرحلة 2: صورة التشغيل (Python فقط) ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# مكتبات نظام لازمة لـ psycopg2 و Pillow + curl لـ healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# استبدال tailwind.css المبني محليًا (ده بيتحدث تلقائيًا مع أي تعديل في
# التمبليتس، من غير الحاجة لـ Node وقت التشغيل ولا تشغيل build يدوي)
COPY --from=css-builder /build/static/css/tailwind.css /app/static/css/tailwind.css

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
