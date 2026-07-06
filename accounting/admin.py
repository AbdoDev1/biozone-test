from django.contrib import admin

from .models import AccountTransaction


@admin.register(AccountTransaction)
class AccountTransactionAdmin(admin.ModelAdmin):
    list_display = ['client', 'kind', 'amount', 'method', 'invoice', 'created_by', 'created_at']
    list_filter = ['kind', 'method', 'created_at']
    search_fields = ['client__username', 'note', 'invoice__invoice_number']
    autocomplete_fields = ['client', 'invoice']
    readonly_fields = ['created_at']
