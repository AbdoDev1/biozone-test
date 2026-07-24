"""
منطق "الرصيد الابتدائي" وقت إضافة/تعديل منتج من فورم الموظف — كان مكرر
بالظبط في product_add وproduct_edit (staff/views/products.py) قبل كده.
"""
from inventory.models import Inventory, StockMovement


def apply_initial_stock(product, formset, user, note):
    """
    بعد حفظ formset الوحدات، بتمر على كل وحدة (غير المحذوفة) وتسجّل حركة
    "وارد" لو الموظف كتب initial_stock > 0. initial_stock مش حقل موديل —
    بيتقرا من cleaned_data لكل نموذج في الـ formset مباشرة.
    """
    inventory, _ = Inventory.objects.get_or_create(
        product=product,
        defaults={'quantity': 0, 'reserved': 0, 'min_quantity': 0},
    )
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
                note=note,
                created_by=user,
            )
    return inventory
