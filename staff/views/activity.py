from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from activity.models import ActivityLog
from staff.permissions import perm_required

STAFF_LIST_PAGE_SIZE = 30


@perm_required('activity.view_activitylog')
def activity_list(request):
    """
    نسخة مبسطة من ActivityLogAdmin (كانت في /admin/activity/activitylog/) —
    عرض/بحث/فلترة بس، بنفس القيود اللي كانت موجودة في الـ admin نفسه:
    السجل للقراءة فقط من هنا (has_add_permission=False هناك)، مفيش إضافة
    ولا تعديل ولا حذف يدوي — السجل بيتكتب من الكود بس وقت الحفظ (راجع
    activity/services.py)، فمفيش داعي أي فورم هنا أصلًا.
    """
    logs = ActivityLog.objects.select_related('content_type', 'created_by')

    search_q = request.GET.get('q', '').strip()
    event_filter = request.GET.get('event', '')
    content_type_filter = request.GET.get('content_type', '')

    if search_q:
        logs = logs.filter(Q(note__icontains=search_q) | Q(changes_summary__icontains=search_q))
    if event_filter:
        logs = logs.filter(event=event_filter)
    if content_type_filter:
        logs = logs.filter(content_type_id=content_type_filter)

    # قائمة أنواع الكيانات اللي فعلاً ليها سجلات نشاط (بدل كل ContentType
    # المسجل في النظام)، عشان الفلتر يعرض بس اختيارات ذات معنى.
    content_type_choices = ContentType.objects.filter(
        pk__in=ActivityLog.objects.values_list('content_type_id', flat=True).distinct()
    ).order_by('model')

    paginator = Paginator(logs, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'staff/activity/list.html', {
        'page_obj': page_obj,
        'logs': page_obj,
        'search_q': search_q,
        'event_filter': event_filter,
        'content_type_filter': content_type_filter,
        'event_choices': ActivityLog.Event.choices,
        'content_type_choices': content_type_choices,
    })
