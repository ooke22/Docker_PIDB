from django.urls import path
from . import views

urlpatterns = [
    path('processes/', views.process_upload, name='proessupload'),
    path('get_processes/', views.get_processes, name='getprocesses'),
    path('view_processes/', views.view_processes, name='viewprocess'),
    path('delete/<str:process_id>/', views.delete_processes, name='deleteprocess'),
    path('update/<str:process_id>/', views.update_process, name='updateprocess')
]