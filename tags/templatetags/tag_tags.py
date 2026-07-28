from django import template
from django.contrib.contenttypes.models import ContentType

from staff.templatetags.staff_ui import color_classes
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
    all_tags = Tag.objects.all()
    # خريطة "اسم الوسم (بحروف صغيرة) → كلاسات لونه الحالية" — بتتستخدم في
    # فورم "إضافة وسم" عشان لما الموظف يكتب اسم وسم موجود بالفعل، يشوف
    # فورًا اللون الحقيقي اللي هيتستخدم (بدل ما يختار لون في القائمة
    # ويتجاهله السيرفر بصمت لأن الوسم مالوش لون جديد أصلاً). بترجع dict
    # عادي (مش JSON مُجهّز) عشان |json_script في التمبليت هو اللي يتكفّل
    # بالـ escaping الآمن وقت الحقن جوه الصفحة.
    existing_tag_colors = {tag.name.strip().lower(): color_classes(tag.color) for tag in all_tags}
    return {
        'current_tags': tags_for(obj),
        'all_tags': all_tags,
        'existing_tag_colors': existing_tag_colors,
        'existing_colors_script_id': f'existing-tag-colors-{content_type.app_label}-{content_type.model}-{obj.pk}',
        'app_label': content_type.app_label,
        'model_name': content_type.model,
        'object_id': obj.pk,
        'request': request,
        'color_choices': Tag.Color.choices,
    }
