import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    """用户角色枚举"""
    ADMIN = 'admin', _('系统管理员')
    RESEARCHER = 'researcher', _('研究人员')
    OPERATOR = 'operator', _('实验操作员')
    VIEWER = 'viewer', _('只读用户')


class UserStatus(models.TextChoices):
    """用户状态枚举"""
    ACTIVE = 'active', _('正常')
    INACTIVE = 'inactive', _('未激活')
    SUSPENDED = 'suspended', _('已停用')
    PENDING = 'pending', _('待审核')


class CustomUserManager(BaseUserManager):
    """自定义用户管理器"""

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError(_('用户名不能为空'))
        if not email:
            raise ValueError(_('邮箱不能为空'))

        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        extra_fields.setdefault('status', UserStatus.ACTIVE)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('超级用户必须设置 is_staff=True'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('超级用户必须设置 is_superuser=True'))

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    自定义用户模型
    扩展 Django 默认用户，增加角色、部门、状态等字段
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name=_('用户名'),
        help_text=_('必填，150个字符以内，只能包含字母、数字和@/./+/-/_')
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_('邮箱'),
        help_text=_('用于登录和找回密码')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('手机号')
    )
    real_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('真实姓名')
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.OPERATOR,
        verbose_name=_('角色')
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('部门')
    )
    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.PENDING,
        verbose_name=_('状态')
    )
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('头像')
    )
    bio = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('个人简介')
    )

    # Django 权限相关字段
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('职员状态'),
        help_text=_('是否可以登录管理后台')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('是否激活')
    )
    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('注册时间')
    )
    last_login_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('最后登录IP')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('更新时间')
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        verbose_name = _('用户')
        verbose_name_plural = _('用户')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['username'], name='idx_username'),
            models.Index(fields=['email'], name='idx_email'),
            models.Index(fields=['status', 'role'], name='idx_status_role'),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def can_edit(self):
        return self.role in (UserRole.ADMIN, UserRole.RESEARCHER, UserRole.OPERATOR)

    @property
    def can_view(self):
        return self.status == UserStatus.ACTIVE

    def get_full_name(self):
        return self.real_name or self.username

    def get_short_name(self):
        return self.username


class UserLoginLog(models.Model):
    """
    用户登录日志
    记录每次登录的IP、时间、设备信息
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_logs',
        verbose_name=_('用户')
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('IP地址')
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('用户代理')
    )
    login_type = models.CharField(
        max_length=20,
        choices=[
            ('password', _('密码登录')),
            ('token', _('Token登录')),
            ('admin', _('后台登录')),
        ],
        default='password',
        verbose_name=_('登录方式')
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', _('成功')),
            ('failed', _('失败')),
            ('locked', _('账户锁定')),
        ],
        default='success',
        verbose_name=_('登录状态')
    )
    fail_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('失败原因')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('登录时间')
    )

    class Meta:
        db_table = 'user_login_logs'
        verbose_name = _('登录日志')
        verbose_name_plural = _('登录日志')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at'], name='idx_user_login_time'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class UserOperationLog(models.Model):
    """
    用户操作日志
    记录关键操作行为，便于审计
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operation_logs',
        verbose_name=_('操作用户')
    )
    action = models.CharField(
        max_length=50,
        verbose_name=_('操作类型')
    )
    resource_type = models.CharField(
        max_length=50,
        verbose_name=_('资源类型')
    )
    resource_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('资源ID')
    )
    detail = models.JSONField(
        default=dict,
        verbose_name=_('操作详情')
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('IP地址')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('操作时间')
    )

    class Meta:
        db_table = 'user_operation_logs'
        verbose_name = _('操作日志')
        verbose_name_plural = _('操作日志')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} - {self.resource_type} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class UserProfileChangeLog(models.Model):
    """
    用户个人信息修改历史记录
    记录用户每次修改个人信息的详细变更
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='profile_changes',
        verbose_name=_('用户')
    )
    changed_fields = models.JSONField(
        verbose_name=_('变更字段列表')
    )
    old_values = models.JSONField(
        verbose_name=_('修改前的值')
    )
    new_values = models.JSONField(
        verbose_name=_('修改后的值')
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('操作IP地址')
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('用户代理')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('修改时间')
    )

    class Meta:
        db_table = 'user_profile_change_logs'
        verbose_name = _('个人信息修改记录')
        verbose_name_plural = _('个人信息修改记录')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at'], name='idx_user_profile_change'),
        ]

    def __str__(self):
        return f"{self.user.username} - 修改于 {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
