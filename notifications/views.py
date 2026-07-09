from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import timesince

from .models import Notification


def _serialize(notification):
    return {
        'id': notification.pk,
        'title': notification.title,
        'message': notification.message,
        'is_read': notification.is_read,
        'url': notification.get_absolute_url() or '',
        'created_since': timesince(notification.created_at),
    }


@login_required
def notification_bell_data(request):
    """
    نقطة JSON خفيفة بيستدعيها جرس الإشعارات كل كام ثانية (Alpine polling)
    عشان يحدّث نفسه من غير ما المستخدم يعمل refresh للصفحة.
    """
    qs = request.user.notifications.all()[:8]
    return JsonResponse({
        'unread_count': request.user.notifications.filter(is_read=False).count(),
        'items': [_serialize(n) for n in qs],
    })


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()[:100]
    is_staff_view = request.user.role in ('ADMIN', 'WAREHOUSE')
    context = {
        'notifications': notifications,
        'is_staff_view': is_staff_view,
        'notifications_base_template': 'staff/base.html' if is_staff_view else 'base.html',
    }
    return render(request, 'notifications/list.html', context)


@login_required
def notification_open(request, pk):
    """بتحدد الإشعار كمقروء وتودّي المستخدم لوجهته مباشرة."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    target = notification.get_absolute_url()
    return redirect(target or 'notifications:list')


@login_required
def notification_mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    next_url = request.POST.get('next') or request.GET.get('next') or 'notifications:list'
    return redirect(next_url)
