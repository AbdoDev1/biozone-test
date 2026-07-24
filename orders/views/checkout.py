from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from inventory.models import Inventory

from ..cart import Cart
from ..models import Order, OrderItem, SiteConfig
from .decorators import client_required

__all__ = ['checkout']


@client_required
def checkout(request):
    cart = Cart(request)
    items = cart.get_items()

    if not items:
        messages.warning(request, 'سلة المشتريات فارغة.')
        return redirect('orders:cart')

    config = SiteConfig.get_solo()
    total = cart.get_total()

    if config.min_order_amount and total < config.min_order_amount:
        messages.error(
            request,
            f'الحد الأدنى لإجمالي الطلب هو {config.min_order_amount} ج.م. '
            f'إجمالي سلتك الحالي {total} ج.م، يلزم إضافة {config.min_order_amount - total} ج.م إضافية.'
        )
        return redirect('orders:cart')

    if request.method == 'POST':
        # ملحوظة: الطلب هنا لا يحجز ولا يخصم أي كمية من المخزون — بيتسجّل بس
        # في حالة "PENDING" لحد ما المخزن يراجعه ويأكده. الفحص تحت للكمية
        # المتاحة هو تنبيه للعميل بس (تجربة استخدام)، مش قفل فعلي على
        # المخزون؛ ممكن الكمية تتغيّر لحد ما المخزن يراجع الطلب فعليًا.
        product_ids = [item['unit'].product_id for item in items]
        inventories = {
            inv.product_id: inv
            for inv in Inventory.objects.filter(product_id__in=product_ids)
        }

        shortages = []
        for item in items:
            unit = item['unit']
            stock_qty = item['quantity'] * unit.qty_in_small
            item['stock_qty'] = stock_qty
            inv = inventories.get(unit.product_id)
            available = inv.available if inv else 0
            if stock_qty > available:
                shortages.append(f"{unit.product.display_name} ({unit.name}): متاح {available // unit.qty_in_small} {unit.name} فقط")

        if shortages:
            for s in shortages:
                messages.error(request, f'الكمية غير متوفرة — {s}')
            return redirect('orders:cart')

        with transaction.atomic():
            order = Order.objects.create(
                client=request.user,
                notes=request.POST.get('notes', ''),
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product_unit=item['unit'],
                    quantity=item['quantity'],
                    public_price=item['public_price'],
                    discount_percent=item['discount_percent'],
                    unit_price=item['unit_price'],
                )
        # السلة دي اتحولت لطلب فعليًا، فمفيش داعي تفضل موجودة كسلة فاضية —
        # لو كانت هي السلة النشطة، مفيش أي إعادة إنشاء تلقائية هنا؛ سلة
        # جديدة هتتنشئ بس لو العميل ضاف صنف فعلي تاني.
        if cart.cart_obj is not None:
            cart.cart_obj.delete()
        messages.success(request, f'تم إرسال طلبك رقم #{order.pk} بنجاح!')
        return redirect('orders:order_detail', pk=order.pk)

    return render(request, 'orders/checkout.html', {
        'cart_items': items,
        'total': cart.get_total(),
    })
