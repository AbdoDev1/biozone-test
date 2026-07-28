from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404

from accounts.models import User, ClientProfile
from accounting.models import AccountTransaction
from activity.models import ActivityLog
from activity.services import log_activity
from staff.permissions import perm_required
from staff.excel_utils import build_simple_workbook, workbook_response

CLIENTS_BALANCE_PAGE_SIZE = 30
TRANSACTIONS_PAGE_SIZE = 30


def _clients_with_balance():
    """
    كل العملاء النشطين مع رصيدهم الحالي (موجب = عليه فلوس)، مرتبين من الأكتر
    مديونية للأقل. بنستخدم annotate على مستوى قاعدة البيانات (مش balance_for
    في لوب) عشان الأداء يفضل كويس حتى لو عدد العملاء كبر.
    """
    balances = dict(
        AccountTransaction.objects.values('client_id').annotate(total=Sum('amount')).values_list('client_id', 'total')
    )
    # select_related('account_type') كمان (مش user بس) — عرض المديونيات
    # وتصدير الإكسل بيوصلوا لـ profile.account_type.name لكل عميل، فمن غيرها
    # كانت هتبقى N+1 (استعلام إضافي منفصل لكل عميل نشط).
    profiles = ClientProfile.objects.filter(user__status='ACTIVE').select_related('user', 'account_type')
    rows = []
    for profile in profiles:
        balance = balances.get(profile.user_id) or Decimal('0')
        rows.append({'profile': profile, 'balance': balance, 'balance_abs': abs(balance)})
    rows.sort(key=lambda r: r['balance'], reverse=True)
    return rows


@perm_required('accounting.view_accounttransaction')
def accounting_overview(request):
    rows = _clients_with_balance()

    total_receivable = sum((r['balance'] for r in rows if r['balance'] > 0), Decimal('0'))
    total_credit = sum((-r['balance'] for r in rows if r['balance'] < 0), Decimal('0'))
    debtors_count = sum(1 for r in rows if r['balance'] > 0)

    # جدول "أرصدة العملاء" مرقّم صفحات (بيكبر مع نمو قاعدة العملاء)، لكن
    # القوائم المنسدلة لاختيار عميل في فورمي "تسجيل دفعة/تسوية" لازم تفضل
    # شايفة كل العملاء النشطين مش بس اللي في الصفحة الحالية — فبنستخدم
    # rows الكاملة للـ dropdowns وrows_page بس لعرض الجدول.
    rows_paginator = Paginator(rows, CLIENTS_BALANCE_PAGE_SIZE)
    rows_page = rows_paginator.get_page(request.GET.get('clients_page'))

    transactions_qs = AccountTransaction.objects.select_related(
        'client', 'client__client_profile', 'invoice', 'created_by'
    ).order_by('-created_at')
    transactions_paginator = Paginator(transactions_qs, TRANSACTIONS_PAGE_SIZE)
    transactions_page = transactions_paginator.get_page(request.GET.get('tx_page'))

    return render(request, 'staff/accounting/overview.html', {
        'rows': rows,
        'rows_page': rows_page,
        'total_receivable': total_receivable,
        'total_credit': total_credit,
        'debtors_count': debtors_count,
        'recent_transactions': transactions_page,
        'payment_methods': AccountTransaction.PaymentMethod.choices,
    })


@perm_required('accounting.add_accounttransaction')
def accounting_quick_entry(request):
    if request.method != 'POST':
        return redirect('staff:accounting_overview')

    client_id = request.POST.get('client_id', '').strip()
    kind = request.POST.get('kind', '').strip()
    raw_amount = request.POST.get('amount', '').strip()
    method = request.POST.get('method', '')
    direction = request.POST.get('direction', 'increase')
    note = request.POST.get('note', '').strip()

    profile = get_object_or_404(ClientProfile, user_id=client_id, user__status='ACTIVE')

    try:
        amount = Decimal(raw_amount)
    except (InvalidOperation, TypeError):
        amount = None

    if not amount or amount <= 0:
        messages.error(request, 'يجب أن تكون القيمة رقمًا أكبر من صفر.')
        return redirect('staff:accounting_overview')

    if kind == AccountTransaction.Kind.PAYMENT:
        try:
            txn = AccountTransaction.objects.create(
                client=profile.user,
                kind=AccountTransaction.Kind.PAYMENT,
                amount=-amount,
                method=method,
                note=note,
                created_by=request.user,
            )
        except ValidationError as e:
            messages.error(request, f'المبلغ غير صالح: {"، ".join(e.messages)}')
        else:
            method_label = txn.get_method_display() if method else ''
            summary = f'دفعة بقيمة {amount} ج.م لـ {profile.business_name}'
            if method_label:
                summary += f' ({method_label})'
            log_activity(
                txn,
                ActivityLog.Event.CREATED,
                user=request.user,
                changes_summary=summary,
                note=note,
            )
            messages.success(request, f'تم تسجيل دفعة بقيمة {amount} ج.م لـ {profile.business_name}.')
            from notifications.services import notify
            from notifications.models import Notification
            new_balance = AccountTransaction.balance_for(profile.user)
            if new_balance > 0:
                balance_note = f'رصيدك الحالي بعد الدفعة: {new_balance} ج.م.'
            elif new_balance < 0:
                balance_note = f'أصبح لك رصيد بقيمة {abs(new_balance)} ج.م.'
            else:
                balance_note = 'حسابك مسدّد بالكامل الآن.'
            notify(
                profile.user,
                kind=Notification.Kind.PAYMENT_RECEIVED,
                title='تم تسجيل دفعة على حسابك',
                message=f'تم تسجيل دفعة بقيمة {amount} ج.م. {balance_note}',
                url_name='accounts:dashboard',
            )

    elif kind == AccountTransaction.Kind.ADJUSTMENT:
        if not note:
            messages.error(request, 'يجب إدخال سبب أو ملاحظة مع عملية التسوية.')
            return redirect('staff:accounting_overview')
        signed_amount = amount if direction == 'increase' else -amount
        try:
            txn = AccountTransaction.objects.create(
                client=profile.user,
                kind=AccountTransaction.Kind.ADJUSTMENT,
                amount=signed_amount,
                note=note,
                created_by=request.user,
            )
        except ValidationError as e:
            messages.error(request, f'المبلغ غير صالح: {"، ".join(e.messages)}')
        else:
            direction_label = 'زيادة' if direction == 'increase' else 'تخفيض'
            log_activity(
                txn,
                ActivityLog.Event.CREATED,
                user=request.user,
                changes_summary=f'تسوية ({direction_label}) بقيمة {amount} ج.م لـ {profile.business_name}',
                note=note,
            )
            messages.success(request, f'تم تسجيل تسوية لـ {profile.business_name}.')
    else:
        messages.error(request, 'نوع الحركة غير معروف.')

    return redirect('staff:accounting_overview')


@perm_required('accounting.view_accounttransaction')
def accounting_export(request):
    rows = _clients_with_balance()
    data_rows = [
        [row['profile'].business_name, row['profile'].account_type.name, row['profile'].phone, float(row['balance'])]
        for row in rows
    ]
    wb = build_simple_workbook(
        sheet_title='المديونيات',
        headers=['اسم النشاط', 'نوع الحساب', 'الهاتف', 'الرصيد (ج.م)'],
        rows=data_rows,
        column_width=24,
    )
    return workbook_response(wb, 'biozone_accounts_receivable.xlsx')
