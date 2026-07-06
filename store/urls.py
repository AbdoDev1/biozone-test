from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.store_home, name='home'),
    path('search/', views.store_search, name='search'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
]
