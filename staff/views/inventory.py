from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from inventory.models import Inventory, StockMovement
from products.models import ProductUnit
from staff.permissions import perm_required


@perm_required('inventory.view_inventory')
def inventory_list(request):
    items = list(
        Inventory.objects.select_related(
            'product__category'
        ).prefetch_related('product__units').order_by('product__name_ar')
    )
    return render(request, 'staff/inventory/list.html', {'items': items})


@perm_required('inventory.view_inventory')
def inventory_detail(request, pk):
    item = get_object_or_404(Inventory, pk=pk)
    movements = item.movements.select_related('created_by', 'unit').order_by('-created_at')[:20]
    units = list(item.product.units.all())

    return render(request, 'staff/inventory/detail.html', {
        'item': item,
        'movements': movements,
        'units': units,
    })


@perm_required('inventory.add_stockmovement')
def add_movement(request, pk):
    item = get_object_or_404(Inventory, pk=pk)
    if request.method == 'POST':
        movement_type = request.POST.get('movement_type')
        note = request.POST.get('note', '')
        unit_id = request.POST.get('unit_id')

        manual_allowed_types = {
            StockMovement.MovementType.IN,
            StockMovement.MovementType.OUT,
            StockMovement.MovementType.RESERVE,
            StockMovement.MovementType.RELEASE,
        }
        if movement_type not in manual_allowed_types:
            messages.error(request, 'نوع الحركة غير صحيح')
            return redirect('staff:inventory_detail', pk=pk)

        unit = ProductUnit.objects.filter(pk=unit_id, product_id=item.product_id).first()
        if not unit:
            messages.error(request, 'يرجى اختيار الوحدة (كرتونة/قطعة) التي سُجّلت بها الكمية')
            return redirect('staff:inventory_detail', pk=pk)

        try:
            quantity = int(request.POST.get('quantity', 0))
        except (TypeError, ValueError):
            messages.error(request, 'الكمية غير صحيحة')
            return redirect('staff:inventory_detail', pk=pk)

        movement = StockMovement(
            inventory=item,
            unit=unit,
            movement_type=movement_type,
            quantity=quantity,
            note=note,
            created_by=request.user,
        )
        try:
            movement.full_clean()
        except ValidationError as e:
            for err in e.messages:
                messages.error(request, err)
            return redirect('staff:inventory_detail', pk=pk)

        movement.save()
        messages.success(request, 'تم تسجيل الحركة بنجاح')
        return redirect('staff:inventory_detail', pk=pk)
    return redirect('staff:inventory_detail', pk=pk)
