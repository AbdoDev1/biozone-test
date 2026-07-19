"""
حماية بسيطة ضد brute-force على شاشات تسجيل الدخول (عميل وموظف).

الفكرة: عداد محاولات فاشلة في الـ cache، مفتاحه (IP + username المُدخل)،
بعد MAX_ATTEMPTS محاولة فاشلة جوه WINDOW_SECONDS بيتم حظر المحاولات لنفس
المفتاح لحد ما الوقت ينتهي. مبني على django.core.cache عشان يشتغل بأي
backend متاح حاليًا (LocMemCache الافتراضي)، ولو اتوصّل Redis كـ cache
backend مستقبلًا (مؤجل حاليًا) هيشتغل معاه تلقائيًا من غير أي تعديل هنا.

ملحوظة: LocMemCache مش مشترك بين عمليات gunicorn المتعددة (كل worker
بيبقى له نسخته)، فالحماية دلوقتي "لكل worker" مش "لكل سيرفر" بالكامل.
ده أفضل بكتير من عدم وجود أي حد على الإطلاق، ولو اتوصّل Redis فعليًا
هيبقى الحد مشترك بين كل الـ workers تلقائيًا.
"""

from django.core.cache import cache

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60  # 15 دقيقة

CACHE_KEY_PREFIX = 'login_attempts'


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _cache_key(request, username):
    username = (username or '').strip().lower()
    return f'{CACHE_KEY_PREFIX}:{_client_ip(request)}:{username}'


def is_login_blocked(request, username):
    """هل المحاولات على الـ (IP, username) ده تعدّت الحد المسموح؟"""
    key = _cache_key(request, username)
    return cache.get(key, 0) >= MAX_ATTEMPTS


def record_failed_login(request, username):
    """تسجيل محاولة فاشلة جديدة، بيبدأ/يمدّد نافذة الـ WINDOW_SECONDS."""
    key = _cache_key(request, username)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, WINDOW_SECONDS)


def reset_login_attempts(request, username):
    """تصفير العداد بعد نجاح تسجيل الدخول."""
    cache.delete(_cache_key(request, username))
