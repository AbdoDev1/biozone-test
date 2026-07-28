from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import Order
from .decorators import client_required

__all__ = [
    'order_detail', 'order_items', 'order_list',
    'order_approve_amendment', 'order_reject_amendment',
]


@client_required
def order_detail(request, pk):
    # مبقاش بيجيب items هنا — صفحة التفاصيل بقت ملخّص بس (رقم الطلب، الحالة،
    # التنبيهات، زرار الإلغاء)، وقائمة الأصناف نفسها انتقلت لصفحة منفصلة
    # (order_items) عشان الصفحة متبقاش مزدحمة، خصوصًا لو الطلب فيه أصناف كتير.
    order = get_object_or_404(
        Order.objects.select_related('invoice'), pk=pk, client=request.user,
    )
    items_count = order.items.count()
    invoice = order.invoice if hasattr(order, 'invoice') else None
    return render(request, 'orders/order_detail.html', {
        'order': order, 'items_count': items_count, 'invoice': invoice,
    })


@client_required
def order_items(request, pk):
    """أصناف الطلب — في صفحة منفصلة عن order_detail، ومقسّمة صفحات لو الطلب فيه أصناف كتير."""
    order = get_object_or_404(Order, pk=pk, client=request.user)
    items_qs = order.items.select_related('product_unit__product').order_by('pk')
    paginator = Paginator(items_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'orders/order_items.html', {'order': order, 'items': page_obj, 'page_obj': page_obj})


@client_required
def order_list(request):
    orders_qs = Order.objects.filter(client=request.user).prefetch_related('items')
    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'orders/order_list.html', {'orders': page_obj, 'page_obj': page_obj})


@client_required
@require_POST
def order_approve_amendment(request, pk):
    order = get_object_or_404(Order, pk=pk, client=request.user)
    if order.status != Order.Status.NEEDS_APPROVAL:
        messages.error(request, 'هذا الطلب ليس بانتظار موافقتك.')
        return redirect('orders:order_detail', pk=order.pk)
    order.client_approve_amendment(actor=request.user)
    messages.success(request, f'تمت الموافقة على التعديل، وأصبح الطلب #{order.pk} مؤكدًا الآن.')
    return redirect('orders:order_detail', pk=order.pk)


@client_required
@require_POST
def order_reject_amendment(request, pk):
    order = get_object_or_404(Order, pk=pk, client=request.user)
    if order.status != Order.Status.NEEDS_APPROVAL:
        messages.error(request, 'هذا الطلب ليس بانتظار موافقتك.')
        return redirect('orders:order_detail', pk=order.pk)
    order.client_reject_amendment(actor=request.user)
    messages.success(request, f'تم رفض التعديل، وتم رفض الطلب #{order.pk}.')
    return redirect('orders:order_detail', pk=order.pk)
