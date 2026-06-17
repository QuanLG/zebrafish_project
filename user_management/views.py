import logging
from django.contrib.auth import authenticate, get_user_model, login as django_login
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.utils.dateformat import format as date_format
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework.pagination import PageNumberPagination

from .models import UserRole, UserStatus, UserLoginLog, UserOperationLog, UserProfileChangeLog
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    AdminUserUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserListQuerySerializer,
    UserLoginLogSerializer,
    UserProfileChangeLogSerializer,
    UserOperationLogSerializer,
)
from .permissions import IsAdmin, IsActiveUser, IsOwnerOrAdmin
from .utils import get_client_ip, log_operation, log_login_attempt

logger = logging.getLogger(__name__)
User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    """标准分页器"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_tokens_for_user(user):
    """为指定用户生成 JWT Token 对"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(APIView):
    """
    用户注册接口
    POST /api/users/register/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            log_operation(
                user=user,
                action='user_register',
                resource_type='user',
                resource_id=str(user.id),
                detail={'username': user.username, 'email': user.email},
                request=request
            )
            return Response({
                'code': 201,
                'message': '注册成功，请等待管理员审核激活',
                'data': {
                    'user_id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'status': user.status,
                }
            }, status=status.HTTP_201_CREATED)
        return Response({
            'code': 400,
            'message': '注册失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    用户登录接口
    POST /api/users/login/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'code': 400,
                'message': '参数错误',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # 支持用户名或邮箱登录
        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:
            # 尝试用邮箱登录
            try:
                user_by_email = User.objects.get(email=username)
                user = authenticate(
                    request,
                    username=user_by_email.username,
                    password=password
                )
            except User.DoesNotExist:
                pass

        if user is None:
            log_login_attempt(None, request, 'failed', '用户名或密码错误')
            return Response({
                'code': 401,
                'message': '用户名或密码错误'
            }, status=status.HTTP_401_UNAUTHORIZED)

        if user.status == UserStatus.SUSPENDED:
            log_login_attempt(user, request, 'locked', '账户已停用')
            return Response({
                'code': 403,
                'message': '账户已停用，请联系管理员'
            }, status=status.HTTP_403_FORBIDDEN)

        if user.status == UserStatus.PENDING:
            log_login_attempt(user, request, 'failed', '账户待审核')
            return Response({
                'code': 403,
                'message': '账户待审核，请等待管理员激活'
            }, status=status.HTTP_403_FORBIDDEN)

        # 更新登录信息
        user.last_login = timezone.now()
        user.last_login_ip = get_client_ip(request)
        user.save(update_fields=['last_login', 'last_login_ip'])

        # 创建 Django Session（浏览器可直接访问 API）
        django_login(request, user)

        # 记录登录日志
        log_login_attempt(user, request, 'success')

        tokens = get_tokens_for_user(user)
        log_operation(
            user=user,
            action='user_login',
            resource_type='user',
            resource_id=str(user.id),
            detail={'ip': user.last_login_ip},
            request=request
        )

        return Response({
            'code': 200,
            'message': '登录成功',
            'data': {
                'user': UserSerializer(user).data,
                'tokens': tokens
            }
        })


class LogoutView(APIView):
    """
    用户登出接口
    POST /api/users/logout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception as e:
            logger.warning(f"Token 黑名单失败: {e}")

        log_operation(
            user=request.user,
            action='user_logout',
            resource_type='user',
            resource_id=str(request.user.id),
            request=request
        )
        return Response({
            'code': 200,
            'message': '登出成功'
        })


class CurrentUserView(APIView):
    """
    获取当前登录用户信息
    GET /api/users/me/
    """
    permission_classes = [permissions.IsAuthenticated, IsActiveUser]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({
            'code': 200,
            'data': serializer.data
        })

    def patch(self, request):
        """更新当前用户信息"""
        # 记录修改前的值用于日志
        user = request.user
        old_data = {
            'email': user.email,
            'phone': user.phone,
            'real_name': user.real_name,
            'department': user.department,
            'bio': user.bio
        }
        
        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response({
                'code': 400,
                'message': '更新失败',
                'errors': serializer.errors,
                'timestamp': date_format(timezone.now(), 'Y-m-d H:i:s')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                serializer.save()
                
                # 记录修改后的值
                updated_user = User.objects.get(pk=user.pk)
                new_data = {
                    'email': updated_user.email,
                    'phone': updated_user.phone,
                    'real_name': updated_user.real_name,
                    'department': updated_user.department,
                    'bio': updated_user.bio
                }
                
                # 生成详细的变更记录
                changes = {}
                changed_fields = []
                old_values = {}
                new_values = {}
                
                for field in old_data:
                    if old_data[field] != new_data[field]:
                        changes[field] = {
                            'old_value': old_data[field],
                            'new_value': new_data[field]
                        }
                        changed_fields.append(field)
                        old_values[field] = old_data[field]
                        new_values[field] = new_data[field]
                
                # 记录用户信息修改历史
                UserProfileChangeLog.objects.create(
                    user=updated_user,
                    changed_fields=changed_fields,
                    old_values=old_values,
                    new_values=new_values,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                
                # 记录操作日志
                log_operation(
                    user=updated_user,
                    action='user_update_profile',
                    resource_type='user',
                    resource_id=str(updated_user.id),
                    detail={
                        'fields': list(request.data.keys()),
                        'changes': changes,
                        'ip_address': get_client_ip(request)
                    },
                    request=request
                )
                
                return Response({
                    'code': 200,
                    'message': '个人信息更新成功',
                    'data': UserSerializer(updated_user).data,
                    'timestamp': date_format(timezone.now(), 'Y-m-d H:i:s'),
                    'updated_fields': changed_fields,
                    'changes': changes
                })
        
        except Exception as e:
            logger.error(f'用户 {user.username} 更新个人信息失败: {str(e)}')
            return Response({
                'code': 500,
                'message': '更新失败，服务器内部错误',
                'detail': str(e),
                'timestamp': date_format(timezone.now(), 'Y-m-d H:i:s')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordChangeView(APIView):
    """
    修改密码接口
    POST /api/users/me/password/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            log_operation(
                user=request.user,
                action='user_change_password',
                resource_type='user',
                resource_id=str(request.user.id),
                request=request
            )
            return Response({
                'code': 200,
                'message': '密码修改成功，请使用新密码重新登录'
            })
        return Response({
            'code': 400,
            'message': '密码修改失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserListView(generics.ListAPIView):
    """
    用户列表接口（管理员）
    GET /api/users/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = User.objects.all()
        query_serializer = UserListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=False)
        filters = query_serializer.validated_data

        if filters.get('role'):
            queryset = queryset.filter(role=filters['role'])
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        if filters.get('keyword'):
            keyword = filters['keyword']
            queryset = queryset.filter(
                Q(username__icontains=keyword) |
                Q(email__icontains=keyword) |
                Q(real_name__icontains=keyword)
            )
        ordering = filters.get('ordering', '-date_joined')
        return queryset.order_by(ordering)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({
            'code': 200,
            'data': response.data
        })


class UserDetailView(APIView):
    """
    用户详情与管理接口（管理员）
    GET    /api/users/<id>/
    PATCH  /api/users/<id>/
    DELETE /api/users/<id>/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({
                'code': 404,
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'code': 200,
            'data': UserSerializer(user).data
        })

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({
                'code': 404,
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUserUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            log_operation(
                user=request.user,
                action='admin_update_user',
                resource_type='user',
                resource_id=str(user.id),
                detail={'updated_fields': list(request.data.keys())},
                request=request
            )
            return Response({
                'code': 200,
                'message': '用户信息更新成功',
                'data': UserSerializer(user).data
            })
        return Response({
            'code': 400,
            'message': '更新失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({
                'code': 404,
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        if user.is_superuser:
            return Response({
                'code': 403,
                'message': '不能删除超级管理员账户'
            }, status=status.HTTP_403_FORBIDDEN)

        user_id = str(user.id)
        username = user.username
        user.delete()
        log_operation(
            user=request.user,
            action='admin_delete_user',
            resource_type='user',
            resource_id=user_id,
            detail={'deleted_username': username},
            request=request
        )
        return Response({
            'code': 200,
            'message': '用户已删除'
        })


class UserStatusUpdateView(APIView):
    """
    批量更新用户状态（管理员）
    POST /api/users/batch-status/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        user_ids = request.data.get('user_ids', [])
        new_status = request.data.get('status')

        if not user_ids or new_status not in dict(UserStatus.choices):
            return Response({
                'code': 400,
                'message': '参数错误：需要提供 user_ids 和有效的 status'
            }, status=status.HTTP_400_BAD_REQUEST)

        updated = User.objects.filter(id__in=user_ids).exclude(is_superuser=True).update(status=new_status)
        log_operation(
            user=request.user,
            action='admin_batch_update_status',
            resource_type='user',
            detail={'user_ids': user_ids, 'new_status': new_status, 'count': updated},
            request=request
        )
        return Response({
            'code': 200,
            'message': f'已更新 {updated} 个用户的状态',
            'data': {'updated_count': updated}
        })


class LoginLogListView(generics.ListAPIView):
    """
    登录日志列表（管理员或本人）
    GET /api/users/login-logs/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserLoginLogSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return UserLoginLog.objects.all().order_by('-created_at')
        return UserLoginLog.objects.filter(user=user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'count': response.data.get('count', 0),
                'next': response.data.get('next'),
                'previous': response.data.get('previous'),
                'results': response.data.get('results', [])
            },
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })


class OperationLogListView(generics.ListAPIView):
    """
    操作日志列表（仅管理员）
    GET /api/users/operation-logs/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    serializer_class = UserOperationLogSerializer
    pagination_class = StandardResultsSetPagination
    queryset = UserOperationLog.objects.all().order_by('-created_at')

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'count': response.data.get('count', 0),
                'next': response.data.get('next'),
                'previous': response.data.get('previous'),
                'results': response.data.get('results', [])
            },
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })


class ProfileChangeLogListView(generics.ListAPIView):
    """
    用户个人信息修改历史记录（管理员或本人）
    GET /api/users/profile-change-logs/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileChangeLogSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return UserProfileChangeLog.objects.all().order_by('-created_at')
        return UserProfileChangeLog.objects.filter(user=user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'count': response.data.get('count', 0),
                'next': response.data.get('next'),
                'previous': response.data.get('previous'),
                'results': response.data.get('results', [])
            },
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })


class TokenRefreshView(APIView):
    """
    Token 刷新接口（兼容 simplejwt 的封装）
    POST /api/users/token/refresh/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        if serializer.is_valid():
            return Response({
                'code': 200,
                'message': 'Token 刷新成功',
                'data': serializer.validated_data
            })
        return Response({
            'code': 401,
            'message': 'Token 无效或已过期',
            'errors': serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)
