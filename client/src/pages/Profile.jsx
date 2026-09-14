import { useMemo, useRef, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { logout, updateCurrentUser, useAuth } from "../lib/authStore";
import { navigateTo } from "../lib/navigation";
import "./Profile.css";

const formatDate = (value) =>
  new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
    .format(new Date(value));

const money = (value) => new Intl.NumberFormat("vi-VN").format(value || 0) + "đ";

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
  const fileRef = useRef(null);
  const [notice, setNotice] = useState("");

  const daysRemaining = useMemo(() => {
    if (!user?.membership?.endDate) return 0;
    const end = new Date(user.membership.endDate + "T23:59:59");
    return Math.max(0, Math.ceil((end - new Date()) / 86400000));
  }, [user]);

  const membershipProgress = useMemo(() => {
    if (!user?.membership) return 0;
    const start = new Date(user.membership.startDate + "T00:00:00");
    const end = new Date(user.membership.endDate + "T23:59:59");
    const totalDays = Math.max(1, (end - start) / 86400000);
    return Math.max(0, Math.min(360, (daysRemaining / totalDays) * 360));
  }, [daysRemaining, user]);

  if (!user) return <EmptyProfile />;

  const membership = user.membership;
  const pt = user.ptCredits || { purchased: 0, reserved: 0, used: 0, remaining: 0 };
  const initials = user.fullName.split(" ").slice(-2).map((part) => part[0]).join("").toUpperCase();

  const handleAvatar = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setNotice("Ảnh cần nhỏ hơn 2MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      updateCurrentUser({ avatar: reader.result });
      setNotice("Đã cập nhật ảnh đại diện.");
      window.setTimeout(() => setNotice(""), 2400);
    };
    reader.readAsDataURL(file);
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
          <button className="profile-avatar" type="button" onClick={() => fileRef.current?.click()} aria-label="Đổi ảnh đại diện">
            {user.avatar ? <img src={user.avatar} alt={user.fullName} /> : <span>{initials}</span>}
            <small>Đổi ảnh</small>
          </button>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleAvatar} hidden />
          <div>
            <p>Ironix member · {user.role}</p>
            <h1>Chào, <em>{user.fullName}.</em></h1>
            <span>{user.email} · {user.phone}</span>
          </div>
        </div>
        <button className="profile-logout" type="button" onClick={handleLogout}>Đăng xuất</button>
      </section>

      <section className="profile-dashboard">
        <article className="profile-card membership-overview">
          <header>
            <div><span>01</span><p>Gói hội viên</p></div>
            <b className={membership ? "is-active" : ""}>{membership ? "Đang hoạt động" : "Chưa đăng ký"}</b>
          </header>
          {membership ? (
            <>
              <div className="membership-name">
                <div>
                  <small>{membership.category} membership</small>
                  <h2>{membership.name}</h2>
                  <p>{membership.period} · {money(membership.price)}</p>
                </div>
                <div className="countdown-ring" style={{ "--progress": membershipProgress + "deg" }}>
                  <strong>{daysRemaining}</strong><span>ngày còn lại</span>
                </div>
              </div>
              <div className="membership-dates">
                <div><span>Ngày bắt đầu</span><strong>{formatDate(membership.startDate)}</strong></div>
                <i>→</i>
                <div><span>Ngày hết hạn</span><strong>{formatDate(membership.endDate)}</strong></div>
              </div>
              <div className="membership-actions">
                <a href="/schedule">Xem lịch tập <b>→</b></a>
                <a href="/plans">Gia hạn gói</a>
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

        <article className="profile-card pt-overview">
          <header><div><span>02</span><p>PT của tôi</p></div><b>200K / buổi</b></header>
          <div className="pt-total"><strong>{pt.purchased}</strong><span>buổi PT<br />đã đăng ký</span></div>
          <div className="pt-breakdown">
            <div><span>Còn lại</span><strong>{pt.remaining}</strong></div>
            <div><span>Đã dùng</span><strong>{pt.used}</strong></div>
            <div><span>Đang giữ</span><strong>{pt.reserved}</strong></div>
          </div>
          <a href={pt.remaining ? "/schedule" : "/plans"}>
            {pt.remaining ? "Đặt lịch cùng PT" : "Mua thêm buổi PT"} <b>→</b>
          </a>
        </article>

        <article className="profile-card body-overview">
          <header><div><span>03</span><p>Thông tin thể chất</p></div><b>Profile</b></header>
          <div className="body-stats">
            <div><strong>{user.height || "—"}</strong><span>cm</span><small>Chiều cao</small></div>
            <div><strong>{user.weight || "—"}</strong><span>kg</span><small>Cân nặng</small></div>
            <div><strong>{user.weeklySessions || "—"}</strong><span>buổi</span><small>Mỗi tuần</small></div>
          </div>
          <dl>
            <div><dt>Kinh nghiệm</dt><dd>{user.experience}</dd></div>
            <div><dt>Mục tiêu</dt><dd>{user.goal}</dd></div>
          </dl>
        </article>

        <article className="profile-card next-session">
          <header><div><span>04</span><p>Buổi tiếp theo</p></div><b>Upcoming</b></header>
          <time>18 <span>Tháng 09</span></time>
          <div><small>18:30 · 60 phút</small><h3>Upper Body Strength</h3><p>Studio A · PT Trần Hoàng Nam</p></div>
          <a href="/schedule">Mở lịch tập →</a>
        </article>
      </section>

      <CurtainFooter />
      <div className={"profile-toast " + (notice ? "is-visible" : "")}>{notice}</div>
    </main>
  );
}
