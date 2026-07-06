from django.urls import path
from . import views

app_name = 'invoices'

urlpatterns = [
    path('<int:pk>/print/', views.invoice_print, name='print'),
]
