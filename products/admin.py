from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Category, Product, ProductUnit
from .forms import BaseProductUnitFormSet


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


class ProductUnitInline(admin.TabularInline):
    model = ProductUnit
    formset = BaseProductUnitFormSet  # نفس فحص الوحدة الكبرى/الصغرى المُصحّح المستخدم في فورم الستاف
    extra = 3
    fields = ('size', 'name', 'qty_in_small', 'unit_price')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'code', 'barcode', 'category', 'manufacturer', 'is_active', 'created_at')
    list_filter = ('category', 'is_active')
    search_fields = ('name_ar', 'name_en', 'manufacturer', 'code', 'barcode')
    inlines = [ProductUnitInline]
