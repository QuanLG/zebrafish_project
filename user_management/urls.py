from django.urls import path
from . import views

app_name = 'user_management'

urlpatterns = [
    # 认证相关
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token_refresh'),

    # 当前用户
    path('me/', views.CurrentUserView.as_view(), name='current_user'),
    path('me/password/', views.PasswordChangeView.as_view(), name='change_password'),

    # 用户管理（管理员）
    path('', views.UserListView.as_view(), name='user_list'),
    # ⚠️ 固定路径必须放在 <str:pk>/ 前面，否则会被当作 UUID 捕获
    path('batch-status/', views.UserStatusUpdateView.as_view(), name='batch_status'),
    path('login-logs/', views.LoginLogListView.as_view(), name='login_logs'),
    path('operation-logs/', views.OperationLogListView.as_view(), name='operation_logs'),
    path('profile-change-logs/', views.ProfileChangeLogListView.as_view(), name='profile_change_logs'),
    # ⚠️ 通配符路径放最后
    path('<str:pk>/', views.UserDetailView.as_view(), name='user_detail'),
]
