from django.urls import path

from . import views

app_name = 'tags'

urlpatterns = [
    path('add/<str:app_label>/<str:model_name>/<int:object_id>/', views.tag_add, name='tag_add'),
    path('remove/<str:app_label>/<str:model_name>/<int:object_id>/<int:tag_id>/', views.tag_remove, name='tag_remove'),
]
