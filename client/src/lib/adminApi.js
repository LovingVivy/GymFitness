import { download, request, upload } from "./api";
import { getToken } from "./authStore";

const auth = () => ({ token: getToken() });

const query = (params) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== false) {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
};

export const getOverview = () => request("/admin/overview", auth());

// --- Tài khoản ---------------------------------------------------------------

export const listUsers = (params) => request(`/admin/users${query(params)}`, auth());

export const createUser = (payload) =>
  request("/admin/users", { method: "POST", body: payload, ...auth() });

export const updateUser = (userId, payload) =>
  request(`/admin/users/${userId}`, { method: "PATCH", body: payload, ...auth() });

export const resetPassword = (userId, password) =>
  request(`/admin/users/${userId}/password`, { method: "POST", body: { password }, ...auth() });

export const deleteUser = (userId) =>
  request(`/admin/users/${userId}`, { method: "DELETE", ...auth() });

// --- Gói tập -----------------------------------------------------------------

export const listAdminPlans = () => request("/admin/plans", auth());

export const createPlan = (payload) =>
  request("/admin/plans", { method: "POST", body: payload, ...auth() });

export const updatePlan = (planId, payload) =>
  request(`/admin/plans/${planId}`, { method: "PUT", body: payload, ...auth() });

export const deletePlan = (planId) =>
  request(`/admin/plans/${planId}`, { method: "DELETE", ...auth() });

// --- Ra vào ------------------------------------------------------------------

export const listCheckins = (params) => request(`/admin/checkins${query(params)}`, auth());

export const createCheckin = (identifier) =>
  request("/admin/checkins", { method: "POST", body: { identifier }, ...auth() });

export const checkout = (checkinId) =>
  request(`/admin/checkins/${checkinId}/checkout`, { method: "POST", ...auth() });

// --- Doanh thu ---------------------------------------------------------------

export const getRevenue = (period) => request(`/admin/revenue${query({ period })}`, auth());

// --- Xuất dữ liệu (chạy nền) và tải file ------------------------------------

export const startExport = (report, format, filters = {}) =>
  request("/admin/exports", { method: "POST", body: { report, format, filters }, ...auth() });

export const getJob = (jobId) => request(`/admin/jobs/${jobId}`, auth());

export const downloadFile = (url, fallbackName) =>
  download(url, { token: getToken(), fallbackName });

export const downloadInvoice = (paymentId) =>
  download(`/payments/${paymentId}/invoice`, { token: getToken(), fallbackName: "hoa-don.pdf" });

// --- Nhật ký thao tác ---------------------------------------------------------

export const listAuditLogs = (params) => request(`/admin/audit-logs${query(params)}`, auth());

export const getMemberGrowth = (period) =>
  request(`/admin/members/growth${query({ period })}`, auth());

// --- Thanh toán --------------------------------------------------------------

export const listPayments = (params) => request(`/admin/payments${query(params)}`, auth());

export const confirmPayment = (paymentId, method) =>
  request(`/admin/payments/${paymentId}/confirm`, { method: "POST", body: { method }, ...auth() });

export const voidPayment = (paymentId, reason) =>
  request(`/admin/payments/${paymentId}/void`, { method: "POST", body: { reason }, ...auth() });

// --- Cửa hàng ----------------------------------------------------------------

export const listAdminProducts = (params) => request(`/admin/products${query(params)}`, auth());

export const createProduct = (payload) =>
  request("/admin/products", { method: "POST", body: payload, ...auth() });

export const updateProduct = (productId, payload) =>
  request(`/admin/products/${productId}`, { method: "PUT", body: payload, ...auth() });

export const deleteProduct = (productId) =>
  request(`/admin/products/${productId}`, { method: "DELETE", ...auth() });

export const importProducts = (file) => upload("/admin/products/import", file, auth());

export const downloadImportTemplate = (format) =>
  download(`/admin/products/import-template${query({ format })}`, {
    token: getToken(),
    fallbackName: `mau-nhap-san-pham.${format}`
  });
