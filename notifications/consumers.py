import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    اتصال WebSocket واحد لكل مستخدم مسجّل دخول (موظف أو عميل)، بينضم
    لمجموعة خاصة بيه (`notifications_user_<id>`) وبس بيستقبل إشارة خفيفة
    ("فيه جديد") لما notifications.services تنشئ إشعار له.

    الرسالة نفسها مفيش فيها بيانات الإشعار — الجرس (bell.html) لما يستقبلها
    بينادي notifications:bell_data زي ما بيعمل أصلاً في الـ polling القديم،
    عشان يفضل مصدر واحد بس للحقيقة (نفس الـ endpoint، نفس الـ serialization)
    بدل ما نكرر منطق تجهيز البيانات هنا كمان جوه consumer منفصل.
    """

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            # زائر مش مسجل دخول حاول يفتح الاتصال — نرفضه بهدوء، مفيش
            # داعي إشعارات لمستخدم مجهول أصلًا.
            await self.close()
            return

        self.group_name = f'notifications_user_{user.pk}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notify(self, event):
        """Handler للرسايل اللي نوعها 'notify' الجاية من channel layer group
        (شوف notifications/services.py — _push_realtime)."""
        await self.send(text_data=json.dumps({'event': 'new_notification'}))
