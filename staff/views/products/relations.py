"""
مرحلة 5 (ROADMAP.md) — منتجات مشابهة/مكمّلة + مقاسات/تنويعات (Product Variants).

هذا الملف مسؤول عن:
- Product Picker العام (بحث + شرائح htmx) — نفس المكوّن المُعاد استخدامه
  لثلاث علاقات مختلفة (مشابه/مكمّل/تنويع مقاس)، بدل ما يتبني من الصفر
  لكل واحدة على حدة (راجع قاعدة "موديلات/مكوّنات عامة بدل مكررة" في
  ROADMAP.md قسم 2-ج).
- إضافة/إزالة منتجات مشابهة ومكمّلة (M2M بسيط).
- ربط/فك ربط مقاسات (ProductVariantGroup) — منطق مختلف شوية لأنه بيحتاج
  ينشئ/يستخدم مجموعة مشتركة، مش يضيف صف M2M مباشر.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.matching import normalize_name
from products.models import Product, ProductVariantGroup
from staff.permissions import perm_required
from staff.utils import redirect_with_qs
from activity.services import log_activity
from activity.models import ActivityLog

# العلاقات المسموح البحث/الإضافة فيها عبر product_relation_search/_add —
# مفتاح واحد يوصف كل علاقة (اسم الحقل + تسمية عربية للرسائل). "variant"
# مش موجود هنا لأنه له view منفصل (product_variant_link) بمنطق مختلف.
RELATION_FIELDS = {
    'similar': ('similar_products', 'منتج مشابه'),
    'complementary': ('complementary_products', 'منتج مكمّل'),
}

PICKER_RESULTS_LIMIT = 8


def _search_products(query, exclude_ids):
    """
    بحث عام لأي Product Picker (بالاسم العربي/الإنجليزي أو الاسم المُطبَّع)،
    مستبعد منه أي id في exclude_ids (المنتج نفسه + المرتبطين بالفعل).
    """
    query = (query or '').strip()
    if not query:
        return Product.objects.none()
    normalized_q = normalize_name(query)
    from django.db.models import Q
    return (
        Product.objects.filter(
            Q(name_ar__icontains=query) | Q(name_key__icontains=normalized_q) | Q(name_en__icontains=query)
        )
        .exclude(pk__in=exclude_ids)
        .select_related('category')[:PICKER_RESULTS_LIMIT]
    )


@perm_required('products.change_product')
def product_relation_search(request, pk, relation):
    """
    نتيجة البحث (htmx) لعلاقة معيّنة (similar/complementary) — بيرجّع
    partial فيه أزرار قابلة للضغط لكل نتيجة، ماعداش المنتج نفسه والمرتبطين
    فعلًا بنفس العلاقة (منعًا لإضافة مكررة).
    """
    if relation not in RELATION_FIELDS:
        return render(request, 'staff/products/partials/relation_picker_results.html', {'results': []})
    product = get_object_or_404(Product, pk=pk)
    field_name, _ = RELATION_FIELDS[relation]
    already_linked_ids = list(getattr(product, field_name).values_list('pk', flat=True))
    results = _search_products(request.GET.get('q', ''), exclude_ids=already_linked_ids + [product.pk])
    return render(request, 'staff/products/partials/relation_picker_results.html', {
        'results': results, 'relation': relation, 'product': product,
    })


@perm_required('products.change_product')
@require_POST
def product_relation_add(request, pk, relation):
    if relation not in RELATION_FIELDS:
        messages.error(request, 'نوع علاقة غير معروف.')
        return redirect_with_qs(request, 'staff:product_edit', pk=pk)

    product = get_object_or_404(Product, pk=pk)
    target = get_object_or_404(Product, pk=request.POST.get('target_id'))
    field_name, label = RELATION_FIELDS[relation]

    if target.pk == product.pk:
        messages.error(request, 'لا يمكن ربط المنتج بنفسه.')
        return redirect_with_qs(request, 'staff:product_edit', pk=pk)

    getattr(product, field_name).add(target)
    log_activity(
        product, ActivityLog.Event.UPDATED, user=request.user,
        changes_summary=f'إضافة {label}: {target.name_ar}',
    )
    return redirect_with_qs(request, 'staff:product_edit', pk=pk)


@perm_required('products.change_product')
@require_POST
def product_relation_remove(request, pk, relation):
    if relation not in RELATION_FIELDS:
        messages.error(request, 'نوع علاقة غير معروف.')
        return redirect_with_qs(request, 'staff:product_edit', pk=pk)

    product = get_object_or_404(Product, pk=pk)
    target = get_object_or_404(Product, pk=request.POST.get('target_id'))
    field_name, label = RELATION_FIELDS[relation]

    getattr(product, field_name).remove(target)
    log_activity(
        product, ActivityLog.Event.UPDATED, user=request.user,
        changes_summary=f'إزالة {label}: {target.name_ar}',
    )
    return redirect_with_qs(request, 'staff:product_edit', pk=pk)


@perm_required('products.change_product')
def product_variant_search(request, pk):
    """
    نفس مكوّن البحث العام، لكن مستبعد منه أعضاء نفس مجموعة المقاسات
    الحالية (لو موجودة) بدل استبعاد M2M عادي.
    """
    product = get_object_or_404(Product, pk=pk)
    exclude_ids = [product.pk]
    if product.variant_group_id:
        exclude_ids += list(product.variant_group.products.values_list('pk', flat=True))
    results = _search_products(request.GET.get('q', ''), exclude_ids=exclude_ids)
    return render(request, 'staff/products/partials/relation_picker_results.html', {
        'results': results, 'relation': 'variant', 'product': product,
    })


@perm_required('products.change_product')
@require_POST
def product_variant_link(request, pk):
    """
    ربط منتج تاني كمقاس بديل لنفس الصنف:
    - لو المنتج الحالي عنده variant_group بالفعل، المنتج التاني بينضم لها.
    - لو المنتج الحالي مالوش مجموعة، بتتنشأ مجموعة جديدة وتتحدد لكل
      المنتجين مع بعض.
    - لو المنتج التاني كان عنده مجموعة تانية خالص (نادر، بس ممكن)، بينقل
      منها لمجموعة المنتج الحالي — مفيش دمج مجموعات، مجرد نقل عضوية.
    """
    product = get_object_or_404(Product, pk=pk)
    target = get_object_or_404(Product, pk=request.POST.get('target_id'))

    if target.pk == product.pk:
        messages.error(request, 'لا يمكن ربط المنتج بنفسه.')
        return redirect_with_qs(request, 'staff:product_edit', pk=pk)

    if not product.variant_group_id:
        product.variant_group = ProductVariantGroup.objects.create()
        product.save(update_fields=['variant_group'])

    target.variant_group = product.variant_group
    target.save(update_fields=['variant_group'])

    log_activity(
        product, ActivityLog.Event.UPDATED, user=request.user,
        changes_summary=f'ربط مقاس بديل: {target.name_ar}',
    )
    messages.success(request, f'تم ربط "{target.name_ar}" كمقاس بديل لهذا الصنف.')
    return redirect_with_qs(request, 'staff:product_edit', pk=pk)


@perm_required('products.change_product')
@require_POST
def product_variant_unlink(request, pk, target_pk):
    """
    فك ربط منتج من مجموعة المقاسات — المنتج المُزال بيرجع variant_group=None
    (مش حذف)، ولو فضل عضو واحد بس في المجموعة بعد الإزالة، المجموعة نفسها
    بتتمسح (مالهاش معنى تفضل موجودة بعضو واحد).
    """
    product = get_object_or_404(Product, pk=pk)
    target = get_object_or_404(Product, pk=target_pk)

    if not product.variant_group_id or target.variant_group_id != product.variant_group_id:
        messages.error(request, 'هذا المنتج ليس ضمن نفس مجموعة المقاسات.')
        return redirect_with_qs(request, 'staff:product_edit', pk=pk)

    group = product.variant_group
    target.variant_group = None
    target.save(update_fields=['variant_group'])

    remaining = group.products.count()
    if remaining <= 1:
        group.delete()  # ما ينفعش تفضل مجموعة بعضو واحد أو صفر

    log_activity(
        product, ActivityLog.Event.UPDATED, user=request.user,
        changes_summary=f'فك ربط مقاس: {target.name_ar}',
    )
    messages.success(request, f'تم فك ربط "{target.name_ar}" عن مجموعة المقاسات.')
    return redirect_with_qs(request, 'staff:product_edit', pk=pk)
