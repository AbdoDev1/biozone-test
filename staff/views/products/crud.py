"""
عمليات CRUD الأساسية للمنتجات (عرض/إضافة/تعديل/حذف). منطق استيراد/تصدير
إكسل منفصل في import_export.py — راجع staff/views/products/__init__.py
للتوثيق الكامل لسبب الفصل.
"""

from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q, F, Value, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_POST

from products.models import Product, Category, ProductUnit
from products.forms import ProductForm, ProductUnitFormSet
from products.pricing import autofill_small_unit_price
from products.matching import normalize_name
from products.services import stock_setup
from staff.permissions import perm_required
from staff.utils import list_qs, url_with_qs, redirect_with_qs
from django.contrib.contenttypes.models import ContentType
from activity.models import ActivityLog
from activity.services import log_activity, diff_summary, delete_activity_logs_for
from tags.services import tags_for, tags_for_many

# الحقول اللي بتتراقب في تايم لاين النشاط (مرحلة 2) — نفس الحقول الأساسية
# الظاهرة في تاب "بيانات المنتج"، مش كل حقول الموديل (مفيش داعي نسجّل
# تغييرات على حقول داخلية زي updated_at).
PRODUCT_TRACKED_FIELDS = ['name_ar', 'name_en', 'category', 'barcode', 'manufacturer', 'size', 'is_active']

STAFF_LIST_PAGE_SIZE = 30


# مرحلة 3 (ترقية الجداول) — أعمدة الترتيب المسموحة وربطها بحقل/تعبير
# فعلي على مستوى الاستعلام. 'price'/'stock' مش حقول مباشرة على Product،
# فمحتاجين annotate تحتهم (شوف small_unit_price/available_qty تحت) —
# الترتيب في بايثون على product.units.all()|first مايصحّش لأنه بيترتب
# صفحة واحدة بس بعد التقطيع (pagination)، مش الاستعلام الكامل.
PRODUCT_SORT_FIELDS = {
    'name': 'name_ar',
    'category': 'category__name',
    'price': 'small_unit_price',
    'stock': 'available_qty',
    'status': 'is_active',
}


@perm_required('products.view_product')
def product_list(request):
    products = Product.objects.select_related('category', 'inventory').prefetch_related('units').all()
    categories = Category.objects.filter(is_active=True)
    selected_category = request.GET.get('category', '')
    # .strip() هي أهم سطر هنا: من غيرها، مسافة زيادة قبل/بعد النص المكتوب
    # (تاب على الشيفت بالغلط، أو نسخ/لصق) كانت بتخلي name_ar__icontains
    # مايلاقيش أي نتيجة رغم إن الصنف موجود فعلاً بنفس الاسم بالظبط.
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')  # '' / 'active' / 'inactive'
    stock_filter = request.GET.get('stock', '')  # '' / 'low' / 'out'
    group_by_category = request.GET.get('group') == '1'
    sort = request.GET.get('sort', 'name')
    if sort not in PRODUCT_SORT_FIELDS:
        sort = 'name'
    direction = request.GET.get('dir', 'asc')
    if direction not in ('asc', 'desc'):
        direction = 'asc'

    if selected_category:
        products = products.filter(category__slug=selected_category)
    if search_q:
        # البحث بقى بيغطي: اسم الصنف (عربي/إنجليزي)، النسخة المُطبَّعة من
        # الاسم (name_key — بتتحمّل فراغات إضافية جوه الاسم نفسه وفروق
        # الحروف المتشابهة زي ا/أ/إ)، الباركود، وكود الصنف الداخلي (BZ-...).
        # قبل كده كان بس name_ar__icontains، فمسح باركود في خانة البحث
        # (بالاسكانر) ما كانش بيرجّع أي نتيجة خالص.
        normalized_q = normalize_name(search_q)
        products = products.filter(
            Q(name_ar__icontains=search_q)
            | Q(name_key__icontains=normalized_q)
            | Q(name_en__icontains=search_q)
            | Q(barcode__iexact=search_q)
            | Q(code__iexact=search_q)
        )
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    if stock_filter == 'low':
        # نفس شرط Inventory.is_low بس على مستوى الاستعلام — راجع
        # InventoryQuerySet.low_stock() في inventory/models.py لنفس المنطق.
        products = products.filter(inventory__quantity__lte=F('inventory__reserved') + F('inventory__min_quantity'))
    elif stock_filter == 'out':
        products = products.filter(inventory__quantity__lte=F('inventory__reserved'))

    # سعر أصغر وحدة (القطعة عادةً، أو الوحدة الوحيدة لو المنتج بوحدة كبرى
    # بس) — بنفس منطق Product.smallest_unit، لكن كـ Subquery عشان يترتب
    # على مستوى قاعدة البيانات، مش بس يُعرض. متاح كترتيب فوري (بدون query
    # إضافي لكل صف) لأن الوحدات متعمول لها prefetch_related فوق أصلاً.
    smallest_unit_price = Subquery(
        ProductUnit.objects.filter(product=OuterRef('pk')).order_by('qty_in_small').values('unit_price')[:1]
    )
    products = products.annotate(
        small_unit_price=smallest_unit_price,
        available_qty=Coalesce(F('inventory__quantity') - F('inventory__reserved'), Value(0)),
    )

    order_field = PRODUCT_SORT_FIELDS[sort]
    order = order_field if direction == 'asc' else f'-{order_field}'
    if group_by_category and sort != 'category':
        # لو التجميع حسب القسم مفعّل، القسم هو المفتاح الأساسي للترتيب
        # (عشان صفوف نفس القسم تتجاور)، والترتيب المطلوب من المستخدم بيبقى
        # ثانوي جوه كل قسم.
        ordering = ['category__name', order, 'pk']
    else:
        ordering = [order, 'pk']  # 'pk' كترتيب ثابت ثانوي يمنع تغيّر ترتيب الصفوف بين الصفحات لو فيه تعادل
    products = products.order_by(*ordering)

    paginator = Paginator(products, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    # وسم كل منتج في الصفحة الحالية باستعلام واحد بدل ما نستدعي tags_for
    # لكل صف على حدة (N+1) — نفس أسلوب staff.views.orders.order_list.
    tags_by_product_id = tags_for_many(Product, [p.pk for p in page_obj])
    for product in page_obj:
        product.tag_list = tags_by_product_id.get(product.pk, [])

    return render(request, 'staff/products/list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'total_products': paginator.count,
        'categories': categories,
        'selected_category': selected_category,
        'search_q': search_q,
        'status_filter': status_filter,
        'stock_filter': stock_filter,
        'group_by_category': group_by_category,
        'sort': sort,
        'dir': direction,
        'page_ids': [p.pk for p in page_obj],
    })


@perm_required('products.change_product')
@require_POST
def product_bulk_action(request):
    """
    تفعيل/تعطيل جماعي لعدة منتجات محددة من قائمة المنتجات (معيار قبول
    مرحلة 3). بنستخدم .update() (تحديث واحد بالقاعدة) مش حفظ كل منتج
    لوحده، لأن مفيش أي منطق إضافي في Product.save() مربوط بـ is_active
    حاليًا (لا signals ولا side effects) — لو ده تغيّر مستقبلًا، الكود ده
    محتاج يتحول لـ loop بيستخدم .save() بدل .update().
    """
    ids = [pk for pk in request.POST.getlist('product_ids') if pk.isdigit()]
    action = request.POST.get('bulk_action')
    if not ids:
        messages.warning(request, 'لازم تحدد صنف واحد على الأقل قبل تنفيذ الإجراء.')
        return redirect_with_qs(request, 'staff:product_list')
    if action not in ('activate', 'deactivate'):
        messages.error(request, 'إجراء غير معروف.')
        return redirect_with_qs(request, 'staff:product_list')

    new_status = action == 'activate'
    to_update = Product.objects.filter(pk__in=ids).exclude(is_active=new_status)
    changed_products = list(to_update)
    updated_count = to_update.update(is_active=new_status)

    status_label = 'نشط' if new_status else 'معطل'
    old_status_label = 'معطل' if new_status else 'نشط'
    for product in changed_products:
        log_activity(
            product, ActivityLog.Event.UPDATED, user=request.user,
            changes_summary=f'الحالة: {old_status_label} → {status_label} (إجراء جماعي)',
        )

    if updated_count:
        action_label = 'تفعيل' if new_status else 'تعطيل'
        messages.success(request, f'تم {action_label} {updated_count} منتج.')
    else:
        messages.info(request, 'الأصناف المحددة كانت بالفعل بنفس الحالة المطلوبة.')
    return redirect_with_qs(request, 'staff:product_list')


@perm_required('products.change_product')
@require_POST
def product_quick_update_price(request, unit_pk):
    """
    تعديل سعر وحدة واحدة (Quick Edit inline — مرحلة 3) من صف الجدول
    مباشرة من غير فتح صفحة تعديل المنتج الكاملة. بيرجّع partial واحد
    (الخلية بس) عشان htmx يستبدلها في مكانها (hx-target/hx-swap في
    التمبلت) من غير أي reload لباقي الصفحة.
    """
    unit = get_object_or_404(ProductUnit, pk=unit_pk)
    raw_price = (request.POST.get('unit_price') or '').strip()
    error = None
    try:
        new_price = Decimal(raw_price)
        if new_price < 0:
            raise InvalidOperation
    except InvalidOperation:
        error = 'قيمة غير صحيحة'
        new_price = unit.unit_price
    else:
        old_price = unit.unit_price
        if old_price != new_price:
            unit.unit_price = new_price
            unit.save(update_fields=['unit_price'])
            log_activity(
                unit.product, ActivityLog.Event.UPDATED, user=request.user,
                changes_summary=f'سعر {unit.name}: {old_price} → {new_price} (تعديل سريع)',
            )

    return render(request, 'staff/products/partials/price_cell.html', {
        'unit': unit,
        'error': error,
    })


@perm_required('products.add_product')
def product_add(request):
    if request.method == 'POST':
        # لو سعر القطعة (الوحدة الصغرى) سايبينه فاضي وفي كرتونة (وحدة كبرى)
        # بسعر وكمية، بنحسب سعر القطعة تلقائيًا قبل ما نبني الفورم/الفورمست
        post_data = autofill_small_unit_price(request.POST)
        form = ProductForm(post_data, request.FILES)
        formset = ProductUnitFormSet(post_data, instance=Product())
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    product = form.save()
                    formset.instance = product
                    units = formset.save()  # بيحفظ كل الوحدات الجديدة (النماذج اللي اتملت واتصدّق عليها)
            except IntegrityError:
                messages.error(
                    request,
                    'حدث تعارض غير متوقع أثناء حفظ وحدات المنتج (مثلاً وحدتين بنفس '
                    'الحجم) — يرجى مراجعة الوحدات وإعادة المحاولة. لو المشكلة '
                    'استمرت، يرجى إبلاغ فريق التطوير بخطوات إعادة حدوثها بالتفصيل.'
                )
                return render(request, 'staff/products/form.html', {
                    'form': form, 'formset': formset,
                    'title': 'إضافة منتج جديد', 'is_edit': False,
                    'back_url': url_with_qs(request, 'staff:product_list'),
                })

            stock_setup.apply_initial_stock(
                product, formset, request.user, note='كمية ابتدائية عند إضافة المنتج',
            )
            log_activity(product, ActivityLog.Event.CREATED, user=request.user)
            messages.success(request, f'تم إضافة المنتج "{product.name_ar}" بنجاح.')
            return redirect_with_qs(request, 'staff:product_list')
    else:
        form = ProductForm()
        formset = ProductUnitFormSet(instance=Product())
    return render(request, 'staff/products/form.html', {
        'form': form,
        'formset': formset,
        'title': 'إضافة منتج جديد',
        'is_edit': False,
        'back_url': url_with_qs(request, 'staff:product_list'),
    })


def _product_activity_count(product):
    return ActivityLog.objects.filter(
        content_type=ContentType.objects.get_for_model(Product), object_id=product.pk,
    ).count()


def _product_tags_count(product):
    return tags_for(product).count()


def _product_related_orders(product, limit=8):
    """
    آخر الطلبات اللي فيها صنف من هذا المنتج (أي وحدة منه) — Related
    Documents (مرحلة 2). بنعدي على OrderItem مش على Order مباشرة لأن
    الربط الفعلي بالمنتج عن طريق ProductUnit، وبنستخدم distinct عشان
    الطلب اللي فيه أكتر من وحدة لنفس المنتج (قطعة وكرتونة مثلاً) ميتكررش.
    """
    from orders.models import OrderItem
    order_ids = (
        OrderItem.objects
        .filter(product_unit__product=product)
        .order_by('-order__created_at')
        .values_list('order_id', flat=True)
        .distinct()[:limit]
    )
    from orders.models import Order
    return Order.objects.filter(pk__in=list(order_ids)).order_by('-created_at')


# الحقول اللي بتتراقب على كل وحدة (ProductUnit) — السعر مش موجود على
# Product نفسه (شوف PRODUCT_TRACKED_FIELDS فوق)، فمحتاج تتبع منفصل هنا
# وإلا تغيير السعر مايتسجلش خالص في تايم لاين النشاط.
UNIT_TRACKED_FIELDS = ['unit_price', 'cost_price']
UNIT_FIELD_LABELS = {'unit_price': 'سعر الجمهور', 'cost_price': 'سعر التكلفة'}


def _snapshot_unit_prices(product):
    """قاموس {unit_id: {'name': ..., field: value, ...}} لأسعار وأسماء الوحدات *الحالية في القاعدة* قبل أي حفظ."""
    return {
        u['id']: {'name': u['name'], **{f: u[f] for f in UNIT_TRACKED_FIELDS}}
        for u in product.units.values('id', 'name', *UNIT_TRACKED_FIELDS)
    }


def _unit_prices_diff_summary(old_snapshot, product):
    """
    بيقارن اللقطة القديمة لأسعار الوحدات بالقيم الحالية بعد الحفظ، ويرجع
    سطر عربي مختصر لكل وحدة اتغيّر سعرها فعلًا (سواء وحدة موجودة اتعدّلت،
    وحدة جديدة اتضافت من الصفر، أو وحدة موجودة اتمسحت أثناء التعديل —
    الحذف ده كان بيحصل بصمت من غير أي أثر في تايم لاين النشاط قبل كده).
    """
    parts = []
    current_units = product.units.all()
    seen_ids = set()
    for unit in current_units:
        seen_ids.add(unit.id)
        old = old_snapshot.get(unit.id)
        for field in UNIT_TRACKED_FIELDS:
            new_value = getattr(unit, field)
            old_value = old.get(field) if old else None
            if old_value != new_value:
                label = UNIT_FIELD_LABELS[field]
                if old is None:
                    parts.append(f'{label} ({unit.name}): جديد — {new_value}')
                else:
                    parts.append(f'{label} ({unit.name}): {old_value} → {new_value}')

    for unit_id, old in old_snapshot.items():
        if unit_id not in seen_ids:
            parts.append(f'تم حذف وحدة ({old["name"]})')

    return '، '.join(parts)


@perm_required('products.change_product')
def product_edit(request, pk):
    product = get_object_or_404(
        Product.objects.prefetch_related(
            'similar_products', 'complementary_products', 'variant_group__products',
        ),
        pk=pk,
    )
    if request.method == 'POST':
        # نفس منطق الحساب التلقائي المستخدم في الإضافة (شوف autofill_small_unit_price)
        post_data = autofill_small_unit_price(request.POST)
        form = ProductForm(post_data, request.FILES, instance=product)
        formset = ProductUnitFormSet(post_data, instance=product)
        # بناخد نسخة من القيم القديمة *قبل* الحفظ عشان نقدر نقارنها بعدين
        # ونطلع منها ملخص التغيير الظاهر في تايم لاين النشاط (مرحلة 2).
        old_values = {f: getattr(product, f) for f in PRODUCT_TRACKED_FIELDS}
        old_unit_prices = _snapshot_unit_prices(product)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
            except ProtectedError:
                messages.error(
                    request,
                    'مينفعش تمسح وحدة ليها حركات مخزون أو طلبات مسجّلة عليها — '
                    'عطّل استخدامها بدل الحذف، أو سيبها من غير حذف.'
                )
                return render(request, 'staff/products/form.html', {
                    'form': form, 'formset': formset,
                    'title': f'تعديل: {product.name_ar}', 'is_edit': True, 'product': product,
                    'back_url': url_with_qs(request, 'staff:product_list'),
                    'activity_count': _product_activity_count(product),
                    'tags_count': _product_tags_count(product),
                })
            except IntegrityError:
                messages.error(
                    request,
                    'حدث تعارض غير متوقع أثناء حفظ وحدات المنتج (مثلاً وحدتين بنفس '
                    'الحجم) — يرجى إعادة تحميل الصفحة والتأكد إن كل وحدة (صغرى/كبرى) '
                    'ليها حجم مختلف عن التانية، وإعادة المحاولة. لو المشكلة استمرت، '
                    'يرجى إبلاغ فريق التطوير بخطوات إعادة حدوثها بالتفصيل.'
                )
                return render(request, 'staff/products/form.html', {
                    'form': form, 'formset': formset,
                    'title': f'تعديل: {product.name_ar}', 'is_edit': True, 'product': product,
                    'back_url': url_with_qs(request, 'staff:product_list'),
                    'activity_count': _product_activity_count(product),
                    'tags_count': _product_tags_count(product),
                })

            # أي وحدة جديدة اتضافت أثناء التعديل ومعاها كمية ابتدائية
            stock_setup.apply_initial_stock(
                product, formset, request.user, note='كمية ابتدائية عند إضافة وحدة جديدة للمنتج',
            )

            summary = diff_summary(old_values, product, PRODUCT_TRACKED_FIELDS)
            unit_summary = _unit_prices_diff_summary(old_unit_prices, product)
            combined_summary = '، '.join(part for part in [summary, unit_summary] if part)
            if combined_summary:
                log_activity(product, ActivityLog.Event.UPDATED, user=request.user, changes_summary=combined_summary)

            messages.success(request, f'تم تعديل المنتج "{product.name_ar}" بنجاح.')
            return redirect_with_qs(request, 'staff:product_list')
    else:
        form = ProductForm(instance=product)
        formset = ProductUnitFormSet(instance=product)
    product_actions = []
    if request.user.has_perm('products.add_product'):
        product_actions.append({
            'label': 'تكرار المنتج (نسخة جديدة بنفس البيانات)',
            'href': url_with_qs(request, 'staff:product_duplicate', pk=product.pk),
            'icon': 'duplicate',
        })
    if request.user.has_perm('products.delete_product'):
        product_actions.append({
            'label': 'حذف المنتج',
            'href': url_with_qs(request, 'staff:product_delete', pk=product.pk),
            'icon': 'archive',
            'variant': 'danger',
        })

    return render(request, 'staff/products/form.html', {
        'form': form,
        'formset': formset,
        'title': f'تعديل: {product.name_ar}',
        'is_edit': True,
        'product': product,
        'back_url': url_with_qs(request, 'staff:product_list'),
        'activity_count': _product_activity_count(product),
        'tags_count': _product_tags_count(product),
        'related_orders': _product_related_orders(product),
        'inventory_item': getattr(product, 'inventory', None),
        'product_actions': product_actions,
        'similar_products': product.similar_products.all(),
        'complementary_products': product.complementary_products.all(),
        'variant_siblings': product.variant_siblings,
        'relations_count': (
            len(product.similar_products.all()) + len(product.complementary_products.all()) + len(product.variant_siblings)
        ),
        'similar_search_url': url_with_qs(request, 'staff:product_relation_search', pk=product.pk, relation='similar'),
        'complementary_search_url': url_with_qs(request, 'staff:product_relation_search', pk=product.pk, relation='complementary'),
        'variant_search_url': url_with_qs(request, 'staff:product_variant_search', pk=product.pk),
    })


@perm_required('products.add_product')
def product_duplicate(request, pk):
    """
    تكرار منتج موجود كنقطة بداية بدل ملء فورم من الصفر (مرحلة 4 — نفس
    فكرة "Duplicate Post" في WordPress). النسخة الجديدة بتاخد اسم القسم/
    الاسم/المصنّع/الوصف ووحداتها (بالاسم والسعر والحجم)، لكن عن قصد
    مابتاخدش:
    - الباركود: unique في الموديل، فمينفعش يتكرر على منتجين.
    - الصورة: بتُرفع يدويًا لو الموظف عايز نفس الصورة أو صورة مختلفة.
    - المخزون/الحركات: النسخة الجديدة تبدأ من غير أي رصيد مسجّل عليها.
    وبتتحفظ 'is_active=False' افتراضيًا عشان الموظف يراجع البيانات
    (خصوصًا الاسم والباركود) قبل ما تظهر فعليًا في المتجر.

    زي product_delete، GET بيعرض صفحة تأكيد بسيطة، وPOST هو اللي بينفّذ
    التكرار فعليًا — أي إجراء بينشئ سجل جديد في القاعدة لازم يمر عبر
    تأكيد صريح من الموظف، مش ينفّذ من مجرد رابط GET (زي روابط قائمة
    الإجراءات في staff/components/action_menu.html).
    """
    source = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            new_product = Product.objects.create(
                category=source.category,
                name_ar=f'{source.name_ar} (نسخة)',
                name_en=source.name_en,
                manufacturer=source.manufacturer,
                description=source.description,
                is_active=False,
            )
            for unit in source.units.all():
                ProductUnit.objects.create(
                    product=new_product,
                    size=unit.size,
                    name=unit.name,
                    qty_in_small=unit.qty_in_small,
                    unit_price=unit.unit_price,
                    cost_price=unit.cost_price,
                )
            log_activity(
                new_product, ActivityLog.Event.CREATED, user=request.user,
                note=f'تم إنشاؤه كنسخة من المنتج "{source.name_ar}" (كود {source.code}).',
            )
        messages.success(
            request,
            f'تم إنشاء نسخة من "{source.name_ar}". راجع البيانات (الاسم/الباركود) وفعّل الصنف عند الانتهاء.',
        )
        return redirect_with_qs(request, 'staff:product_edit', pk=new_product.pk)

    return render(request, 'staff/products/duplicate_confirm.html', {
        'product': source,
        'back_url': url_with_qs(request, 'staff:product_edit', pk=source.pk),
    })


@perm_required('products.delete_product')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)

    has_stock = hasattr(product, 'inventory') and product.inventory.quantity > 0

    if request.method == 'POST':
        name = product.name_ar
        if has_stock:
            product.is_active = False
            product.save()
            messages.warning(request, f'المنتج "{name}" له مخزون — تم تعطيله بدل الحذف.')
        else:
            delete_activity_logs_for(product)
            product.delete()
            messages.success(request, f'تم حذف المنتج "{name}".')
        return redirect_with_qs(request, 'staff:product_list')

    return render(request, 'staff/products/delete.html', {
        'product': product,
        'has_stock': has_stock,
        'back_url': url_with_qs(request, 'staff:product_list'),
    })
