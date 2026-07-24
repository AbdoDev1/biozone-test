from django.urls import re_path

from . import consumers

# مسار WebSocket واحد بس لجرس الإشعارات — كل مستخدم مسجّل دخول بيفتح
# اتصال واحد لما أي صفحة تتحمّل (bell.html)، وبيقفل تلقائيًا لما يسيب
# الصفحة. راجع notifications/consumers.py للتفاصيل.
websocket_urlpatterns = [
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]
