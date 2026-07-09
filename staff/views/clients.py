from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from accounts.models import User, ClientProfile, BusinessTypeSetting
from orders.models import Order
from invoices.models import Invoice
from accounting.models import AccountTransaction
from staff.permissions import perm_required


# إدارة حسابات العملاء بقت مبنية على صلاحيات دجانجو حقيقية دقيقة (مش قفل
# كامل على الأدمن بس زي الأول): عرض العملاء يحتاج accounts.view_clientprofile،
# الموافقة/الرفض/التعديل يحتاج accounts.change_clientprofile، وتسجيل أي حركة
# مالية (دفعة/تسوية) يحتاج accounting.add_accounttransaction — بالظبط نفس
# الصلاحية المستخدمة في قسم الحسابات، لأنها فعليًا نفس العملية (إنشاء AccountTransaction).
# الأدمن Superuser تلقائيًا فعنده وصول كامل دايمًا، والمخزن لازم ياخد
# الصلاحية المطلوبة صراحةً من شاشة تعديل الموظف.
@perm_required('accounts.view_clientprofile')
def client_list(request):
    pending = ClientProfile.objects.filter(user__status='PENDING').select_related('user')
    active = ClientProfile.objects.filter(user__status='ACTIVE').select_related('user')
    rejected = ClientProfile.objects.filter(user__status='REJECTED').select_related('user')
    return render(request, 'staff/clients/list.html', {
        'pending': pending,
        'active': active,
        'rejected': rejected,
    })


@perm_required('accounts.view_clientprofile')
def client_detail(request, pk):
    profile = get_object_or_404(ClientProfile, pk=pk)
    orders = Order.objects.filter(client=profile.user).prefetch_related('items')
    invoices = Invoice.objects.filter(order__client=profile.user).prefetch_related('items')

    transactions = AccountTransaction.objects.filter(client=profile.user).select_related('invoice')
    balance = AccountTransaction.balance_for(profile.user)

    # كشف حساب: بنحسب الرصيد التراكمي بعد كل حركة بالترتيب الزمني، وبعدين
    # بنعرضها الأحدث فوق (لازم يتساوى مع صفحة العميل نفسها في accounts/dashboard.html)
    running = Decimal('0')
    statement = []
    for tx in transactions:
        running += tx.amount
        statement.append({'tx': tx, 'running_balance': running})
    statement.reverse()

    return render(request, 'staff/clients/detail.html', {
        'profile': profile,
        'orders': orders,
        'invoices': invoices,
        'statement': statement,
        'balance': balance,
        'balance_abs': abs(balance),
        'payment_methods': AccountTransaction.PaymentMethod.choices,
    })


@perm_required('accounting.add_accounttransaction')
def client_add_payment(request, pk):
    profile = get_object_or_404(ClientProfile, pk=pk)

    if request.method == 'POST':
        raw_amount = request.POST.get('amount', '').strip()
        method = request.POST.get('method', '')
        note = request.POST.get('note', '').strip()

        try:
            amount = Decimal(raw_amount)
        except (InvalidOperation, TypeError):
            amount = None

        if not amount or amount <= 0:
            messages.error(request, 'يجب أن تكون قيمة الدفعة رقمًا أكبر من صفر.')
        else:
            try:
                AccountTransaction.objects.create(
                    client=profile.user,
                    kind=AccountTransaction.Kind.PAYMENT,
                    amount=-amount,  # دايمًا سالبة لأنها بتقلل المديونية
                    method=method,
                    note=note,
                    created_by=request.user,
                )
            except ValidationError as e:
                messages.error(request, f'المبلغ غير صالح: {"، ".join(e.messages)}')
            else:
                messages.success(request, f'تم تسجيل دفعة بقيمة {amount} ج.م.')

    return redirect('staff:client_detail', pk=profile.pk)


@perm_required('accounting.add_accounttransaction')
def client_add_adjustment(request, pk):
    profile = get_object_or_404(ClientProfile, pk=pk)

    if request.method == 'POST':
        raw_amount = request.POST.get('amount', '').strip()
        direction = request.POST.get('direction', 'increase')  # increase = بتزود عليه، decrease = بتقلل عليه
        note = request.POST.get('note', '').strip()

        try:
            amount = Decimal(raw_amount)
        except (InvalidOperation, TypeError):
            amount = None

        if not amount or amount <= 0:
            messages.error(request, 'يجب أن تكون قيمة التسوية رقمًا أكبر من صفر.')
        elif not note:
            messages.error(request, 'يجب إدخال سبب أو ملاحظة مع عملية التسوية.')
        else:
            signed_amount = amount if direction == 'increase' else -amount
            try:
                AccountTransaction.objects.create(
                    client=profile.user,
                    kind=AccountTransaction.Kind.ADJUSTMENT,
                    amount=signed_amount,
                    note=note,
                    created_by=request.user,
                )
            except ValidationError as e:
                messages.error(request, f'المبلغ غير صالح: {"، ".join(e.messages)}')
            else:
                messages.success(request, 'تم تسجيل التسوية بنجاح.')

    return redirect('staff:client_detail', pk=profile.pk)


@perm_required('accounts.change_clientprofile')
def client_approve(request, pk):
    profile = get_object_or_404(ClientProfile, pk=pk)
    default_setting = BusinessTypeSetting.get_for(profile.business_type)

    if request.method == 'POST':
        override_choice = request.POST.get('wholesale_override', 'default')
        if override_choice == 'wholesale':
            profile.is_wholesale_override = True
        elif override_choice == 'retail':
            profile.is_wholesale_override = False
        else:
            profile.is_wholesale_override = None

        discount_raw = request.POST.get('custom_discount_percent', '').strip()
        profile.custom_discount_percent = discount_raw or None

        user = profile.user
        user.status = User.Status.ACTIVE
        user.is_active = True
        profile.verified_at = timezone.now()
        user.save()
        profile.save()
        messages.success(request, f'تم تفعيل حساب {profile.business_name}')
        return redirect('staff:clients')

    return render(request, 'staff/clients/approve.html', {
        'profile': profile,
        'default_setting': default_setting,
    })


@perm_required('accounts.change_clientprofile')
def client_reject(request, pk):
    profile = get_object_or_404(ClientProfile, pk=pk)
    user = profile.user
    user.status = User.Status.REJECTED
    user.is_active = False
    user.save()
    messages.error(request, f'تم رفض حساب {profile.business_name}')
    return redirect('staff:clients')
