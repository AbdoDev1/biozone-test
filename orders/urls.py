from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:unit_id>/", views.cart_add, name="cart_add"),
    path("cart/update/<int:unit_id>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:unit_id>/", views.cart_remove, name="cart_remove"),
    path("cart/plus/<int:unit_id>/", views.cart_plus, name="cart_plus"),
    path("cart/minus/<int:unit_id>/", views.cart_minus, name="cart_minus"),
    path("cart/controls/<int:unit_id>/", views.cart_controls, name="cart_controls"),
    path("cart/badge/", views.cart_badge, name="cart_badge"),
    path("carts/new/", views.cart_new, name="cart_new"),
    path("carts/<int:cart_id>/switch/", views.cart_switch, name="cart_switch"),
    path("carts/<int:cart_id>/rename/", views.cart_rename, name="cart_rename"),
    path("carts/<int:cart_id>/delete/", views.cart_delete, name="cart_delete"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/items/", views.order_items, name="order_items"),
    path("orders/<int:pk>/cancel/", views.order_cancel, name="order_cancel"),
    path("orders/<int:pk>/approve-amendment/", views.order_approve_amendment, name="order_approve_amendment"),
    path("orders/<int:pk>/reject-amendment/", views.order_reject_amendment, name="order_reject_amendment"),
]
