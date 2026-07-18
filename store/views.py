from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from products.models import Category, Product, ProductUnit
from products.new_arrivals import new_arrivals_queryset, NEW_ARRIVALS_WINDOW_DAYS
from inventory.models import Inventory
from django.db.models import Q


PRODUCTS_PER_PAGE = 24
NEW_ARRIVALS_PREVIEW_COUNT = 8  # عدد المنتجات في شريط المعاينة بصفحة المتجر الرئيسية


def store_home(request):
    categories = Category.objects.filter(is_active=True)
    selected_category = request.GET.get('category', '')
    selected_manufacturer = request.GET.get('manufacturer', '')
    search_q = request.GET.get('q', '')

    # منتجات "الوارد" بتظهر في مكانها (صفحة/شريط الوارد) بس، مش هنا كمان —
    # عشان الصنف ميبقاش ظاهر في مكانين. لما يخرج من الوارد (كمية أو وقت،
    # راجع products.new_arrivals) بيرجع يظهر هنا تلقائيًا.
    products = (
        Product.objects.filter(is_active=True)
        .exclude(pk__in=new_arrivals_queryset().values('pk'))
        .select_related('category', 'inventory')
        .prefetch_related('units')
    )

    if selected_category:
        products = products.filter(category__slug=selected_category)
    if selected_manufacturer:
        products = products.filter(manufacturer=selected_manufacturer)
    if search_q:
       products = products.filter(
    Q(name_ar__icontains=search_q) |
    Q(name_en__icontains=search_q)
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
    }

    # لو طلب HTMX يرجع partial بس (تحديث الشبكة فقط عند الفلترة) — من غير
    # ما نحسب معاينة "الوارد" في كل مرة، هي مش موجودة في الـ partial أصلًا.
    if request.headers.get('HX-Request'):
        return render(request, 'store/partials/product_grid.html', context)

    # شريط "الوارد الجديد" — خاص بالعملاء المسجّلين فقط، مش بيظهر لأي زائر
    # غير مسجّل حتى لو الصفحة نفسها عامة. نفس منتجات المتجر بالظبط، بس
    # معروضة هنا كمان كمعاينة (مفيش نسخ بيانات، مجرد استعلام تاني).
    if request.user.is_authenticated:
        context['new_arrivals_preview'] = new_arrivals_queryset()[:NEW_ARRIVALS_PREVIEW_COUNT]

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
    })
