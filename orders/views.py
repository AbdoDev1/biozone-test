import json
from functools import wraps
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from products.models import ProductUnit
from inventory.models import Inventory
from .cart import Cart
from .models import Order, OrderItem, SiteConfig


def client_required(view_func):
    """
    بوابة موحّدة لكل عمليات السلة والطلبات: لازم المستخدم يكون مسجّل دخول،
    ودوره CLIENT، وحالته ACTIVE. استخدام decorator واحد بدل تكرار نفس
    الفحص يدويًا في كل دالة يمنع نسيانه بالغلط في دالة جديدة مستقبلًا
    (زي ما حصل مع cart_update/remove/plus/minus).
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'CLIENT' or request.user.status != 'ACTIVE':
            messages.error(request, 'ليست لديك صلاحية للوصول إلى هذه الصفحة.')
            return redirect('store:home')
        return view_func(request, *args, **kwargs)
    return wrapper


@client_required
@require_POST
def cart_add(request, unit_id):
    unit = get_object_or_404(ProductUnit, pk=unit_id)
    cart = Cart(request)
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    added = cart.add(unit_id, quantity)

    if request.headers.get("HX-Request"):
        if not added:
            # الصنف غير متاح حاليًا (نفدت الكمية، أو الوحدة مش مسموحة لنوع
            # حساب العميل) — نرجّع الزر بحالته الأصلية بدل ما نضيفه فعليًا.
            return render(request, "orders/partials/add_button.html", {
                "unit": unit,
                "in_cart": False,
                "unavailable": True,
            })
        # نرجع الزر المحدّث (أخضر) + نحرك event لتحديث الـ badge
        response = render(request, "orders/partials/add_button.html", {
            "unit": unit,
            "in_cart": True,
        })
        response['HX-Trigger'] = json.dumps({'cartUpdated': {'count': len(cart)}})
        return response

    if not added:
        messages.error(request, 'هذا الصنف غير متوفر حاليًا في المخزون.')
    return redirect(request.POST.get("next", "store:home"))


def cart_badge(request):
    cart = Cart(request)
    return render(request, 'orders/partials/cart_badge.html', {'count': len(cart)})


@client_required
@require_POST
def cart_update(request, unit_id):
    cart = Cart(request)
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    added = cart.set_quantity(unit_id, quantity)
    if not added and not request.headers.get("HX-Request"):
        messages.error(request, 'هذا الصنف غير متوفر حاليًا في المخزون.')
    if request.headers.get("HX-Request"):
        return cart_controls(request, unit_id)
    return redirect("orders:cart")


@client_required
@require_POST
def cart_remove(request, unit_id):
    cart = Cart(request)
    cart.remove(unit_id)
    if request.headers.get("HX-Request"):
        return cart_controls(request, unit_id)
    return redirect("orders:cart")


@client_required
def cart_view(request):
    cart = Cart(request)
    config = SiteConfig.get_solo()
    total = cart.get_total()
    remaining = config.min_order_amount - total if config.min_order_amount else 0
    return render(request, 'orders/cart.html', {
        'cart_items': cart.get_items(),
        'total': total,
        'min_order_amount': config.min_order_amount,
        'remaining_to_min': remaining if remaining > 0 else 0,
        'below_min': remaining > 0,
    })


@client_required
@require_POST
def cart_plus(request, unit_id):
    cart = Cart(request)
    cart.increase(unit_id)
    return cart_controls(request, unit_id)


@client_required
@require_POST
def cart_minus(request, unit_id):
    cart = Cart(request)
    cart.decrease(unit_id)
    return cart_controls(request, unit_id)


def cart_controls(request, unit_id):
    cart = Cart(request)
    entry = cart.cart.get(str(unit_id), {})
    quantity = entry.get("quantity", 0)
    response = render(request, "orders/partials/cart_controls.html", {
        "unit_id": unit_id,
        "quantity": quantity,
    })
    response['HX-Trigger'] = json.dumps({'cartUpdated': {'count': len(cart)}})
    return response


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
        cart.clear()
        messages.success(request, f'تم إرسال طلبك رقم #{order.pk} بنجاح!')
        return redirect('orders:order_detail', pk=order.pk)

    return render(request, 'orders/checkout.html', {
        'cart_items': items,
        'total': cart.get_total(),
    })


@client_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product_unit__product'),
        pk=pk, client=request.user,
    )
    return render(request, 'orders/order_detail.html', {'order': order})


@client_required
@require_POST
def order_cancel(request, pk):
    """
    العميل بيلغي طلبه بنفسه — متاح بس لسه الطلب "في الانتظار" (لسه محدش
    من المخزن فتحه). لو الطلب دخل أي مرحلة تانية، بنرفض ونوجّه العميل
    للتواصل المباشر مع المخزن.
    """
    order = get_object_or_404(Order, pk=pk, client=request.user)
    try:
        order.client_cancel(actor=request.user)
        messages.success(request, f'تم إلغاء طلبك #{order.pk}.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('orders:order_detail', pk=order.pk)


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
