import re
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from .models import UserRole, UserStatus, UserLoginLog, UserOperationLog, UserProfileChangeLog

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
        help_text=_('密码必须至少8位，包含字母和数字')
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text=_('确认密码')
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'phone', 'real_name', 'department', 'bio'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'phone': {'required': False},
            'real_name': {'required': False},
            'department': {'required': False},
            'bio': {'required': False},
        }

    def validate_username(self, value):
        if not re.match(r'^[\w.@+-]+$', value):
            raise serializers.ValidationError(_('用户名只能包含字母、数字和 @/./+/-/_'))
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(_('该用户名已被注册'))
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_('该邮箱已被注册'))
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': _('两次输入的密码不一致')})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            status=UserStatus.PENDING,
            **validated_data
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """用户登录序列化器"""
    username = serializers.CharField(required=True, help_text=_('用户名或邮箱'))
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )


class UserSerializer(serializers.ModelSerializer):
    """用户信息序列化器（用于列表和详情）"""
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    date_joined = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'real_name',
            'role', 'role_display', 'department',
            'status', 'status_display', 'avatar', 'bio',
            'is_staff', 'is_active', 'date_joined', 'updated_at',
            'last_login_ip'
        ]
        read_only_fields = ['id', 'date_joined', 'updated_at', 'last_login_ip']


class UserUpdateSerializer(serializers.ModelSerializer):
    """用户信息更新序列化器（普通用户自用）"""
    
    class Meta:
        model = User
        fields = [
            'email', 'phone', 'real_name',
            'department', 'avatar', 'bio'
        ]

    def validate_email(self, value):
        """验证邮箱格式和唯一性"""
        # 邮箱格式验证
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise serializers.ValidationError(_('请输入有效的邮箱地址'))
        
        # 邮箱唯一性验证（排除当前用户）
        user = self.context['request'].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError(_('该邮箱已被其他用户使用'))
        return value

    def validate_phone(self, value):
        """验证手机号格式"""
        if value:
            # 中国大陆手机号格式验证
            phone_pattern = r'^1[3-9]\d{9}$'
            if not re.match(phone_pattern, value):
                raise serializers.ValidationError(_('请输入有效的手机号码'))
        return value

    def validate_real_name(self, value):
        """验证真实姓名"""
        if value:
            # 只允许中文、英文和空格
            name_pattern = r'^[\u4e00-\u9fa5a-zA-Z\s]+$'
            if not re.match(name_pattern, value):
                raise serializers.ValidationError(_('姓名只能包含中文、英文和空格'))
            if len(value) > 50:
                raise serializers.ValidationError(_('姓名长度不能超过50个字符'))
        return value

    def validate_avatar(self, value):
        """验证头像文件"""
        if value:
            # 文件大小限制（5MB）
            max_size = 5 * 1024 * 1024
            if value.size > max_size:
                raise serializers.ValidationError(_('头像文件大小不能超过5MB'))
            
            # 文件类型限制
            allowed_types = ['image/jpeg', 'image/png', 'image/gif']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(_('头像只支持 JPG、PNG、GIF 格式'))
        return value

    def validate_bio(self, value):
        """验证个人简介"""
        if value and len(value) > 500:
            raise serializers.ValidationError(_('个人简介不能超过500个字符'))
        return value


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """管理员更新用户信息序列化器"""
    class Meta:
        model = User
        fields = [
            'email', 'phone', 'real_name',
            'role', 'department', 'status',
            'avatar', 'bio', 'is_staff', 'is_active'
        ]

    def validate_role(self, value):
        request_user = self.context['request'].user
        if value == UserRole.ADMIN and not request_user.is_superuser:
            raise serializers.ValidationError(_('只有超级管理员可以分配管理员角色'))
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """密码修改序列化器"""
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('原密码不正确'))
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': _('两次输入的新密码不一致')})
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """密码重置请求序列化器"""
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """密码重置确认序列化器"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': _('两次输入的新密码不一致')})
        return attrs


class UserListQuerySerializer(serializers.Serializer):
    """用户列表查询参数序列化器"""
    role = serializers.ChoiceField(
        choices=UserRole.choices,
        required=False,
        help_text=_('按角色筛选')
    )
    status = serializers.ChoiceField(
        choices=UserStatus.choices,
        required=False,
        help_text=_('按状态筛选')
    )
    keyword = serializers.CharField(
        required=False,
        help_text=_('用户名/邮箱/真实姓名关键词')
    )
    ordering = serializers.ChoiceField(
        choices=['date_joined', '-date_joined', 'username', '-username'],
        required=False,
        default='-date_joined'
    )


class UserLoginLogSerializer(serializers.ModelSerializer):
    """登录日志序列化器"""
    login_type_display = serializers.CharField(source='get_login_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = UserLoginLog
        fields = [
            'id', 'ip_address', 'user_agent',
            'login_type', 'login_type_display',
            'status', 'status_display', 'fail_reason', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 手动处理 user 字段，避免 PrimaryKeyRelatedField 的 UUID 转换错误
        try:
            if instance.user_id and instance.user:
                data['username'] = instance.user.username
                data['user_id'] = str(instance.user.id)
            else:
                data['username'] = None
                data['user_id'] = None
        except Exception:
            data['username'] = None
            data['user_id'] = None
        return data


class UserOperationLogSerializer(serializers.ModelSerializer):
    """操作日志序列化器"""
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = UserOperationLog
        fields = [
            'id', 'action', 'resource_type',
            'resource_id', 'detail', 'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if instance.user_id and instance.user:
                data['username'] = instance.user.username
                data['user_id'] = str(instance.user.id)
            else:
                data['username'] = None
                data['user_id'] = None
        except Exception:
            data['username'] = None
            data['user_id'] = None
        return data


class UserProfileChangeLogSerializer(serializers.ModelSerializer):
    """用户个人信息修改历史记录序列化器"""
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = UserProfileChangeLog
        fields = [
            'id', 'changed_fields',
            'old_values', 'new_values',
            'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if instance.user_id and instance.user:
                data['username'] = instance.user.username
                data['user_id'] = str(instance.user.id)
            else:
                data['username'] = None
                data['user_id'] = None
        except Exception:
            data['username'] = None
            data['user_id'] = None
        return data
