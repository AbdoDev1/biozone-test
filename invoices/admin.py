from django.contrib import admin
from .models import Invoice, InvoiceItem, InvoiceSequence


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    can_delete = False
    readonly_fields = ['product_name', 'unit_name', 'quantity', 'unit_price']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'order', 'client_name', 'total', 'issued_by', 'issued_at']
    search_fields = ['invoice_number', 'client_name', 'client_business_name', 'order__id']
    list_filter = ['issued_at']
    inlines = [InvoiceItemInline]
    readonly_fields = [f.name for f in Invoice._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(admin.ModelAdmin):
    list_display = ['year', 'last_number']
    readonly_fields = ['year', 'last_number']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
