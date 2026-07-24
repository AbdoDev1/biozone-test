"""
ASGI config for config project.

بيعرّض متغير `application` — ده اللي بيتنادى من daphne/uvicorn وقت التشغيل.
بعد تفعيل Django Channels بقى الملف ده بيوجّه نوعين من الاتصالات:
- http  → نفس Django ASGI app العادي (views/templates/HTMX زي ما هو تمامًا).
- websocket → notifications.routing (جرس الإشعارات اللحظي)، محمي بـ
  AuthMiddlewareStack عشان request.user/scope['user'] يبقى متاح جوه
  الـ consumer بالظبط زي ما بيبقى متاح في أي view عادي (بيعتمد على نفس
  الـ session، يعني نفس تسجيل الدخول بتاع الموقع، مفيش تسجيل دخول منفصل
  للـ WebSocket).

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# لازم نجيب الـ Django ASGI app الأول (وبالتالي django.setup() يتنفذ) قبل
# أي import لأي حاجة بتلمس الموديلات أو الروابط (زي notifications.routing) —
# لو الترتيب اتقلب هتظهر مشكلة "Apps aren't loaded yet".
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

import notifications.routing  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(notifications.routing.websocket_urlpatterns)
    ),
})
