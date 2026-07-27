from django.urls import path

from . import views

app_name = 'activity'

urlpatterns = [
    path('note/<str:app_label>/<str:model_name>/<int:object_id>/', views.add_note, name='add_note'),
]
