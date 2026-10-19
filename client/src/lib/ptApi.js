import { request } from "./api";
import { getToken } from "./authStore";

const auth = () => ({ token: getToken() });

// --- Huấn luyện viên -------------------------------------------------------

export const listTrainers = (activityType) =>
  request(`/trainers${activityType ? `?activity_type=${activityType}` : ""}`, auth());

/** PT hội viên đặt được: chuyên môn trùng loại hình (Gym/Yoga) của gói còn hiệu lực. */
export const listBookableTrainers = () => request("/trainers/bookable", auth());

export const getMyTrainerProfile = () => request("/trainers/me", auth());

/** Các ô 60 phút còn trống trong 14 ngày tới của một PT. */
export const listTrainerSlots = (trainerId) => request(`/trainers/${trainerId}/slots`, auth());

// --- Lịch của bạn (PT) ----------------------------------------------------

export const getMySchedule = () => request("/trainers/me/schedule", auth());

export const saveMySchedule = (weekly) =>
  request("/trainers/me/schedule", { method: "PUT", body: { weekly }, ...auth() });

export const addTimeOff = (payload) =>
  request("/trainers/me/time-off", { method: "POST", body: payload, ...auth() });

export const deleteTimeOff = (timeOffId) =>
  request(`/trainers/me/time-off/${timeOffId}`, { method: "DELETE", ...auth() });

// --- Lượt PT ---------------------------------------------------------------

export const getPtCredits = () => request("/pt-credits", auth());

export const purchasePtCredits = (quantity) =>
  request("/pt-credits/purchase", { method: "POST", body: { quantity }, ...auth() });

// --- Buổi PT ---------------------------------------------------------------

export const listMyBookings = () => request("/pt-bookings", auth());

export const listTeachingSessions = () => request("/pt-bookings/teaching", auth());

/** Đặt một ô trống: xác nhận ngay, không chờ PT duyệt. */
export const createBooking = (payload) =>
  request("/pt-bookings", { method: "POST", body: payload, ...auth() });

export const cancelBooking = (bookingId, reason) =>
  request(`/pt-bookings/${bookingId}/cancel`, {
    method: "POST",
    body: { reason: reason || null },
    ...auth()
  });

export const completeBooking = (bookingId) =>
  request(`/pt-bookings/${bookingId}/complete`, { method: "POST", ...auth() });

export const markNoShow = (bookingId) =>
  request(`/pt-bookings/${bookingId}/no-show`, { method: "POST", ...auth() });

// --- Thông báo -------------------------------------------------------------

export const listNotifications = () => request("/notifications", auth());

export const getUnreadCount = () => request("/notifications/unread-count", auth());

export const markNotificationRead = (notificationId) =>
  request(`/notifications/${notificationId}/read`, { method: "POST", ...auth() });

export const markAllNotificationsRead = () =>
  request("/notifications/read-all", { method: "POST", ...auth() });
