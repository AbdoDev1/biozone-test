from django.urls import path
from staff.views import dashboard, inventory, clients, products, orders, accounting

app_name = 'staff'

urlpatterns = [
    path('', dashboard.dashboard, name='dashboard'),
    path('login/', dashboard.staff_login, name='login'),
    path('logout/', dashboard.staff_logout, name='logout'),
    path('inventory/', inventory.inventory_list, name='inventory'),
    path('inventory/<int:pk>/', inventory.inventory_detail, name='inventory_detail'),
    path('inventory/<int:pk>/movement/', inventory.add_movement, name='add_movement'),
    path('clients/', clients.client_list, name='clients'),
    path('clients/<int:pk>/', clients.client_detail, name='client_detail'),
    path('clients/<int:pk>/approve/', clients.client_approve, name='client_approve'),
    path('clients/<int:pk>/reject/', clients.client_reject, name='client_reject'),
    path('clients/<int:pk>/payments/add/', clients.client_add_payment, name='client_add_payment'),
    path('clients/<int:pk>/adjustments/add/', clients.client_add_adjustment, name='client_add_adjustment'),
    path('products/', products.product_list, name='product_list'),
    path('products/add/', products.product_add, name='product_add'),
    path('products/<int:pk>/edit/', products.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', products.product_delete, name='product_delete'),
    path('products/import/', products.import_products, name='import_products'),
    path('products/template/', products.download_template, name='download_template'),
    path('orders/', orders.order_list, name='order_list'),
    path('orders/<int:pk>/', orders.order_detail, name='order_detail'),
    path('accounting/', accounting.accounting_overview, name='accounting_overview'),
    path('accounting/quick-entry/', accounting.accounting_quick_entry, name='accounting_quick_entry'),
    path('accounting/export/', accounting.accounting_export, name='accounting_export'),
]
