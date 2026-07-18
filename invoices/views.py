from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404

from accounting.models import AccountTransaction
from .models import Invoice
from .utils import amount_to_arabic_words

ITEMS_PER_PRINT_PAGE = 14  # لو الأصناف زادت عن كده، الفاتورة بتتقسم لصفحات مرقّمة 1/ن، 2/ن...


def _is_staff(user):
    return user.is_authenticated and user.role in ['ADMIN', 'WAREHOUSE']


@login_required
def invoice_print(request, pk):
    """
    عرض الفاتورة بشكل جاهز للطباعة (زرار Print بيستخدم window.print())،
    بنفس شكل الفاتورة الورقية: بيانات المخزن، جدول الأصناف، وملخص الحساب
    (الرصيد السابق/الحالي، صافي الفاتورة، المبلغ بالحروف...).
    الستاف يشوف أي فاتورة، والعميل يشوف بس فواتيره هو.

    لو عدد الأصناف أكتر من ITEMS_PER_PRINT_PAGE، الفاتورة بتتقسم لصفحات
    طباعة منفصلة (كل واحدة مرقّمة "1/ن"، "2/ن"...)، وملخص الحساب/المبلغ
    بالحروف بيظهر في آخر صفحة بس مع باقي الأصناف — مش متكرر في كل صفحة.
    """
    invoice = get_object_or_404(
        Invoice.objects.select_related('order', 'order__client', 'issued_by').prefetch_related('items'),
        pk=pk,
    )

    is_staff = _is_staff(request.user)
    if not is_staff and invoice.order.client_id != request.user.id:
        raise PermissionDenied('مينفعش تشوف فاتورة عميل تاني.')

    # حركة "فاتورة" اللي اتسجّلت تلقائيًا في دفتر حساب العميل لحظة إصدار الفاتورة دي.
    own_transaction = invoice.account_transactions.first()

    if own_transaction is not None:
        # الرصيد الحالي = مجموع كل حركات العميل لغاية (وشاملة) حركة الفاتورة دي بالظبط،
        # عشان الرقم يفضل ثابت في نسخة الفاتورة المطبوعة حتى لو العميل سدّد بعدين.
        current_balance = AccountTransaction.objects.filter(
            client=invoice.order.client,
            created_at__lte=own_transaction.created_at,
        ).aggregate(total=Sum('amount'))['total'] or 0
        previous_balance = current_balance - invoice.total
    else:
        # حالة استثنائية (مفيش حركة مرتبطة بالفاتورة) — نرجع لآخر رصيد معروف كـ fallback.
        current_balance = AccountTransaction.balance_for(invoice.order.client)
        previous_balance = current_balance - invoice.total

    all_items = list(invoice.items.all())
    for idx, item in enumerate(all_items, start=1):
        item.display_index = idx
    public_total = sum((item.public_subtotal for item in all_items), start=0)
    item_pages = [
        all_items[i:i + ITEMS_PER_PRINT_PAGE]
        for i in range(0, len(all_items), ITEMS_PER_PRINT_PAGE)
    ] or [[]]

    context = {
        'invoice': invoice,
        'is_staff': is_staff,
        'item_count': len(all_items),
        'item_pages': item_pages,
        'previous_balance': previous_balance,
        'current_balance': current_balance,
        'public_total': public_total,
        'amount_in_words': amount_to_arabic_words(invoice.total),
    }
    return render(request, 'invoices/print.html', context)
