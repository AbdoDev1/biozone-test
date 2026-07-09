"""
دوال مساعدة لإرسال الإشعارات — أي app في النظام يقدر يستدعيها من غير ما
يعرف تفاصيل موديل Notification. الاستيراد بيبقى جوه الدالة نفسها (مش
أعلى الملف) في الأماكن اللي بتستخدمها من apps تانية، عشان نتفادى أي
circular import بين orders/accounts/notifications.
"""
from accounts.models import User

from .models import Notification


def notify(recipient, kind, title, message='', url_name='', url_kwargs=None, exclude_actor=None):
    """
    إشعار لمستخدم واحد. لو exclude_actor اتبعت وكان هو نفسه الـ recipient
    (يعني الشخص هو اللي عمل الحدث بنفسه) مبنبعتش إشعار — مفيش داعي نقول
    للعميل "وافقت على تعديلك" وهو اللي عمل الفعل بنفسه دلوقتي.
    """
    if exclude_actor is not None and getattr(exclude_actor, 'pk', None) == getattr(recipient, 'pk', None):
        return None
    if recipient is None:
        return None
    return Notification.objects.create(
        recipient=recipient,
        kind=kind,
        title=title,
        message=message,
        url_name=url_name,
        url_kwargs=url_kwargs or {},
    )


def notify_staff_with_perm(codename, kind, title, message='', url_name='', url_kwargs=None, exclude_actor=None):
    """
    بتبعت نفس الإشعار لكل الموظفين النشطين اللي عندهم الصلاحية المطلوبة
    (الأدمن دايمًا مستلم لأنه Superuser، والمخزن لازم يكون عنده الصلاحية
    صراحةً — شوف staff.permissions.PERMISSION_SECTIONS).
    """
    staff = User.objects.filter(
        role__in=[User.Role.ADMIN, User.Role.WAREHOUSE], is_active=True
    )
    notifications = []
    for user in staff:
        if exclude_actor is not None and user.pk == getattr(exclude_actor, 'pk', None):
            continue
        if user.has_perm(codename):
            notifications.append(Notification(
                recipient=user, kind=kind, title=title, message=message,
                url_name=url_name, url_kwargs=url_kwargs or {},
            ))
    if notifications:
        Notification.objects.bulk_create(notifications)
    return notifications
