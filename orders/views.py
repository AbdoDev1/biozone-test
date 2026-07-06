import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from products.models import ProductUnit
from inventory.models import Inventory, StockMovement
from .cart import Cart
from .models import Order, OrderItem, SiteConfig


def cart_add(request, unit_id):
    if not request.user.is_authenticated:
        messages.warning(request, 'يرجى تسجيل الدخول أولاً.')
        return redirect('accounts:login')

    if request.user.role != 'CLIENT' or request.user.status != 'ACTIVE':
        messages.error(request, 'ليست لديك صلاحية للوصول إلى هذه الصفحة.')
        return redirect('store:home')

    cart = Cart(request)
    quantity = int(request.POST.get("quantity", 1))
    cart.add(unit_id, quantity)

    if request.headers.get("HX-Request"):
        unit = get_object_or_404(ProductUnit, pk=unit_id)
        # نرجع الزر المحدّث (أخضر) + نحرك event لتحديث الـ badge
        response = render(request, "orders/partials/add_button.html", {
            "unit": unit,
            "in_cart": True,
        })
        response['HX-Trigger'] = json.dumps({'cartUpdated': {'count': len(cart)}})
        return response

    return redirect(request.POST.get("next", "store:home"))


def cart_badge(request):
    cart = Cart(request)
    return render(request, 'orders/partials/cart_badge.html', {'count': len(cart)})


def cart_update(request, unit_id):
    cart = Cart(request)
    quantity = int(request.POST.get("quantity", 1))
    cart.set_quantity(unit_id, quantity)
    if request.headers.get("HX-Request"):
        return cart_controls(request, unit_id)
    return redirect("orders:cart")


def cart_remove(request, unit_id):
    cart = Cart(request)
    cart.remove(unit_id)
    if request.headers.get("HX-Request"):
        return cart_controls(request, unit_id)
    return redirect("orders:cart")


def cart_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
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


def cart_plus(request, unit_id):
    cart = Cart(request)
    cart.increase(unit_id)
    return cart_controls(request, unit_id)


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


@login_required
def checkout(request):
    if request.user.role != 'CLIENT' or request.user.status != 'ACTIVE':
        return redirect('store:home')

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
        with transaction.atomic():
            product_ids = [item['unit'].product_id for item in items]
            locked_inventories = {
                inv.product_id: inv
                for inv in Inventory.objects.select_for_update().filter(product_id__in=product_ids)
            }

            # الرصيد الحقيقي محفوظ بالقطعة دايمًا على مستوى المنتج (مش الوحدة).
            # بنحوّل item['quantity'] (بوحدة الطلب: كرتونة للجملة أو قطعة
            # للقطاعي) لـ stock_qty بالقطعة عن طريق qty_in_small قبل أي فحص أو حجز.
            shortages = []
            for item in items:
                unit = item['unit']
                stock_qty = item['quantity'] * unit.qty_in_small
                item['stock_qty'] = stock_qty
                inv = locked_inventories.get(unit.product_id)
                available = inv.available if inv else 0
                if stock_qty > available:
                    shortages.append(f"{unit.product.display_name} ({unit.name}): متاح {available // unit.qty_in_small} {unit.name} فقط")

            if shortages:
                for s in shortages:
                    messages.error(request, f'الكمية غير متوفرة — {s}')
                return redirect('orders:cart')

            order = Order.objects.create(
                client=request.user,
                notes=request.POST.get('notes', ''),
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product_unit=item['unit'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                )
                inv = locked_inventories[item['unit'].product_id]
                StockMovement.objects.create(
                    inventory=inv,
                    unit=item['unit'],
                    movement_type=StockMovement.MovementType.RESERVE,
                    quantity=item['quantity'],
                    note=f'حجز لطلب #{order.pk}',
                    created_by=request.user,
                )
        cart.clear()
        messages.success(request, f'تم إرسال طلبك رقم #{order.pk} بنجاح!')
        return redirect('orders:order_detail', pk=order.pk)

    return render(request, 'orders/checkout.html', {
        'cart_items': items,
        'total': cart.get_total(),
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, client=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def order_list(request):
    if request.user.role != 'CLIENT':
        return redirect('store:home')
    orders = Order.objects.filter(client=request.user)
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_approve_amendment(request, pk):
    order = get_object_or_404(Order, pk=pk, client=request.user)
    if order.status != Order.Status.NEEDS_APPROVAL:
        messages.error(request, 'هذا الطلب ليس بانتظار موافقتك.')
        return redirect('orders:order_detail', pk=order.pk)
    order.client_approve_amendment(actor=request.user)
    messages.success(request, f'تمت الموافقة على التعديل، وأصبح الطلب #{order.pk} مؤكدًا الآن.')
    return redirect('orders:order_detail', pk=order.pk)


@login_required
def order_reject_amendment(request, pk):
    order = get_object_or_404(Order, pk=pk, client=request.user)
    if order.status != Order.Status.NEEDS_APPROVAL:
        messages.error(request, 'هذا الطلب ليس بانتظار موافقتك.')
        return redirect('orders:order_detail', pk=order.pk)
    order.client_reject_amendment(actor=request.user)
    messages.success(request, f'تم رفض التعديل، وتم رفض الطلب #{order.pk}.')
    return redirect('orders:order_detail', pk=order.pk)
