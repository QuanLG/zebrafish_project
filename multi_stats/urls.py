from django.urls import path
from . import views

app_name = 'multi_stats'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload'),
    path('sample-data/', views.get_sample_data, name='sample_data'),
    path('comparison-groups/', views.get_comparison_groups, name='comparison_groups'),
    path('update-filter/', views.update_sample_filter, name='update_filter'),
    path('generate-chart/', views.generate_chart, name='generate_chart'),
    path('download-charts/', views.download_charts, name='download_charts'),
]
