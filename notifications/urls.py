from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('bell-data/', views.notification_bell_data, name='bell_data'),
    path('<int:pk>/open/', views.notification_open, name='open'),
    path('mark-all-read/', views.notification_mark_all_read, name='mark_all_read'),
]
