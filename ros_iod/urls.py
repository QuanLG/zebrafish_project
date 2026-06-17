from django.urls import path
from . import views

app_name = 'ros_iod'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload'),
    path('select_folders/', views.select_folders, name='select_folders'),
    path('select_video/', views.select_video, name='select_video'),
    path('select_all/', views.select_all, name='select_all'),   
    path('download/', views.download_results, name='download'),
]
