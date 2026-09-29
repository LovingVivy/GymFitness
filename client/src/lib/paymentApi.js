import { request } from "./api";
import { getToken } from "./authStore";

const auth = () => ({ token: getToken() });

/** Thông tin chuyển khoản QR và trạng thái hiện tại của một payment. */
export const getCheckout = (paymentId) => request(`/payments/${paymentId}`, auth());

/**
 * Chỉ dùng khi backend bật giả lập (môi trường dev): đánh dấu đã nhận tiền
 * mà không cần chuyển khoản thật. Ở production backend trả 403.
 */
export const simulatePaid = (paymentId) =>
  request(`/payments/${paymentId}/mark-paid`, { method: "POST", ...auth() });
