from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ClientProfile, BusinessTypeSetting


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'status', 'is_active', 'can_access_accounting')
    list_filter = ('role', 'status', 'can_access_accounting')
    list_editable = ('can_access_accounting',)
    fieldsets = UserAdmin.fieldsets + (
        ('بيانات إضافية', {'fields': ('role', 'status', 'can_access_accounting')}),
    )


@admin.register(BusinessTypeSetting)
class BusinessTypeSettingAdmin(admin.ModelAdmin):
    list_display = ('get_business_type_display', 'is_wholesale', 'discount_percent')
    list_editable = ('is_wholesale', 'discount_percent')

    def get_business_type_display(self, obj):
        return obj.get_business_type_display()
    get_business_type_display.short_description = 'نوع النشاط'


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'business_type', 'user', 'phone', 'is_wholesale', 'effective_discount_percent')
    list_filter = ('business_type',)
    fields = (
        'user', 'business_name', 'business_type', 'address', 'phone', 'verified_at',
        'is_wholesale_override', 'custom_discount_percent',
    )

    def is_wholesale(self, obj):
        return obj.is_wholesale
    is_wholesale.boolean = True
    is_wholesale.short_description = 'جملة؟'
