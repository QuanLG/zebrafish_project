from django.urls import path
from . import views

app_name = 'antioxidant_report'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload'),
    path('save-config/', views.save_config, name='save_config'),
    path('update-filter/', views.update_filter, name='update_filter'),
    path('run-statistics/', views.run_statistics, name='run_statistics'),
    path('update-conclusion/', views.update_conclusion, name='update_conclusion'),
    path('merge-and-generate/', views.merge_and_generate, name='merge_and_generate'),
    path('download/', views.download_results, name='download'),
]
