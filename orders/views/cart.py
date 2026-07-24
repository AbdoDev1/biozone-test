import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import ProductUnit

from ..cart import Cart
from ..models import Cart as CartModel, SiteConfig
from .decorators import client_required

__all__ = [
    'CART_ITEMS_PER_PAGE',
    'cart_add', 'cart_badge', 'cart_update', 'cart_remove', 'cart_view',
    'cart_plus', 'cart_minus', 'cart_controls', 'cart_new', 'cart_switch',
    'cart_rename', 'cart_delete',
]

CART_ITEMS_PER_PAGE = 15  # عدد أصناف السلة اللي تتعرض في الصفحة الواحدة


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
        # نرجع الـ stepper (-/الكمية الفعلية/+) بدل ما نرجّع فورم "أضف" تاني —
        # كان بيرجع add_button.html بـ in_cart=True لكن خانة الكمية فيه كانت
        # قيمتها الافتراضية 1 دايمًا (مش الكمية الفعلية اللي بقت في السلة)،
        # فالعميل كان بيكتب رقم (مثلاً 5)، يضيف، والرقم يرجع 1 تاني وكأن
        # حاجة اتلغت — مع إن الإضافة فعليًا نجحت والسلة اتحدّثت. الـ stepper
        # ده هو نفسه المستخدم في صفحة تفاصيل المنتج، بيعرض الكمية الحقيقية
        # وبيفضل واضح للعميل قد إيه في السلة فعليًا.
        entry_quantity = cart.get_quantity(unit_id)
        response = render(request, "orders/partials/cart_controls.html", {
            "unit_id": unit_id,
            "quantity": entry_quantity,
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
    """
    صفحة السلة — بقت صفحة واحدة فيها كل سلال العميل (لو أكتر من واحدة) كـ
    تابات، بدل ما تكون "السلة" و"سلالي" صفحتين منفصلتين يتنقل بينهم (كان
    ده مشتت). كل تاب بيمثّل سلة، والتاب النشط هو اللي بيعرض أصنافه تحت،
    وهو نفسه اللي أي "أضف للسلة" جديد من المتجر بيروحله.
    """
    config = SiteConfig.get_solo()
    carts = list(
        CartModel.objects.filter(client=request.user)
        .prefetch_related('items')
        .order_by('created_at')
    )
    active_cart_obj = next((c for c in carts if c.is_active), None)
    if active_cart_obj is None and carts:
        # حالة نادرة (متوقعة نظريًا بس مش عمليًا) — لو مفيش أي سلة معلّمة
        # نشطة رغم وجود سلال، نفعّل أول واحدة عشان الصفحة تفضل متسقة.
        active_cart_obj = carts[0]
        active_cart_obj.is_active = True
        active_cart_obj.save(update_fields=['is_active'])

    cart = Cart(request)  # بيقرا نفس السلة النشطة (active_cart_obj) من غير ما ينشئ حاجة
    total = cart.get_total()
    remaining = config.min_order_amount - total if config.min_order_amount else 0

    # لو الطلبية فيها عدد كبير من الأصناف (مثلاً 30 صنف)، الجدول كان بيطول
    # من غير أي ترقيم أو تقسيم لصفحات. الإجمالي (total) بيتحسب على كل
    # الأصناف زي ما هو (مش بس صفحة العرض الحالية).
    all_items = cart.get_items()
    paginator = Paginator(all_items, CART_ITEMS_PER_PAGE)
    items_page = paginator.get_page(request.GET.get('page'))

    return render(request, 'orders/cart.html', {
        'carts': carts,
        'active_cart': active_cart_obj,
        'cart_items': items_page,
        'cart_items_count': len(all_items),
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
    quantity = cart.get_quantity(unit_id)
    response = render(request, "orders/partials/cart_controls.html", {
        "unit_id": unit_id,
        "quantity": quantity,
    })
    response['HX-Trigger'] = json.dumps({'cartUpdated': {'count': len(cart)}})
    return response


@client_required
@require_POST
def cart_new(request):
    name = request.POST.get('name', '').strip()
    CartModel.objects.create(client=request.user, name=name, is_active=True)
    messages.success(request, 'تم إنشاء طلبية جديدة، وبقت هي النشطة دلوقتي.')
    return redirect('orders:cart')


@client_required
@require_POST
def cart_switch(request, cart_id):
    cart_obj = get_object_or_404(CartModel, pk=cart_id, client=request.user)
    cart_obj.is_active = True
    cart_obj.save()
    return redirect('orders:cart')


@client_required
@require_POST
def cart_rename(request, cart_id):
    cart_obj = get_object_or_404(CartModel, pk=cart_id, client=request.user)
    cart_obj.name = request.POST.get('name', '').strip()
    cart_obj.save(update_fields=['name'])
    return redirect('orders:cart')


@client_required
@require_POST
def cart_delete(request, cart_id):
    cart_obj = get_object_or_404(CartModel, pk=cart_id, client=request.user)
    cart_obj.delete()
    # ملاحظًا: من غير أي إعادة إنشاء تلقائية لسلة فاضية بديلة — لو دي كانت
    # آخر سلة عند العميل، يفضل مفيش عنده أي سلة مفتوحة خالص لحد ما يضيف
    # صنف فعلي تاني (orders.cart.Cart.add بينشئها وقتها لوحده).
    messages.success(request, 'تم حذف الطلبية.')
    return redirect('orders:cart')
