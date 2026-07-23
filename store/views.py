from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from products.models import Category, Product, ProductUnit
from products.matching import normalize_name
from products.new_arrivals import new_arrivals_queryset, NEW_ARRIVALS_WINDOW_DAYS
from inventory.models import Inventory
from orders.cart import Cart
from django.db.models import Q


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
NEW_ARRIVALS_PREVIEW_COUNT = 8  # عدد المنتجات في شريط المعاينة بصفحة المتجر الرئيسية


def store_home(request):
    categories = Category.objects.filter(is_active=True)
    selected_category = request.GET.get('category', '')
    selected_manufacturer = request.GET.get('manufacturer', '')
    search_q = request.GET.get('q', '').strip()

    # منتجات "الوارد" بتظهر في مكانها (صفحة/شريط الوارد) بس، مش هنا كمان —
    # عشان الصنف ميبقاش ظاهر في مكانين. لما يخرج من الوارد (كمية أو وقت،
    # راجع products.new_arrivals) بيرجع يظهر هنا تلقائيًا.
    products = (
        Product.objects.filter(is_active=True)
        .exclude(pk__in=new_arrivals_queryset().values('pk'))
        .select_related('category', 'inventory')
        # 'units__discounts' (مش 'units' بس) — لأن كارت المنتج بيحسب السعر
        # بعد الخصم لكل صنف لو site_config.show_discounted_prices مفعّل،
        # وده بيوصل لـ unit.discounts.all() لكل وحدة. من غير الـ prefetch
        # ده، كل منتج في الصفحة (24) كان بيعمل استعلام إضافي منفصل (N+1).
        .prefetch_related('units__discounts')
    )

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
    manufacturers = Product.objects.filter(is_active=True)\
                           .exclude(manufacturer='')\
                           .values_list('manufacturer', flat=True)\
                           .distinct()

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

    # شريط "الوارد الجديد" — خاص بالعملاء المسجّلين فقط، مش بيظهر لأي زائر
    # غير مسجّل حتى لو الصفحة نفسها عامة. نفس منتجات المتجر بالظبط، بس
    # معروضة هنا كمان كمعاينة (مفيش نسخ بيانات، مجرد استعلام تاني).
    # بيظهر بس في أول صفحة من الصفحة الرئيسية (من غير بحث أو فلتر أو تنقل
    # لصفحة تانية)، عشان ميظهرش مع نتائج بحث العميل عن منتج معيّن، أو
    # نتائج فلترة فئة/شركة، أو صفحات لاحقة من نفس القائمة.
    is_filtered_view = bool(search_q or selected_category or selected_manufacturer)
    show_new_arrivals = (
        request.user.is_authenticated
        and not is_filtered_view
        and page_obj.number == 1
    )
    if show_new_arrivals:
        context['new_arrivals_preview'] = new_arrivals_queryset()[:NEW_ARRIVALS_PREVIEW_COUNT]

    # لو طلب HTMX (بحث/فلترة/تنقل صفحات)، بنرجّع الشبكة كـ partial، وكمان
    # نسخة محدّثة من شريط "الوارد الجديد" كـ out-of-band swap — عشان الشريط
    # ده برّه #product-grid (اللي هو الـ hx-target الوحيد)، ولو سبناه من
    # غيره كان هيفضل ظاهر زي ما هو حتى لو العميل بيبحث أو بيتنقل لصفحة تانية.
    if request.headers.get('HX-Request'):
        grid_html = render_to_string('store/partials/product_grid.html', context, request=request)
        oob_html = render_to_string('store/partials/new_arrivals_block_oob.html', context, request=request)
        return HttpResponse(grid_html + oob_html)

    return render(request, 'store/home.html', context)


def store_search(request):
    return store_home(request)


@login_required
def new_arrivals(request):
    """
    صفحة "الوارد الجديد" — أي منتج جديد أو رصيد جديد اتضاف خلال آخر
    NEW_ARRIVALS_WINDOW_DAYS يوم. خاصة بالعملاء المسجّلين فقط (login_required)،
    ومش بتاخد أي بيانات مستقلة — هي نفس منتجات المتجر، مجرد فلتر بالتاريخ.
    """
    products_qs = new_arrivals_queryset()
    paginator = Paginator(products_qs, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'total_products': paginator.count,
        'window_days': NEW_ARRIVALS_WINDOW_DAYS,
        'grid_url': 'store:new_arrivals',
        'cart_quantities': _cart_quantities(request),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'store/partials/product_grid.html', context)

    return render(request, 'store/new_arrivals.html', context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    # صفحة منتج واحد بس (مش شبكة متجر)، فمفيش قلق أداء من استعلام إضافي هنا.
    # units_for_client بيحدد الوحدة (أو الوحدات) اللي تظهر لنوع الحساب ده:
    # قطاعي = أصغر وحدة، جملة = أكبر وحدة.
    # ملحوظة: المخزون بقى على مستوى المنتج (product.inventory) مش الوحدة —
    # ما بنعملش وصول مباشر ليه هنا في كود بايثون، لأن منتج جديد لسه ماتفتحش
    # له مخزون هيعمل RelatedObjectDoesNotExist. القالب بيوصل لـ product.inventory
    # بأمان (Django بيتعامل مع الغياب ده silently جوه التمبليت).
    client = request.user if request.user.is_authenticated else None
    units = product.units_for_client(client)
    return render(request, 'store/product_detail.html', {
        'product': product,
        'units': units,
        'cart_quantities': _cart_quantities(request),
    })
