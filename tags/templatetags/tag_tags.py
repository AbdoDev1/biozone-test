from django import template
from django.contrib.contenttypes.models import ContentType

from tags.models import Tag
from tags.services import tags_for

register = template.Library()


@register.inclusion_tag('tags/_panel.html', takes_context=True)
def tag_panel(context, obj):
    """
    شارات الوسوم الحالية + قائمة إضافة/إزالة لأي كيان (طلب، منتج، ...)،
    بدل ما كل صفحة تفاصيل تكرر نفس الكود (نفس فكرة activity_tags.activity_panel).
    الاستخدام في أي template:

        {% load tag_tags %}
        {% tag_panel order %}

    الـ object لازم يكون له pk بالفعل (مش instance جديد لسه ما اتحفظش).
    """
    content_type = ContentType.objects.get_for_model(obj.__class__)
    request = context.get('request')
    return {
        'current_tags': tags_for(obj),
        'all_tags': Tag.objects.all(),
        'app_label': content_type.app_label,
        'model_name': content_type.model,
        'object_id': obj.pk,
        'request': request,
        'color_choices': Tag.Color.choices,
    }
