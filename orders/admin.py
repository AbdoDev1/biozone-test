from django.contrib import admin
from .models import Order, OrderItem, OrderLog, SiteConfig


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_unit', 'quantity', 'unit_price')
    can_delete = False


class OrderLogInline(admin.TabularInline):
    model = OrderLog
    extra = 0
    readonly_fields = ('event', 'new_status', 'note', 'created_at', 'created_by')
    can_delete = False
    ordering = ('created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'status', 'total', 'created_at')
    list_filter = ('status',)
    search_fields = ('id', 'client__username')
    inlines = [OrderItemInline, OrderLogInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ('min_order_amount',)

    def has_add_permission(self, request):
        # نمنع إضافة سطر جديد لو موجود واحد فعلاً (Singleton)
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
