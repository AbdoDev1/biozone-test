from django.shortcuts import render, get_object_or_404
from products.models import Category, Product, ProductUnit
from inventory.models import Inventory

def store_home(request):
    categories = Category.objects.filter(is_active=True)
    selected_category = request.GET.get('category', '')
    selected_manufacturer = request.GET.get('manufacturer', '')
    search_q = request.GET.get('q', '')

    products = Product.objects.filter(is_active=True).select_related('category', 'inventory').prefetch_related('units')

    if selected_category:
        products = products.filter(category__slug=selected_category)
    if selected_manufacturer:
        products = products.filter(manufacturer=selected_manufacturer)
    if search_q:
        products = products.filter(name_ar__icontains=search_q) | \
                   products.filter(name_en__icontains=search_q)

    manufacturers = Product.objects.filter(is_active=True)\
                           .exclude(manufacturer='')\
                           .values_list('manufacturer', flat=True)\
                           .distinct()

    context = {
        'products': products,
        'categories': categories,
        'manufacturers': manufacturers,
        'selected_category': selected_category,
        'selected_manufacturer': selected_manufacturer,
        'search_q': search_q,
    }

    # لو طلب HTMX يرجع partial بس
    if request.headers.get('HX-Request'):
        return render(request, 'store/partials/product_grid.html', context)

    return render(request, 'store/home.html', context)


def store_search(request):
    return store_home(request)


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
