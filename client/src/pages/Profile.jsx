import { useEffect, useMemo, useRef, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import TwoFactorCard from "../components/TwoFactorCard";
import {
  logout,
  refreshProfile,
  uploadAvatar,
  useAuth,
  useToken
} from "../lib/authStore";
import { navigateTo } from "../lib/navigation";
import { useObjectUrl } from "../lib/useObjectUrl";
import "./Profile.css";

const formatDate = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric"
  }).format(date);
};

const formatDateTime = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
};

const money = (value) =>
  new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + "đ";

const ACTIVITY_LABELS = { GYM: "Gym", YOGA: "Yoga" };

// Ảnh chụp điện thoại thường 3–10MB: thu nhỏ trước khi gửi để luôn dưới giới hạn 2MB của API.
const MAX_SOURCE_BYTES = 20 * 1024 * 1024;
const AVATAR_MAX_EDGE = 512;

async function resizeAvatar(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("Trình duyệt không đọc được ảnh này, hãy dùng JPG, PNG hoặc WebP.");
  }

  const scale = Math.min(1, AVATAR_MAX_EDGE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();

  // WebP nhỏ hơn; trình duyệt không hỗ trợ xuất WebP sẽ tự trả về PNG nên ép sang JPEG.
  const webp = canvas.toDataURL("image/webp", 0.88);
  return webp.startsWith("data:image/webp") ? webp : canvas.toDataURL("image/jpeg", 0.88);
}

const STATUS_LABELS = {
  ACTIVE: "Đang hoạt động",
  FROZEN: "Đang tạm dừng",
  PENDING: "Chờ thanh toán",
  EXPIRED: "Đã hết hạn",
  CANCELLED: "Đã huỷ"
};

function EmptyProfile() {
  return (
    <main className="profile-page">
      <SiteHeader />
      <section className="profile-empty">
        <span>Member profile</span>
        <h1>Đăng nhập để xem<br /><em>hồ sơ hội viên.</em></h1>
        <p>Thông tin gói tập, lịch tập và lượt PT của bạn được quản lý tại đây.</p>
        <a href="/login">Đăng nhập ngay <b>→</b></a>
      </section>
      <CurtainFooter />
    </main>
  );
}

export default function Profile() {
  const user = useAuth();
  const token = useToken();
  const fileRef = useRef(null);
  const toastTimer = useRef(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  // Ảnh đại diện là tệp riêng tư nên phải tải kèm token.
  const avatarSrc = useObjectUrl(user?.avatarUrl, token);

  useEffect(() => {
    if (!user) return;
    refreshProfile().catch(() => {
      /* lỗi mạng thì giữ dữ liệu đang có */
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => window.clearTimeout(toastTimer.current), []);

  // Liên kết /profile#security từ menu tài khoản: cuộn tới khối bảo mật.
  useEffect(() => {
    if (window.location.hash === "#security") {
      window.setTimeout(() => document.getElementById("security")?.scrollIntoView({ block: "start" }), 120);
    }
  }, []);

  const membership = user?.membership ?? null;
  // Gói còn hiệu lực của loại hình khác (vd. đang có cả Gym và Yoga).
  const otherPlans = (user?.memberships ?? []).filter(
    (item) => item.activityType !== membership?.activityType
  );
  const isMember = user?.role === "USER";

  const progress = useMemo(() => {
    if (!membership?.totalDays || membership.daysRemaining == null) return 0;
    const ratio = membership.daysRemaining / membership.totalDays;
    return Math.max(0, Math.min(360, ratio * 360));
  }, [membership]);

  if (!user) return <EmptyProfile />;

  const initials = (user.fullName || user.email || "?")
    .split(" ")
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  const notify = (message) => {
    setNotice(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setNotice(""), 2600);
  };

  const handleAvatar = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      notify("Vui lòng chọn một tệp ảnh.");
      return;
    }
    if (file.size > MAX_SOURCE_BYTES) {
      notify("Ảnh gốc cần nhỏ hơn 20MB.");
      return;
    }

    setBusy(true);
    try {
      await uploadAvatar(await resizeAvatar(file));
      notify("Đã cập nhật ảnh đại diện.");
    } catch (error) {
      notify(error.message || "Không thể cập nhật ảnh đại diện.");
    } finally {
      setBusy(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigateTo("/");
  };

  return (
    <main className="profile-page">
      <SiteHeader />

      <section className="profile-hero">
        <div className="profile-identity">
          <button
            className="profile-avatar"
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            aria-label="Đổi ảnh đại diện"
          >
            {avatarSrc ? (
              <img src={avatarSrc} alt={user.fullName || "Ảnh đại diện"} />
            ) : (
              <span>{initials}</span>
            )}
            <small>{busy ? "Đang lưu…" : "Đổi ảnh"}</small>
          </button>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleAvatar} hidden />
          <div>
            <p>
              {user.memberCode ? `Hội viên ${user.memberCode}` : "Ironix member"} · {user.role}
            </p>
            <h1>Chào, <em>{user.fullName || user.email}.</em></h1>
            <span>
              {user.email}
              {user.phone ? ` · ${user.phone}` : ""}
            </span>
          </div>
        </div>
        <button className="profile-logout" type="button" onClick={handleLogout}>Đăng xuất</button>
      </section>

      <section className="profile-dashboard">
        {isMember ? (
          <>
          <article className="profile-card membership-overview">
            <header>
              <div><span>01</span><p>Gói hội viên</p></div>
              <b className={membership?.status === "ACTIVE" ? "is-active" : ""}>
                {membership ? STATUS_LABELS[membership.status] ?? membership.status : "Chưa đăng ký"}
              </b>
            </header>

            {membership ? (
              <>
                <div className="membership-name">
                  <div>
                    <small>{membership.category} membership</small>
                    <h2>{membership.name}</h2>
                    <p>{membership.period} · {money(membership.price)}</p>
                  </div>
                  <div className="countdown-ring" style={{ "--progress": progress + "deg" }}>
                    <strong>{membership.daysRemaining ?? "—"}</strong>
                    <span>ngày còn lại</span>
                  </div>
                </div>

                <div className="membership-dates">
                  <div><span>Ngày bắt đầu</span><strong>{formatDate(membership.startAt)}</strong></div>
                  <i>→</i>
                  <div><span>Ngày hết hạn</span><strong>{formatDate(membership.endAt)}</strong></div>
                </div>

                {membership.status === "EXPIRED" ? (
                  <p className="membership-expired">
                    Gói đã hết hạn: bạn tạm thời chưa check-in và đặt PT được. Gia hạn để tiếp tục tập.
                  </p>
                ) : membership.daysRemaining !== null && membership.daysRemaining <= 7 ? (
                  <p className="membership-expired">
                    Gói sắp hết hạn. Gia hạn ngay: ngày của gói mới được cộng nối tiếp, không mất ngày còn lại.
                  </p>
                ) : null}

                {otherPlans.length ? (
                  <ul className="membership-others">
                    {otherPlans.map((item) => (
                      <li key={item.activityType}>
                        <span>{item.category}</span>
                        <strong>{item.name}</strong>
                        <small>còn {item.daysRemaining} ngày · hết hạn {formatDate(item.endAt)}</small>
                      </li>
                    ))}
                  </ul>
                ) : null}

                <div className="membership-actions">
                  {membership.status === "EXPIRED" ? null : <a href="/schedule">Xem lịch tập <b>→</b></a>}
                  <a href="/plans">{membership.status === "EXPIRED" ? "Gia hạn ngay →" : "Gia hạn gói"}</a>
                </div>
              </>
            ) : (
              <div className="membership-empty">
                <h2>Bắt đầu hành trình của bạn.</h2>
                <p>Chọn gói Gym hoặc Yoga để mở lịch tập và QR check-in.</p>
                <a href="/plans">Chọn gói tập →</a>
              </div>
            )}
          </article>

          <article className="profile-card member-overview">
            <header><div><span>02</span><p>Hồ sơ hội viên</p></div><b>Member</b></header>
            <div className="member-code">
              <small>Mã hội viên</small>
              <strong>{user.memberCode || "—"}</strong>
            </div>
            <dl className="member-facts">
              <div><dt>Chi nhánh</dt><dd>{user.homeBranch || "—"}</dd></div>
              <div><dt>Ngày tham gia</dt><dd>{formatDate(user.joinedAt)}</dd></div>
              <div><dt>Đăng nhập gần nhất</dt><dd>{formatDateTime(user.lastLoginAt)}</dd></div>
              <div><dt>Vai trò</dt><dd>{user.role}</dd></div>
            </dl>
          </article>

          <article className="profile-card body-overview">
            <header><div><span>03</span><p>Thông tin thể chất</p></div><b>Profile</b></header>
            <div className="body-stats">
              <div><strong>{user.height ?? "—"}</strong><span>cm</span><small>Chiều cao</small></div>
              <div><strong>{user.weight ?? "—"}</strong><span>kg</span><small>Cân nặng</small></div>
              <div><strong>{user.weeklySessions ?? "—"}</strong><span>buổi</span><small>Mỗi tuần</small></div>
            </div>
            <dl>
              <div><dt>Kinh nghiệm</dt><dd>{user.experience || "Chưa cập nhật"}</dd></div>
              <div><dt>Mục tiêu</dt><dd>{user.goal || "Chưa cập nhật"}</dd></div>
            </dl>
          </article>

          <article className="profile-card plan-detail">
            <header><div><span>04</span><p>Chi tiết gói</p></div><b>Plan</b></header>
            {membership ? (
              <dl className="plan-facts">
                <div><dt>Loại hình</dt><dd>{ACTIVITY_LABELS[membership.activityType] ?? membership.activityType}</dd></div>
                <div><dt>Mã gói</dt><dd>{membership.planCode}</dd></div>
                <div><dt>Thời hạn</dt><dd>{membership.period}</dd></div>
                <div><dt>Tổng số ngày</dt><dd>{membership.totalDays ?? "—"}</dd></div>
                <div><dt>Giá gói</dt><dd>{money(membership.price)}</dd></div>
              </dl>
            ) : (
              <div className="plan-empty">
                <p>Bạn chưa có gói tập nào đang hoạt động.</p>
                <a href="/plans">Chọn gói tập →</a>
              </div>
            )}
          </article>

          </>
        ) : (
          <article className="profile-card member-overview">
            <header><div><span>01</span><p>Tài khoản nhân sự</p></div><b className="is-active">{user.role}</b></header>
            <div className="membership-empty">
              <h2>Khu làm việc của bạn.</h2>
              <p>Tài khoản {user.role === "PT" ? "huấn luyện viên" : "quản trị"} không có gói hội viên. Bảo mật tài khoản nằm ngay bên dưới.</p>
              <a href={user.role === "PT" ? "/pt" : "/admin"}>{user.role === "PT" ? "Buổi dạy" : "Trang quản trị"} →</a>
            </div>
          </article>
        )}

        <TwoFactorCard enabled={user.twoFactorEnabled} notify={notify} />
      </section>

      <CurtainFooter />
      <div className={"profile-toast " + (notice ? "is-visible" : "")}>{notice}</div>
    </main>
  );
}
