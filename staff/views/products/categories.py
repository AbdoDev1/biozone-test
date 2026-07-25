"""
إدارة أقسام المنتجات (Category) من لوحة الموظفين: عرض/إضافة/تعديل/حذف.
منفصلة عن crud.py (منتجات) لأنها موديل مختلف تمامًا، بس بنفس الباترن
(نفس ديكوريتور الصلاحيات، نفس شكل شاشة التأكيد قبل الحذف).
"""
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import ProtectedError, Count

from products.models import Category
from products.forms import CategoryForm
from staff.permissions import perm_required

CATEGORY_LIST_PAGE_SIZE = 30


@perm_required('products.view_category')
def category_list(request):
    categories = Category.objects.annotate(products_count=Count('products')).order_by('name')
    search_q = request.GET.get('q', '').strip()
    if search_q:
        categories = categories.filter(name__icontains=search_q)

    paginator = Paginator(categories, CATEGORY_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'staff/categories/list.html', {
        'categories': page_obj,
        'page_obj': page_obj,
        'total_categories': paginator.count,
        'search_q': search_q,
    })


@perm_required('products.add_category')
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'تم إضافة القسم "{category.name}" بنجاح.')
            return redirect('staff:category_list')
    else:
        form = CategoryForm()
    return render(request, 'staff/categories/form.html', {
        'form': form,
        'title': 'إضافة قسم جديد',
        'is_edit': False,
    })


@perm_required('products.change_category')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'تم تعديل القسم "{category.name}" بنجاح.')
            return redirect('staff:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'staff/categories/form.html', {
        'form': form,
        'title': f'تعديل: {category.name}',
        'is_edit': True,
        'category': category,
    })


@perm_required('products.delete_category')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    # Product.category معمول عليه on_delete=PROTECT، يعني أي قسم فيه أصناف
    # (حتى معطّلة) مينفعش يتحذف فعليًا من قاعدة البيانات — بنعطّله (soft
    # delete) بدل الحذف الحقيقي، زي بالظبط منطق product_delete في crud.py.
    has_products = category.products.exists()

    if request.method == 'POST':
        name = category.name
        if has_products:
            category.is_active = False
            category.save()
            messages.warning(request, f'القسم "{name}" له أصناف مرتبطة به — تم تعطيله بدل الحذف.')
        else:
            try:
                category.delete()
                messages.success(request, f'تم حذف القسم "{name}".')
            except ProtectedError:
                category.is_active = False
                category.save()
                messages.warning(request, f'القسم "{name}" مرتبط بأصناف — تم تعطيله بدل الحذف.')
        return redirect('staff:category_list')

    return render(request, 'staff/categories/delete.html', {
        'category': category,
        'has_products': has_products,
    })
