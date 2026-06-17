from rest_framework import permissions
from .models import UserRole


class IsAdmin(permissions.BasePermission):
    """仅系统管理员可访问"""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_admin
        )


class IsResearcherOrAbove(permissions.BasePermission):
    """研究人员及以上角色可访问"""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in (UserRole.ADMIN, UserRole.RESEARCHER)
        )


class IsOperatorOrAbove(permissions.BasePermission):
    """实验操作员及以上角色可访问"""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in (UserRole.ADMIN, UserRole.RESEARCHER, UserRole.OPERATOR)
        )


class IsActiveUser(permissions.BasePermission):
    """仅激活状态用户可访问"""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.can_view
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """对象所有者或管理员可访问"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        return obj == request.user


class ReadOnly(permissions.BasePermission):
    """只读权限"""
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class IsAdminOrReadOnly(permissions.BasePermission):
    """管理员可写，其他只读"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_admin
        )
