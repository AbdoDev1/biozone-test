from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from products.models import Category, Product, ProductUnit
from products.matching import normalize_name
from products.new_arrivals import new_arrival_filter, NEW_ARRIVALS_WINDOW_DAYS
from inventory.models import Inventory
from orders.cart import Cart
from django.db.models import Q, Case, When, Value, BooleanField


def _cart_quantities(request):
    """
    قاموس {unit_id: quantity} للسلة النشطة الحالية — بيتحسب مرة واحدة
    وبيتحقن في شبكة المنتجات عشان بطاقة المنتج تعرف تعرض الـ stepper
    (+/-) للأصناف الموجودة فعلاً بالسلة بدل زرار "أضف" دايمًا. فاضل
    فاضي لغير العميل المسجّل (زائر/موظف) لأنه مالوش سلة أصلًا.
    """
    if request.user.is_authenticated and request.user.role == 'CLIENT':
        return Cart(request).get_quantities()
    return {}


PRODUCTS_PER_PAGE = 24


def _base_products_queryset():
    """
    كل المنتجات النشطة، معلَّم عليها is_new_arrival (badge "وارد جديد" في
    الكارت) — من غير أي استبعاد؛ الصنف الوارد فاضل ظاهر هنا زي أي منتج
    عادي بالظبط (في الشبكة، البحث، والأقسام)، وده الفرق الأساسي عن
    التصميم القديم اللي كان بيشيل الصنف من هنا لحد ما يخرج من "الوارد".
    """
    return (
        Product.objects.filter(is_active=True)
        .annotate(
            is_new_arrival=Case(
                When(new_arrival_filter(), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )
        .select_related('category', 'inventory')
        # 'units__discounts' (مش 'units' بس) — لأن كارت المنتج بيحسب السعر
        # بعد الخصم لكل صنف لو site_config.show_discounted_prices مفعّل،
        # وده بيوصل لـ unit.discounts.all() لكل وحدة. من غير الـ prefetch
        # ده، كل منتج في الصفحة (24) كان بيعمل استعلام إضافي منفصل (N+1).
        .prefetch_related('units__discounts')
    )


def _apply_filters(products, request):
    """
    بحث + فلترة (قسم/شركة مصنعة) مشتركة بين المتجر العادي وصفحة الوارد،
    عشان صفحة الوارد تدعم نفس البحث والفلاتر بالظبط (كانت ناقصة قبل كده).
    """
    selected_category = request.GET.get('category', '')
    selected_manufacturer = request.GET.get('manufacturer', '')
    search_q = request.GET.get('q', '').strip()

    if selected_category:
        products = products.filter(category__slug=selected_category)
    if selected_manufacturer:
        products = products.filter(manufacturer=selected_manufacturer)
    if search_q:
        normalized_q = normalize_name(search_q)
        products = products.filter(
            Q(name_ar__icontains=search_q)
            | Q(name_en__icontains=search_q)
            | Q(name_key__icontains=normalized_q)
        )

    return products, selected_category, selected_manufacturer, search_q


def _manufacturers_list():
    return (
        Product.objects.filter(is_active=True)
        .exclude(manufacturer='')
        .values_list('manufacturer', flat=True)
        .distinct()
    )


def store_home(request):
    categories = Category.objects.filter(is_active=True)
    products, selected_category, selected_manufacturer, search_q = _apply_filters(
        _base_products_queryset(), request
    )
    manufacturers = _manufacturers_list()

    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    # لو فلتر (فئة/بحث) اتغيّر ورجع صفحة مش موجودة (مثلاً كنت في صفحة 5
    # وبقى الناتج صفحتين بس)، get_page بترجع آخر صفحة صالحة بدل ما تطلع خطأ.
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'total_products': paginator.count,
        'categories': categories,
        'manufacturers': manufacturers,
        'selected_category': selected_category,
        'selected_manufacturer': selected_manufacturer,
        'search_q': search_q,
        'grid_url': 'store:home',
        'cart_quantities': _cart_quantities(request),
    }

    if request.headers.get('HX-Request'):
        return HttpResponse(render_to_string('store/partials/product_grid.html', context, request=request))

    return render(request, 'store/home.html', context)


def store_search(request):
    return store_home(request)


@login_required
def new_arrivals(request):
    """
    صفحة "الوارد الجديد" — كل منتج جديد أو اتزوّد رصيده خلال آخر
    NEW_ARRIVALS_WINDOW_DAYS يوم (نفس شرط badge الوارد في المتجر العادي
    بالظبط). خاصة بالعملاء المسجّلين فقط (login_required)، وبتدعم نفس
    بحث/فلاتر المتجر العادي (قسم، شركة مصنعة، بحث بالاسم) — الصنف هنا
    فاضل موجود في المتجر العادي كمان، الصفحة دي مجرد تجميعة مفلترة.
    """
    categories = Category.objects.filter(is_active=True)
    base_qs = _base_products_queryset().filter(new_arrival_filter())
    products, selected_category, selected_manufacturer, search_q = _apply_filters(base_qs, request)
    manufacturers = _manufacturers_list()

    paginator = Paginator(products.order_by('-new_arrival_at'), PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'total_products': paginator.count,
        'categories': categories,
        'manufacturers': manufacturers,
        'selected_category': selected_category,
        'selected_manufacturer': selected_manufacturer,
        'search_q': search_q,
        'window_days': NEW_ARRIVALS_WINDOW_DAYS,
        'grid_url': 'store:new_arrivals',
        'cart_quantities': _cart_quantities(request),
    }

    if request.headers.get('HX-Request'):
        return HttpResponse(render_to_string('store/partials/product_grid.html', context, request=request))

    return render(request, 'store/new_arrivals.html', context)


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related(
            'units__discounts',
            'similar_products__units__discounts', 'similar_products__category', 'similar_products__inventory',
            'complementary_products__units__discounts', 'complementary_products__category', 'complementary_products__inventory',
            'variant_group__products', 'variant_group__products__inventory',
        ),
        pk=pk,
    )
    # صفحة منتج واحد بس (مش شبكة متجر)، فمفيش قلق أداء من استعلام إضافي هنا.
    # units_for_client بيحدد الوحدة (أو الوحدات) اللي تظهر لنوع الحساب ده:
    # قطاعي = أصغر وحدة، جملة = أكبر وحدة.
    # ملحوظة: المخزون بقى على مستوى المنتج (product.inventory) مش الوحدة —
    # ما بنعملش وصول مباشر ليه هنا في كود بايثون، لأن منتج جديد لسه ماتفتحش
    # له مخزون هيعمل RelatedObjectDoesNotExist. القالب بيوصل لـ product.inventory
    # بأمان (Django بيتعامل مع الغياب ده silently جوه التمبليت).
    client = request.user if request.user.is_authenticated else None
    units = product.units_for_client(client)
    # نفلتر على is_active بايثونيًا (مش .filter() جديد) عشان نستفيد من
    # الـ prefetch_related الجاهز فوق بدل ما نضرب استعلام إضافي لكل قسم.
    similar_products = [p for p in product.similar_products.all() if p.is_active][:6]
    complementary_products = [p for p in product.complementary_products.all() if p.is_active][:6]
    variant_siblings = [p for p in product.variant_siblings if p.is_active]
    return render(request, 'store/product_detail.html', {
        'product': product,
        'units': units,
        'cart_quantities': _cart_quantities(request),
        'similar_products': similar_products,
        'complementary_products': complementary_products,
        'variant_siblings': variant_siblings,
    })
