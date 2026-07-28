from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.models import User
from activity.models import ActivityLog
from activity.services import log_activity
from .models import Tag
from .services import add_tag, remove_tag

TAG_NAME_MAX_LENGTH = 50


def _can_manage_tags(user):
    """نفس شرط activity.views.add_note: أي موظف (أدمن/مخزن) قادر يدير الوسوم — مش عميل."""
    return user.is_authenticated and user.role in (User.Role.ADMIN, User.Role.WAREHOUSE)


@login_required
@require_POST
def tag_add(request, app_label, model_name, object_id):
    """
    نقطة نهاية عامة واحدة لإضافة وسم على أي كيان في النظام (طلب، منتج،
    ...)، بنفس نمط activity.views.add_note — بدل ما نعمل view منفصل لكل
    قسم في كل مرة نحتاج فيها وسوم على كيان جديد.
    """
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'staff:dashboard'

    if not _can_manage_tags(request.user):
        messages.error(request, 'ليس لديك صلاحية إضافة وسوم.')
        return redirect(next_url)

    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    model_class = content_type.model_class()
    instance = get_object_or_404(model_class, pk=object_id)

    name = request.POST.get('name', '').strip()
    color = request.POST.get('color', '').strip() or None
    if color not in dict(Tag.Color.choices):
        color = None

    if not name:
        messages.error(request, 'يجب كتابة اسم الوسم.')
    elif len(name) > TAG_NAME_MAX_LENGTH:
        messages.error(request, f'اسم الوسم طويل جدًا ({TAG_NAME_MAX_LENGTH} حرف كحد أقصى).')
    else:
        add_tag(instance, name, color=color, user=request.user)
        log_activity(
            instance, ActivityLog.Event.UPDATED, user=request.user,
            changes_summary=f'تمت إضافة وسم "{name}"',
        )
        messages.success(request, f'تم إضافة وسم "{name}".')

    return redirect(next_url)


@login_required
@require_POST
def tag_remove(request, app_label, model_name, object_id, tag_id):
    """يشيل وسم واحد عن كيان معيّن (الوسم نفسه يفضل موجود في النظام لاستخدامه على عناصر تانية)."""
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'staff:dashboard'

    if not _can_manage_tags(request.user):
        messages.error(request, 'ليس لديك صلاحية إزالة وسوم.')
        return redirect(next_url)

    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    model_class = content_type.model_class()
    instance = get_object_or_404(model_class, pk=object_id)
    tag = get_object_or_404(Tag, pk=tag_id)

    remove_tag(instance, tag_id)
    log_activity(
        instance, ActivityLog.Event.UPDATED, user=request.user,
        changes_summary=f'تمت إزالة وسم "{tag.name}"',
    )
    messages.success(request, 'تم إزالة الوسم.')
    return redirect(next_url)
