from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from orders.models import Order, OrderItem
from invoices.models import Invoice
from staff.permissions import perm_required


@perm_required('orders.view_order')
def order_list(request):
    status = request.GET.get('status', '')
    orders = Order.objects.select_related('client').prefetch_related('items')

    if status:
        orders = orders.filter(status=status)

    context = {
        'orders': orders,
        'selected_status': status,
        'status_choices': Order.Status.choices,
    }
    return render(request, 'staff/orders/list.html', context)


@perm_required('orders.view_order')
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('client').prefetch_related('items__product_unit__product__inventory'),
        pk=pk,
    )

    if request.method == 'POST':
        # الإجراءات دي بتعدّل حالة الطلب فعليًا (تأكيد/رفض/تسليم/تعديل كمية)
        # فمحتاجة صلاحية "تعديل" مش "عرض" بس.
        if not request.user.has_perm('orders.change_order'):
            messages.error(request, 'ليس لديك صلاحية تعديل الطلبات. تواصل مع الأدمن.')
            return redirect('staff:order_detail', pk=order.pk)

        action = request.POST.get('action')

        if action == 'update_quantities':
            any_changed = False
            for item in order.items.all():
                field_name = f'quantity_{item.pk}'
                if field_name not in request.POST:
                    continue
                try:
                    new_qty = int(request.POST.get(field_name))
                except (TypeError, ValueError):
                    continue
                if new_qty == item.quantity or new_qty < 0:
                    continue
                if new_qty == 0:
                    messages.error(request, 'لا يمكن تصفير كمية صنف من هنا، استخدم خيار رفض الطلب إذا أردت إزالته بالكامل.')
                    continue
                try:
                    order.amend_item_quantity(item, new_qty, actor=request.user)
                    any_changed = True
                except ValueError as e:
                    messages.error(request, str(e))

            if any_changed:
                order.send_for_client_approval(actor=request.user)
                messages.success(request, 'تم تعديل الكميات وإرسال الطلب للعميل للموافقة على التعديل.')
            else:
                messages.info(request, 'لم يتم تطبيق أي تعديلات.')
            return redirect('staff:order_detail', pk=order.pk)

        elif action == 'confirm':
            if order.is_amended and order.status != Order.Status.NEEDS_APPROVAL:
                messages.error(request, 'يحتوي الطلب على تعديلات بانتظار موافقة العميل، ولا يمكن تأكيده مباشرة.')
            else:
                order.confirm(actor=request.user)
                messages.success(request, f'تم تأكيد الطلب #{order.pk}.')
            return redirect('staff:order_detail', pk=order.pk)

        elif action == 'reject':
            reason = request.POST.get('reason', '')
            try:
                order.reject(actor=request.user, reason=reason)
                messages.success(request, f'تم رفض الطلب #{order.pk} وفك الحجز.')
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('staff:order_detail', pk=order.pk)

        elif action == 'deliver':
            if order.status != Order.Status.CONFIRMED:
                messages.error(request, 'يجب تأكيد الطلب أولًا قبل التسليم.')
            else:
                try:
                    with transaction.atomic():
                        order.mark_delivered(actor=request.user)
                        Invoice.issue_for_order(order, actor=request.user)
                    messages.success(request, f'تم تسليم الطلب #{order.pk} وإصدار الفاتورة.')
                except ValidationError as e:
                    messages.error(request, f'تعذّر تسليم الطلب: {"، ".join(e.messages)}')
            return redirect('staff:order_detail', pk=order.pk)

    return render(request, 'staff/orders/detail.html', {'order': order})
