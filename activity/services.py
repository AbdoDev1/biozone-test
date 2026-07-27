"""
دوال مساعدة لتسجيل الأنشطة — الواجهة الوحيدة اللي المفروض أي view يستخدمها
بدل ما ينشئ ActivityLog يدويًا في كل مكان (لو شكل التسجيل احتاج يتغيّر
بعدين، بيتغيّر هنا مرة واحدة بس).
"""
from django.contrib.contenttypes.models import ContentType

from .models import ActivityLog


def log_activity(instance, event, user=None, note='', changes_summary=''):
    """يسجّل حدث نشاط واحد على أي instance عنده pk بالفعل."""
    content_type = ContentType.objects.get_for_model(instance.__class__)
    return ActivityLog.objects.create(
        content_type=content_type,
        object_id=instance.pk,
        event=event,
        note=note,
        changes_summary=changes_summary,
        created_by=user,
    )


def log_created(instance, user=None):
    return log_activity(instance, ActivityLog.Event.CREATED, user=user)


def log_note(instance, note, user=None):
    return log_activity(instance, ActivityLog.Event.NOTE, user=user, note=note)


def diff_summary(old_values, new_instance, fields):
    """
    بتقارن dict من القيم القديمة (اتاخدت *قبل* الحفظ) بقيم الحقول الحالية
    على instance بعد الحفظ، وترجع سطر عربي مختصر بس للحقول اللي اتغيّرت
    فعلًا (مش كل الحقول). بترجع string فاضي لو مفيش أي تغيير حقيقي —
    الـ view وقتها مايسجّلش UPDATED خالص بدل ما يسجّل سطر فاضي.

    مثال استخدام في view:
        old_values = {f: getattr(product, f) for f in TRACKED_FIELDS}
        form.save()
        summary = diff_summary(old_values, product, TRACKED_FIELDS)
        if summary:
            log_activity(product, ActivityLog.Event.UPDATED, user=request.user, changes_summary=summary)
    """
    parts = []
    for field_name in fields:
        old_value = old_values.get(field_name)
        new_value = getattr(new_instance, field_name)
        if old_value != new_value:
            label = new_instance._meta.get_field(field_name).verbose_name
            parts.append(f'{label}: {old_value} → {new_value}')
    return '، '.join(parts)


def delete_activity_logs_for(instance):
    """
    بتمسح كل سجلات النشاط الخاصة بـ instance قبل ما هو نفسه يتمسح. لازمة
    لأن الربط بـ ActivityLog عن طريق ContentType عام (object_id) مش FK
    حقيقي على الموديل، فمفيش CASCADE تلقائي من قاعدة البيانات وقت حذف
    السجل الأصلي — لازم تتنادى صراحةً من أي delete view (زي product_delete)
    قبل استدعاء instance.delete()، وإلا سجلات النشاط تفضل يتيمة في القاعدة.
    """
    content_type = ContentType.objects.get_for_model(instance.__class__)
    ActivityLog.objects.filter(content_type=content_type, object_id=instance.pk).delete()
