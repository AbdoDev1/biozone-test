"""
دوال مساعدة للوسوم — الواجهة الوحيدة اللي المفروض أي view يستخدمها بدل ما
ينشئ Tag/TaggedItem يدويًا في كل مكان (نفس فكرة activity/services.py).
"""
from django.contrib.contenttypes.models import ContentType

from .models import Tag, TaggedItem


def tags_for(instance):
    """كل الوسوم الحالية على instance، مرتبة بالاسم."""
    content_type = ContentType.objects.get_for_model(instance.__class__)
    return Tag.objects.filter(
        tagged_items__content_type=content_type,
        tagged_items__object_id=instance.pk,
    ).order_by('name')


def tags_for_many(model_class, object_ids):
    """
    نسخة جماعية من tags_for — بترجع dict {object_id: [tags]} لكل
    الوسوم على مجموعة عناصر من نفس النوع في استعلام واحد، بدل ما نستدعي
    tags_for لكل صف على حدة (N+1) زي في صفحات القوائم (مثلاً جدول
    الطلبات). العناصر اللي مالهاش وسوم أصلًا مش موجودة كمفتاح في الـ dict
    (استخدم .get(pk, []) في التمبليت/الـ view).
    """
    object_ids = list(object_ids)
    if not object_ids:
        return {}
    content_type = ContentType.objects.get_for_model(model_class)
    tagged_items = TaggedItem.objects.filter(
        content_type=content_type, object_id__in=object_ids,
    ).select_related('tag').order_by('tag__name')

    tags_by_object_id = {}
    for tagged_item in tagged_items:
        tags_by_object_id.setdefault(tagged_item.object_id, []).append(tagged_item.tag)
    return tags_by_object_id


def add_tag(instance, tag_name, color=None, user=None):
    """
    يضيف وسم لـ instance — لو الوسم بالاسم ده موجود بالفعل (حتى لو على
    كيان تاني) بيتعاد استخدامه زي ما هو (نفس اللون المحفوظ له مسبقًا)،
    وبيتجاهل 'color' المُمرر في هذه الحالة؛ لو وسم جديد كليًا، بيتنشئ
    باللون المُمرر (أو الرمادي الافتراضي لو مفيش).
    """
    tag_name = tag_name.strip()
    if not tag_name:
        return None
    content_type = ContentType.objects.get_for_model(instance.__class__)
    defaults = {'color': color} if color else {}
    tag, _ = Tag.objects.get_or_create(name=tag_name, defaults=defaults)
    TaggedItem.objects.get_or_create(
        tag=tag, content_type=content_type, object_id=instance.pk,
        defaults={'created_by': user},
    )
    return tag


def remove_tag(instance, tag_id):
    """يشيل وسم واحد بس عن instance (مش الوسم نفسه من النظام — يفضل موجود لاستخدامه على عناصر تانية)."""
    content_type = ContentType.objects.get_for_model(instance.__class__)
    TaggedItem.objects.filter(tag_id=tag_id, content_type=content_type, object_id=instance.pk).delete()


def delete_tagged_items_for(instance):
    """
    بتمسح كل وسوم instance قبل ما هو نفسه يتمسح — لازمة لأن الربط عن طريق
    ContentType عام (مش FK حقيقي)، فمفيش CASCADE تلقائي وقت حذف السجل
    الأصلي (نفس منطق activity.delete_activity_logs_for بالظبط).
    """
    content_type = ContentType.objects.get_for_model(instance.__class__)
    TaggedItem.objects.filter(content_type=content_type, object_id=instance.pk).delete()
