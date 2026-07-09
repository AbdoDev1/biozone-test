from django.db import models
from django.urls import NoReverseMatch, reverse

from accounts.models import User


class Notification(models.Model):
    """
    إشعار موجّه لمستخدم واحد (موظف أو عميل). النظام عام وبيتغذّى من أي
    مكان في الكود عن طريق notifications.services.notify /
    notify_staff_with_perm — مش لازم تعرف تفاصيل الموديل ده لتستخدمه.
    """

    class Kind(models.TextChoices):
        NEW_ORDER = 'NEW_ORDER', 'طلب جديد'
        ORDER_NEEDS_APPROVAL = 'ORDER_NEEDS_APPROVAL', 'طلب يحتاج موافقتك على تعديل'
        ORDER_CONFIRMED = 'ORDER_CONFIRMED', 'تم تأكيد الطلب'
        ORDER_REJECTED = 'ORDER_REJECTED', 'تم رفض الطلب'
        ORDER_DELIVERED = 'ORDER_DELIVERED', 'تم تسليم الطلب'
        CLIENT_APPROVED_AMENDMENT = 'CLIENT_APPROVED_AMENDMENT', 'العميل وافق على التعديل'
        CLIENT_REJECTED_AMENDMENT = 'CLIENT_REJECTED_AMENDMENT', 'العميل رفض التعديل'
        NEW_CLIENT_REGISTRATION = 'NEW_CLIENT_REGISTRATION', 'طلب تسجيل عميل جديد'

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=200)
    message = models.CharField(max_length=300, blank=True)

    # رابط الوجهة (اختياري) — بنخزّن اسم الـ URL + الـ kwargs بدل رابط ثابت
    # عشان يفضل شغّال حتى لو اتغيّر شكل الروابط مستقبلًا.
    url_name = models.CharField(max_length=100, blank=True)
    url_kwargs = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f'{self.title} → {self.recipient.username}'

    def get_absolute_url(self):
        if not self.url_name:
            return ''
        try:
            return reverse(self.url_name, kwargs=self.url_kwargs)
        except NoReverseMatch:
            return ''
