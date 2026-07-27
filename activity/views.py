from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.models import User
from .models import ActivityLog
from .services import log_note


@login_required
@require_POST
def add_note(request, app_label, model_name, object_id):
    """
    نقطة نهاية عامة واحدة لإضافة ملاحظة (Chatter) على أي كيان في النظام،
    بدل ما نعمل view منفصل لكل قسم (عميل/منتج/...). مفيش صلاحية موديل
    محددة مطلوبة هنا عن قصد: أي موظف قادر يوصل لصفحة تفاصيل السجل أصلًا
    (وده اتفلتر بصلاحية view الخاصة بالموديل ده في الـ view بتاعه) يقدر
    يسيب ملاحظة عليها — الشرط الوحيد هنا إنه موظف (أدمن/مخزن) مش عميل.
    """
    if request.user.role not in (User.Role.ADMIN, User.Role.WAREHOUSE):
        messages.error(request, 'ليس لديك صلاحية إضافة ملاحظات.')
        return redirect(request.POST.get('next') or 'staff:dashboard')

    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    model_class = content_type.model_class()
    instance = get_object_or_404(model_class, pk=object_id)

    note = request.POST.get('note', '').strip()
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'staff:dashboard'

    if not note:
        messages.error(request, 'يجب كتابة نص الملاحظة.')
    else:
        log_note(instance, note, user=request.user)
        messages.success(request, 'تم إضافة الملاحظة.')

    return redirect(next_url)
