from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ActivityLog(models.Model):
    """
    سجل نشاط عام (Audit Log + Chatter) — بديل عام لِـ orders.OrderLog
    (اللي فضل مقفول على الطلبات بس)، يشتغل على أي موديل في النظام من غير
    أي migration إضافية لكل كيان جديد، لأن الربط عن طريق ContentType عام
    (GenericForeignKey) مش FK مباشر لموديل معيّن. راجع "مرحلة 2" في
    ROADMAP.md لتفاصيل القرار وسبب دمج الـ Audit Log مع الـ Chatter في
    موديل واحد (تكلفة شبه صفرية لأن البنية واحدة).

    النوعين الأساسيين:
    - CREATED / UPDATED: تسجيل تلقائي من الكود نفسه وقت الحفظ في الـ view
      (مش من الموظف مباشرة) — ده الجزء اللي بيمثّل "مين عدّل إيه وإمتى".
    - NOTE: "Chatter" — ملاحظة داخلية بيكتبها موظف يدويًا من فورم في
      الصفحة، وتفضل ظاهرة على السجل لباقي الموظفين (فكرة من Odoo).
    """
    class Event(models.TextChoices):
        CREATED = 'CREATED', 'تم الإنشاء'
        UPDATED = 'UPDATED', 'تعديل بيانات'
        DELETED = 'DELETED', 'تم الحذف'
        NOTE = 'NOTE', 'ملاحظة'

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    event = models.CharField(max_length=20, choices=Event.choices)
    # وصف مختصر تلقائي لما اتغيّر فعليًا (مثال: "الاسم: أ → ب، نشط: نعم → لا").
    # بيتولّد من الكود وقت الحفظ (شوف activity/services.py)، مش حقل حر للموظف.
    changes_summary = models.TextField(blank=True)
    # نص الملاحظة اليدوية (Chatter) — فاضي في أحداث CREATED/UPDATED التلقائية.
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activity_logs',
    )

    class Meta:
        verbose_name = 'سجل نشاط'
        verbose_name_plural = 'سجل الأنشطة'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.get_event_display()} — {self.content_type.name} #{self.object_id}'
