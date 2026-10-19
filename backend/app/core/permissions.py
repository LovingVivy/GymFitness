"""Role-based access control: which role may open which screen and do which action.

Routes declare the permission they need (``PermissionDep("payments:void")``);
services add data-level rules on top, e.g. a manager may only edit member
accounts. The same permission list is sent to the frontend, which uses it only
to hide screens and buttons — the backend stays the one that enforces it.
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    # Màn hình tổng quan và báo cáo
    DASHBOARD_VIEW = "dashboard:view"
    REPORTS_VIEW = "reports:view"
    REPORTS_EXPORT = "reports:export"
    # Tài khoản
    USERS_VIEW = "users:view"
    USERS_MANAGE_MEMBERS = "users:manage_members"
    USERS_MANAGE_STAFF = "users:manage_staff"
    USERS_DELETE = "users:delete"
    # Gói tập
    PLANS_VIEW = "plans:view"
    PLANS_MANAGE = "plans:manage"
    # Ra vào
    CHECKINS_VIEW = "checkins:view"
    CHECKINS_MANAGE = "checkins:manage"
    # Thanh toán
    PAYMENTS_VIEW = "payments:view"
    PAYMENTS_CONFIRM = "payments:confirm"
    PAYMENTS_VOID = "payments:void"
    # Cửa hàng
    PRODUCTS_VIEW = "products:view"
    PRODUCTS_MANAGE = "products:manage"
    # Nhật ký thao tác
    AUDIT_VIEW = "audit:view"


_MANAGER = frozenset(
    {
        Permission.DASHBOARD_VIEW,
        Permission.REPORTS_VIEW,
        Permission.REPORTS_EXPORT,
        Permission.USERS_VIEW,
        Permission.USERS_MANAGE_MEMBERS,
        Permission.PLANS_VIEW,
        Permission.CHECKINS_VIEW,
        Permission.CHECKINS_MANAGE,
        Permission.PAYMENTS_VIEW,
        Permission.PAYMENTS_CONFIRM,
        Permission.PRODUCTS_VIEW,
        Permission.PRODUCTS_MANAGE,
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "ADMIN": frozenset(Permission),
    "MANAGER": _MANAGER,
    "PT": frozenset(),
    "USER": frozenset(),
}

# Vai trò quản lý được tạo/sửa bởi người có quyền tương ứng.
MEMBER_ROLES = frozenset({"USER"})
STAFF_ROLES = frozenset({"PT", "MANAGER", "ADMIN"})


def permissions_for(role: str | None) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role or "", frozenset())


def has_permission(role: str | None, permission: Permission | str) -> bool:
    return Permission(permission) in permissions_for(role)


def can_manage_account(actor_role: str | None, target_role: str) -> bool:
    """Data-level rule: staff accounts are reserved for whoever may manage staff."""
    needed = (
        Permission.USERS_MANAGE_STAFF
        if target_role in STAFF_ROLES
        else Permission.USERS_MANAGE_MEMBERS
    )
    return has_permission(actor_role, needed)


def sorted_permissions(role: str | None) -> list[str]:
    return sorted(permission.value for permission in permissions_for(role))
