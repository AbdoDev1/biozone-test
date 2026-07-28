from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from accounts.models import AccountType
from activity.models import ActivityLog
from activity.services import diff_summary, log_activity, log_created
from products.models import Product, ProductUnit, UnitDiscount
from products.matching import normalize_name
from staff.permissions import admin_required

_TRACKED_ACCOUNT_TYPE_FIELDS = ['name', 'default_unit_size', 'is_active']

DISCOUNTS_PAGE_SIZE = 20


# =====================================================================
# أنواع الحسابات — إضافة/تعديل نوع جديد (جملة/صيدلية/مستشفى/... إلخ).
# مقصورة على الأدمن حصريًا (نفس منطق admin_required المستخدم في شاشة
# إدارة الموظفين) — محدش غير الأدمن يقدر يضيف نوع حساب جديد أو يغيّر
# الوحدة الافتراضية لنوع موجود، لأن ده بيأثر على تسعير كل عملاء النوع ده.
# =====================================================================

@admin_required
def account_type_list(request):
    account_types = AccountType.objects.all()
    return render(request, 'staff/account_types/list.html', {
        'account_types': account_types,
    })


@admin_required
def account_type_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        default_unit_size = request.POST.get('default_unit_size', AccountType.UnitSize.SMALL)
        is_active = bool(request.POST.get('is_active'))

        if not name:
            messages.error(request, 'يجب إدخال اسم نوع الحساب.')
        elif AccountType.objects.filter(name=name).exists():
            messages.error(request, f'يوجد نوع حساب بنفس الاسم "{name}" بالفعل.')
        else:
            account_type = AccountType.objects.create(
                name=name,
                default_unit_size=default_unit_size,
                is_active=is_active,
            )
            log_created(account_type, user=request.user)
            messages.success(request, f'تم إضافة نوع الحساب "{name}" بنجاح.')
            return redirect('staff:account_types')

    return render(request, 'staff/account_types/form.html', {
        'title': 'إضافة نوع حساب جديد',
        'is_edit': False,
        'account_type': None,
        'unit_sizes': AccountType.UnitSize.choices,
    })


@admin_required
def account_type_edit(request, pk):
    account_type = get_object_or_404(AccountType, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        default_unit_size = request.POST.get('default_unit_size', AccountType.UnitSize.SMALL)
        is_active = bool(request.POST.get('is_active'))

        if not name:
            messages.error(request, 'يجب إدخال اسم نوع الحساب.')
        elif AccountType.objects.exclude(pk=account_type.pk).filter(name=name).exists():
            messages.error(request, f'يوجد نوع حساب بنفس الاسم "{name}" بالفعل.')
        else:
            old_values = {f: getattr(account_type, f) for f in _TRACKED_ACCOUNT_TYPE_FIELDS}
            account_type.name = name
            account_type.default_unit_size = default_unit_size
            account_type.is_active = is_active
            account_type.save()
            summary = diff_summary(old_values, account_type, _TRACKED_ACCOUNT_TYPE_FIELDS)
            if summary:
                log_activity(account_type, ActivityLog.Event.UPDATED, user=request.user, changes_summary=summary)
            messages.success(request, f'تم تعديل نوع الحساب "{name}" بنجاح.')
            return redirect('staff:account_types')

    return render(request, 'staff/account_types/form.html', {
        'title': f'تعديل: {account_type.name}',
        'is_edit': True,
        'account_type': account_type,
        'unit_sizes': AccountType.UnitSize.choices,
    })


# =====================================================================
# قائمة الخصومات: لكل نوع حساب، الأدمن بيحدد نسبة الخصم على مستوى كل
# صنف/وحدة على حدة. سعر الجمهور (unit_price) ثابت دايمًا، والخصم هنا
# (لو موجود) هو اللي بيحدد سعر القطعة الفعلي لهذا النوع. عدم وجود صف
# لصنف معيّن = بدون خصم (سعر الجمهور كامل).
# =====================================================================

@admin_required
def account_type_discounts(request, pk):
    account_type = get_object_or_404(AccountType, pk=pk)
    search_q = request.GET.get('q', '').strip()

    products_qs = Product.objects.filter(is_active=True).select_related('category').prefetch_related(
        Prefetch(
            'units',
            queryset=ProductUnit.objects.order_by('qty_in_small').prefetch_related(
                Prefetch(
                    'discounts',
                    queryset=UnitDiscount.objects.filter(account_type=account_type),
                    to_attr='type_discounts',
                ),
            ),
        ),
    ).order_by('name_ar')

    if search_q:
        normalized_q = normalize_name(search_q)
        products_qs = products_qs.filter(
            Q(name_ar__icontains=search_q) | Q(name_key__icontains=normalized_q)
        )

    if request.method == 'POST':
        changed_units = []  # ملخص التغييرات الفعلية بس، عشان نسجلها كنشاط واحد مجمّع بعد الحفظ

        with transaction.atomic():
            for key, raw_value in request.POST.items():
                if not key.startswith('discount_'):
                    continue
                unit_id = key.split('_', 1)[1]
                value = raw_value.strip()

                try:
                    unit = ProductUnit.objects.select_related('product').get(pk=unit_id)
                except (ProductUnit.DoesNotExist, ValueError):
                    continue

                existing = UnitDiscount.objects.filter(unit_id=unit_id, account_type=account_type).first()
                old_percent = existing.discount_percent if existing else None
                unit_label = f'{unit.product.name_ar} ({unit.get_size_display()})'

                # الخصم بيتحدد يدويًا بس على الوحدة الصغرى، أو على الكبرى لو
                # المنتج مالوش وحدة صغرى أصلًا. أي وحدة كبرى معاها صغرى، سعرها
                # بيتحسب تلقائيًا (مش قابلة للتعديل يدويًا) — فبنشيل أي صف قديم
                # كان مسجّل ليها قبل هذا التعديل عشان مايفضلش معلّق بدون فايدة.
                has_small_sibling = unit.size == ProductUnit.Size.LARGE and unit.product.units.filter(
                    size=ProductUnit.Size.SMALL,
                ).exists()
                if has_small_sibling:
                    if existing:
                        UnitDiscount.objects.filter(unit_id=unit_id, account_type=account_type).delete()
                        changed_units.append(f'{unit_label}: {old_percent}% → بدون خصم (تلقائي)')
                    continue

                if value == '':
                    if existing:
                        UnitDiscount.objects.filter(unit_id=unit_id, account_type=account_type).delete()
                        changed_units.append(f'{unit_label}: {old_percent}% → بدون خصم')
                    continue

                try:
                    discount_percent = Decimal(value)
                except InvalidOperation:
                    messages.warning(request, f'قيمة خصم غير صالحة تم تجاهلها (وحدة #{unit_id}).')
                    continue

                if discount_percent < 0 or discount_percent > 100:
                    messages.warning(request, f'نسبة الخصم يجب أن تكون بين 0 و100 (وحدة #{unit_id}) — تم تجاهلها.')
                    continue

                if old_percent != discount_percent:
                    old_label = f'{old_percent}%' if old_percent is not None else 'بدون خصم'
                    changed_units.append(f'{unit_label}: {old_label} → {discount_percent}%')

                UnitDiscount.objects.update_or_create(
                    unit_id=unit_id,
                    account_type=account_type,
                    defaults={'discount_percent': discount_percent},
                )

        if changed_units:
            log_activity(
                account_type, ActivityLog.Event.UPDATED,
                user=request.user, changes_summary='، '.join(changed_units),
            )
        messages.success(request, f'تم حفظ قائمة الخصومات لنوع الحساب "{account_type.name}".')
        base_url = reverse('staff:account_type_discounts', kwargs={'pk': account_type.pk})
        params = {}
        if search_q:
            params['q'] = search_q
        if request.GET.get('page'):
            params['page'] = request.GET['page']
        if params:
            base_url = f'{base_url}?{urlencode(params)}'
        return redirect(base_url)

    paginator = Paginator(products_qs, DISCOUNTS_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    for product in page_obj:
        sizes_present = {u.size for u in product.units.all()}
        for unit in product.units.all():
            # الوحدة قابلة للتعديل اليدوي إلا لو هي كبرى ومعاها صغرى لنفس
            # المنتج — في الحالة دي سعرها بيتحسب تلقائيًا من الصغرى (شوف
            # ProductUnit.get_pricing_breakdown_for_account_type).
            unit.is_editable = not (
                unit.size == ProductUnit.Size.LARGE and ProductUnit.Size.SMALL in sizes_present
            )
            unit.current_discount = next(
                (d.discount_percent for d in getattr(unit, 'type_discounts', [])), None,
            )
            unit.price_after_discount = unit.get_price_for_account_type(account_type)

    return render(request, 'staff/account_types/discounts.html', {
        'account_type': account_type,
        'products': page_obj,
        'page_obj': page_obj,
        'search_q': search_q,
    })
