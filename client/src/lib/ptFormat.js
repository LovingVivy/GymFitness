// Giờ hiển thị luôn theo giờ phòng tập (Việt Nam), không phụ thuộc máy người xem.
export const GYM_TIME_ZONE = "Asia/Ho_Chi_Minh";

export const WEEKDAYS = [
  { value: 1, short: "T2", long: "Thứ 2" },
  { value: 2, short: "T3", long: "Thứ 3" },
  { value: 3, short: "T4", long: "Thứ 4" },
  { value: 4, short: "T5", long: "Thứ 5" },
  { value: 5, short: "T6", long: "Thứ 6" },
  { value: 6, short: "T7", long: "Thứ 7" },
  { value: 7, short: "CN", long: "Chủ nhật" }
];

export const weekdayShort = (value) => WEEKDAYS.find((day) => day.value === value)?.short ?? "";

export const SESSION_STATUS = {
  REQUESTED: { label: "Đã xác nhận", tone: "is-ok" },
  ACCEPTED: { label: "Đã xác nhận", tone: "is-ok" },
  COMPLETED: { label: "Hoàn thành", tone: "is-ok" },
  NO_SHOW: { label: "Vắng mặt", tone: "is-danger" },
  CANCELLED: { label: "Đã huỷ", tone: "is-muted" },
  REJECTED: { label: "Đã từ chối", tone: "is-muted" },
  EXPIRED: { label: "Hết hạn", tone: "is-muted" }
};

export const isActiveSession = (booking) => ["REQUESTED", "ACCEPTED"].includes(booking.status);

const formatter = (options) => new Intl.DateTimeFormat("vi-VN", { timeZone: GYM_TIME_ZONE, ...options });

const dayFormat = formatter({ weekday: "short", day: "2-digit", month: "2-digit" });
const dateTimeFormat = formatter({
  weekday: "short",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit"
});
const timeFormat = formatter({ hour: "2-digit", minute: "2-digit" });
const dayKeyFormat = formatter({ year: "numeric", month: "2-digit", day: "2-digit" });

const valid = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

export const formatDay = (value) => (valid(value) ? dayFormat.format(valid(value)) : "—");
export const formatDateTime = (value) => (valid(value) ? dateTimeFormat.format(valid(value)) : "—");
export const formatTime = (value) => (valid(value) ? timeFormat.format(valid(value)) : "—");

/** "dd/mm/yyyy" theo giờ phòng tập — dùng làm khoá gom nhóm theo ngày. */
export const dayKey = (value) => (valid(value) ? dayKeyFormat.format(valid(value)) : "");

/** Ngày "YYYY-MM-DD" (giờ phòng tập) → nhãn "T3, 30/09". */
export function formatLocalDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  // Giữa trưa để không lệch ngày dù trình duyệt ở múi giờ nào.
  return dayFormat.format(new Date(Date.UTC(year, month - 1, day, 5)));
}

export const money = (value) => new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + "đ";
