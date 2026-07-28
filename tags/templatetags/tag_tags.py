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
    current_tags = tags_for(obj)
    current_tag_ids = {tag.pk for tag in current_tags}
    # الوسوم الموجودة اللي لسه معملهاش إضافة على العنصر ده — بتتعرض
    # كأزرار جاهزة للنقر جوه فورم "إضافة وسم"، عشان يبقى واضح إن فيه
    # وسوم موجودة أصلاً يقدر يختار منها بدل ما يكتبها من الصفر كل مرة
    # (الـ <datalist> وحدها مش واضحة بما فيه الكفاية كخيار "موجود").
    available_tags = [tag for tag in all_tags if tag.pk not in current_tag_ids]
    # خريطة "اسم الوسم (بحروف صغيرة) → كلاسات لونه الحالية" — بتتستخدم في
    # فورم "إضافة وسم" عشان لما الموظف يكتب اسم وسم موجود بالفعل، يشوف
    # فورًا اللون الحقيقي اللي هيتستخدم (بدل ما يختار لون في القائمة
    # ويتجاهله السيرفر بصمت لأن الوسم مالوش لون جديد أصلاً). بترجع dict
    # عادي (مش JSON مُجهّز) عشان |json_script في التمبليت هو اللي يتكفّل
    # بالـ escaping الآمن وقت الحقن جوه الصفحة.
    existing_tag_colors = {tag.name.strip().lower(): color_classes(tag.color) for tag in all_tags}
    return {
        'current_tags': current_tags,
        'all_tags': all_tags,
        'available_tags': available_tags,
        'existing_tag_colors': existing_tag_colors,
        'existing_colors_script_id': f'existing-tag-colors-{content_type.app_label}-{content_type.model}-{obj.pk}',
        'app_label': content_type.app_label,
        'model_name': content_type.model,
        'object_id': obj.pk,
        'request': request,
        'color_choices': Tag.Color.choices,
    }


@register.inclusion_tag('tags/_badges_small.html')
def tag_badges_small(tags):
    """
    شارات وسوم صغيرة للعرض فقط (بدون إضافة/إزالة) — لصفحات القوائم
    (مثلاً جدول الطلبات) اللي محتاجة تعرض وسوم كل صف من غير ما تكرر
    استعلام لكل صف على حدة.

    الاستخدام في الـ view (استعلام واحد لكل الصفحة، بعدين تعليق النتيجة
    كخاصية على كل عنصر — أبسط من فلتر dict-lookup في التمبليت):

        tags_by_id = tags_for_many(Order, [o.pk for o in orders])
        for order in orders:
            order.tag_list = tags_by_id.get(order.pk, [])

    وفي التمبليت:

        {% load tag_tags %}
        {% tag_badges_small order.tag_list %}
    """
    return {'tags': tags}
