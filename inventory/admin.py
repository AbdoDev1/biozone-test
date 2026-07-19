from django.contrib import admin
from .models import Inventory, StockMovement


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 1
    fields = ('movement_type', 'unit', 'quantity', 'note', 'created_by')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('movement_type', 'unit', 'quantity', 'note', 'created_by')
        return ()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'reserved', 'available', 'min_quantity', 'is_low')
    list_filter = ('product__category',)
    search_fields = ('product__name_ar', 'product__name_en')
    # min_quantity وis_available بقوا يتعدّلوا من صفحة تفاصيل المخزون في
    # لوحة الموظفين (staff:inventory_detail) بدل الأدمن — راجع
    # staff/views/inventory.py::update_settings.
    readonly_fields = ('quantity', 'reserved', 'available', 'updated_at', 'min_quantity', 'is_available')
    inlines = [StockMovementInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('inventory', 'unit', 'movement_type', 'quantity', 'created_by', 'created_at')
    list_filter = ('movement_type',)
    readonly_fields = ('inventory', 'unit', 'movement_type', 'quantity', 'note', 'created_by', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
