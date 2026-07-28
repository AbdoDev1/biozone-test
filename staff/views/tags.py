from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import render, get_object_or_404

from staff.permissions import perm_required
from staff.utils import redirect_with_qs
from tags.models import Tag

STAFF_LIST_PAGE_SIZE = 30

# نفس فكرة PRODUCT_SORT_FIELDS في staff/views/products/crud.py — خريطة
# اسم الترتيب في الرابط (?sort=...) لاسم الحقل/annotation الفعلي في الاستعلام،
# عشان نتحقق إن القيمة القادمة من querystring آمنة قبل استخدامها في order_by.
TAG_SORT_FIELDS = {
    'name': 'name',
    'usage': 'usage_count',
    'created_at': 'created_at',
}


@perm_required('tags.view_tag')
def tag_list(request):
    """
    نسخة مبسطة من TagAdmin (كانت في /admin/tags/tag/) — عرض/بحث/فلترة/ترتيب
    وإضافة/تعديل/حذف الوسوم، بنفس شكل باقي شاشات لوحة الموظفين بدل الشكل
    التقني الافتراضي لإدارة دجانجو. عدد استخدامات كل وسم (usage_count)
    بيتحسب هنا بدل ما يتعرض في صفحة منفصلة (TaggedItemAdmin)، لأنه المعلومة
    العملية المهمة فعليًا (هل الوسم ده مستخدم ولا ينفع يتشال بأمان).
    """
    tags = Tag.objects.annotate(usage_count=Count('tagged_items', distinct=True))

    search_q = request.GET.get('q', '').strip()
    color_filter = request.GET.get('color', '')
    sort = request.GET.get('sort', 'name')
    if sort not in TAG_SORT_FIELDS:
        sort = 'name'
    direction = request.GET.get('dir', 'asc')
    if direction not in ('asc', 'desc'):
        direction = 'asc'

    if search_q:
        tags = tags.filter(name__icontains=search_q)
    if color_filter:
        tags = tags.filter(color=color_filter)

    order_field = TAG_SORT_FIELDS[sort]
    tags = tags.order_by(order_field if direction == 'asc' else f'-{order_field}')

    paginator = Paginator(tags, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'staff/tags/list.html', {
        'page_obj': page_obj,
        'tags': page_obj,
        'search_q': search_q,
        'color_filter': color_filter,
        'color_choices': Tag.Color.choices,
        'sort': sort,
        'dir': direction,
    })


@perm_required('tags.add_tag')
def tag_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', Tag.Color.GRAY)
        if not name:
            messages.error(request, 'اسم الوسم مطلوب.')
        else:
            try:
                with transaction.atomic():
                    Tag.objects.create(name=name, color=color)
                messages.success(request, f'تم إضافة الوسم "{name}".')
            except IntegrityError:
                messages.error(request, f'في وسم بنفس الاسم "{name}" موجود بالفعل.')
    return redirect_with_qs(request, 'staff:tag_list')


@perm_required('tags.change_tag')
def tag_edit(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', tag.color)
        if not name:
            messages.error(request, 'اسم الوسم مطلوب.')
        else:
            tag.name = name
            tag.color = color
            try:
                with transaction.atomic():
                    tag.save()
                messages.success(request, f'تم تحديث الوسم "{name}".')
            except IntegrityError:
                messages.error(request, f'في وسم بنفس الاسم "{name}" موجود بالفعل.')
    return redirect_with_qs(request, 'staff:tag_list')


@perm_required('tags.delete_tag')
def tag_delete(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    if request.method == 'POST':
        name = tag.name
        # الحذف بيمسح كل TaggedItem المرتبط بالوسم ده كمان (on_delete=CASCADE
        # في tags.models.TaggedItem) — يعني الوسم هيتشال من كل العناصر اللي
        # عليها، بنفس سلوك حذفه من Django admin بالظبط.
        tag.delete()
        messages.success(request, f'تم حذف الوسم "{name}" وإزالته من كل العناصر المرتبطة به.')
    return redirect_with_qs(request, 'staff:tag_list')
