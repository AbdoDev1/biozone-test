"""
عمليات CRUD الأساسية للمنتجات (عرض/إضافة/تعديل/حذف). منطق استيراد/تصدير
إكسل منفصل في import_export.py — راجع staff/views/products/__init__.py
للتوثيق الكامل لسبب الفصل.
"""

from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q

from products.models import Product, Category
from products.forms import ProductForm, ProductUnitFormSet
from products.pricing import autofill_small_unit_price
from products.matching import normalize_name
from inventory.models import Inventory, StockMovement
from staff.permissions import perm_required
from staff.utils import list_qs, url_with_qs, redirect_with_qs

STAFF_LIST_PAGE_SIZE = 30


@perm_required('products.view_product')
def product_list(request):
    products = Product.objects.select_related('category', 'inventory').prefetch_related('units').all()
    categories = Category.objects.filter(is_active=True)
    selected_category = request.GET.get('category', '')
    # .strip() هي أهم سطر هنا: من غيرها، مسافة زيادة قبل/بعد النص المكتوب
    # (تاب على الشيفت بالغلط، أو نسخ/لصق) كانت بتخلي name_ar__icontains
    # مايلاقيش أي نتيجة رغم إن الصنف موجود فعلاً بنفس الاسم بالظبط.
    search_q = request.GET.get('q', '').strip()
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

    paginator = Paginator(products, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'staff/products/list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'total_products': paginator.count,
        'categories': categories,
        'selected_category': selected_category,
        'search_q': search_q,
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

            inventory, _ = Inventory.objects.get_or_create(
                product=product,
                defaults={'quantity': 0, 'reserved': 0, 'min_quantity': 0},
            )
            # initial_stock مش حقل موديل — بنقراه من cleaned_data لكل نموذج غير محذوف
            for unit_form in formset.forms:
                if unit_form.cleaned_data.get('DELETE'):
                    continue
                unit = unit_form.instance
                initial_stock = unit_form.cleaned_data.get('initial_stock') or 0
                if unit.pk and initial_stock > 0:
                    StockMovement.objects.create(
                        inventory=inventory,
                        unit=unit,
                        movement_type='IN',
                        quantity=initial_stock,
                        note='كمية ابتدائية عند إضافة المنتج',
                        created_by=request.user,
                    )
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


@perm_required('products.change_product')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        # نفس منطق الحساب التلقائي المستخدم في الإضافة (شوف autofill_small_unit_price)
        post_data = autofill_small_unit_price(request.POST)
        form = ProductForm(post_data, request.FILES, instance=product)
        formset = ProductUnitFormSet(post_data, instance=product)
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
                })

            # أي وحدة جديدة اتضافت أثناء التعديل ومعاها كمية ابتدائية
            inventory, _ = Inventory.objects.get_or_create(
                product=product,
                defaults={'quantity': 0, 'reserved': 0, 'min_quantity': 0},
            )
            for unit_form in formset.forms:
                if unit_form.cleaned_data.get('DELETE'):
                    continue
                initial_stock = unit_form.cleaned_data.get('initial_stock') or 0
                unit = unit_form.instance
                if unit.pk and initial_stock > 0:
                    StockMovement.objects.create(
                        inventory=inventory,
                        unit=unit,
                        movement_type='IN',
                        quantity=initial_stock,
                        note='كمية ابتدائية عند إضافة وحدة جديدة للمنتج',
                        created_by=request.user,
                    )

            messages.success(request, f'تم تعديل المنتج "{product.name_ar}" بنجاح.')
            return redirect_with_qs(request, 'staff:product_list')
    else:
        form = ProductForm(instance=product)
        formset = ProductUnitFormSet(instance=product)
    return render(request, 'staff/products/form.html', {
        'form': form,
        'formset': formset,
        'title': f'تعديل: {product.name_ar}',
        'is_edit': True,
        'product': product,
        'back_url': url_with_qs(request, 'staff:product_list'),
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
            product.delete()
            messages.success(request, f'تم حذف المنتج "{name}".')
        return redirect_with_qs(request, 'staff:product_list')

    return render(request, 'staff/products/delete.html', {
        'product': product,
        'has_stock': has_stock,
        'back_url': url_with_qs(request, 'staff:product_list'),
    })
