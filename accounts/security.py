"""
حماية بسيطة ضد brute-force على شاشات تسجيل الدخول (عميل وموظف).

الفكرة: عداد محاولات فاشلة في الـ cache، مفتاحه (IP + username المُدخل)،
بعد MAX_ATTEMPTS محاولة فاشلة جوه WINDOW_SECONDS بيتم حظر المحاولات لنفس
المفتاح لحد ما الوقت ينتهي. مبني على django.core.cache (Redis حاليًا،
راجع CACHES في settings.py)، فالحد مشترك فعليًا بين كل عمليات gunicorn.

ملحوظة أمان مهمة عن تحديد IP العميل: مينفعش نثق في هيدر X-Forwarded-For
كامل زي ما هو، لأنه هيدر بيقدر أي عميل يبعته بنفسه في الطلب الأصلي —
nginx (راجع nginx/nginx.conf) بيستخدم $proxy_add_x_forwarded_for اللي
بيضيف/يلحق IP العميل الحقيقي في **آخر** السلسلة، مش بيمسح أي قيمة العميل
بعتها هو نفسه الأول. يعني لو اعتمدنا على أول قيمة في X-Forwarded-For
(زي ما كان الكود قبل كده)، عميل خبيث كان يقدر يبعت X-Forwarded-For بقيمة
عشوائية مختلفة مع كل محاولة دخول فيتهرّب من حد المحاولات تمامًا.
الحل: نعتمد على X-Real-IP بدل كده — nginx بيحطه هو بنفسه (proxy_set_header
X-Real-IP $remote_addr) على *كل* طلب رايح للتطبيق، وده بيستبدل/يتجاهل أي
قيمة X-Real-IP يكون العميل بعتها هو في الطلب الأصلي، فمينفعش يتزيّف.
"""

from django.core.cache import cache

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60  # 15 دقيقة

CACHE_KEY_PREFIX = 'login_attempts'

# نفس الرسالة كانت مكتوبة حرفيًا مرتين (بوابة العملاء وبوابة الموظفين) —
# ولو حبينا نغيّر صياغتها يوم ما، كان لازم نتذكر نعدّلها في المكانين مع
# بعض. دلوقتي مصدر واحد بس.
LOGIN_BLOCKED_MESSAGE = 'محاولات دخول كتيرة فشلت. حاول تاني بعد ربع ساعة تقريبًا.'


def _client_ip(request):
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()
    # لو مفيش X-Real-IP خالص (مثلاً تشغيل محلي بدون nginx قدام Django
    # مباشرة)، REMOTE_ADDR هو اتصال TCP فعلي مباشر مع Django نفسه، فمينفعش
    # يتزيّف هو كمان في السيناريو ده.
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
