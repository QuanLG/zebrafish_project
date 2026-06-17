from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def registration(request):
    return render(request, 'registration.html')


def login_page(request):
    return render(request, 'login.html')


def user_management_page(request):
    return render(request, 'user_management.html')


urlpatterns = [
    path('', home, name='home'),
    path('register/', registration, name='register'),
    path('login/', login_page, name='login'),
    path('users-manage/', user_management_page, name='user_manage'),
    path('admin/', admin.site.urls),
    path('api/users/', include('user_management.urls')),
    path('multi-stats/', include('multi_stats.urls')),
    path('antioxidant/', include('antioxidant_report.urls')),
    path('tumor/', include('tumor_report.urls')),
    path('ros_iod/', include('ros_iod.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
