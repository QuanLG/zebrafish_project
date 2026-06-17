from .models import UserOperationLog, UserLoginLog


def get_client_ip(request):
    """
    从请求中获取客户端真实 IP 地址
    支持 X-Forwarded-For 和 X-Real-IP 代理头
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_operation(user, action, resource_type, resource_id=None, detail=None, request=None):
    """
    记录用户操作日志的便捷函数

    Args:
        user: 操作用户实例，未登录可传 None
        action: 操作类型，如 'user_login', 'analysis_create'
        resource_type: 资源类型，如 'user', 'analysis_result'
        resource_id: 资源标识，可选
        detail: 操作详情字典，可选
        request: HTTP 请求对象，用于获取 IP
    """
    ip = None
    if request:
        ip = get_client_ip(request)

    UserOperationLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        detail=detail or {},
        ip_address=ip
    )


def log_login_attempt(user, request, status, fail_reason=None):
    """
    记录登录尝试日志的便捷函数

    Args:
        user: 用户实例，登录失败时可能为 None
        request: HTTP 请求对象
        status: 登录状态 ('success', 'failed', 'locked')
        fail_reason: 失败原因，可选
    """
    UserLoginLog.objects.create(
        user=user,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        status=status,
        fail_reason=fail_reason
    )
