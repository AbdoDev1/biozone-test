"""
views السلة والطلبات — كان ده ملف واحد (views.py، 358 سطر، 21 دالة) فيه 3
مسؤوليات مختلفة، اتقسم لباكدج بنفس الاسم فيه 3 ملفات حسب المرحلة (نفس
نمط orders/urls.py: cart -> checkout -> order):

1. cart.py     — كل عمليات السلة (إضافة/تحديث/حذف/تبديل بين سلال متعددة)
2. checkout.py — تحويل السلة لطلب فعلي
3. order.py    — عمليات الطلب بعد إرساله (تفاصيل، موافقة/رفض تعديل)
4. decorators.py — client_required، مشترك بين التلاتة

orders/urls.py بيستورد بـ `from . import views` وبعدين `views.cart_view`
إلخ — الملف ده بيعيد تصدير كل الدوال عشان ده يفضل شغّال زي ما هو
بالظبط من غير أي تعديل في urls.py.
"""
from .cart import (
    CART_ITEMS_PER_PAGE,
    cart_add,
    cart_badge,
    cart_controls,
    cart_delete,
    cart_minus,
    cart_new,
    cart_plus,
    cart_remove,
    cart_rename,
    cart_switch,
    cart_update,
    cart_view,
)
from .checkout import checkout
from .decorators import client_required
from .order import (
    order_approve_amendment,
    order_detail,
    order_items,
    order_list,
    order_reject_amendment,
    order_reorder,
)

__all__ = [
    'client_required',
    'CART_ITEMS_PER_PAGE',
    'cart_add', 'cart_badge', 'cart_update', 'cart_remove', 'cart_view',
    'cart_plus', 'cart_minus', 'cart_controls', 'cart_new', 'cart_switch',
    'cart_rename', 'cart_delete',
    'checkout',
    'order_detail', 'order_items', 'order_list', 'order_reorder',
    'order_approve_amendment', 'order_reject_amendment',
]
