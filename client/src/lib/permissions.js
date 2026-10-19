/**
 * Role permissions (RBAC) as sent by the backend in the profile/login response.
 *
 * The frontend only uses them to show or hide screens and buttons; the
 * backend checks every request again, so hiding a button is not security.
 */
export const P = {
  DASHBOARD_VIEW: "dashboard:view",
  REPORTS_VIEW: "reports:view",
  REPORTS_EXPORT: "reports:export",
  USERS_VIEW: "users:view",
  USERS_MANAGE_MEMBERS: "users:manage_members",
  USERS_MANAGE_STAFF: "users:manage_staff",
  USERS_DELETE: "users:delete",
  PLANS_VIEW: "plans:view",
  PLANS_MANAGE: "plans:manage",
  CHECKINS_VIEW: "checkins:view",
  CHECKINS_MANAGE: "checkins:manage",
  PAYMENTS_VIEW: "payments:view",
  PAYMENTS_CONFIRM: "payments:confirm",
  PAYMENTS_VOID: "payments:void",
  PRODUCTS_VIEW: "products:view",
  PRODUCTS_MANAGE: "products:manage",
  AUDIT_VIEW: "audit:view"
};

export const can = (user, permission) => Boolean(user?.permissions?.includes(permission));

export const ROLE_LABELS = {
  USER: "Hội viên",
  PT: "Huấn luyện viên",
  MANAGER: "Quản lý",
  ADMIN: "Quản trị"
};
