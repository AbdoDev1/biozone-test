from django import template
from django.contrib.contenttypes.models import ContentType

from activity.models import ActivityLog

register = template.Library()


@register.inclusion_tag('activity/_panel.html', takes_context=True)
def activity_panel(context, obj):
    """
    بيعرض تايم لاين النشاط + فورم إضافة ملاحظة لأي سجل، من غير ما كل صفحة
    تفاصيل (عميل/منتج/...) تكرر نفس الكود. الاستخدام في أي template:

        {% load activity_tags %}
        {% activity_panel profile %}

    الـ object لازم يكون له pk بالفعل (مش instance جديد لسه ما اتحفظش).
    """
    content_type = ContentType.objects.get_for_model(obj.__class__)
    logs = (
        ActivityLog.objects
        .filter(content_type=content_type, object_id=obj.pk)
        .select_related('created_by')[:50]
    )
    request = context.get('request')
    return {
        'logs': logs,
        'app_label': content_type.app_label,
        'model_name': content_type.model,
        'object_id': obj.pk,
        'request': request,
    }
