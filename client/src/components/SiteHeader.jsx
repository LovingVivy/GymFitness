import { useEffect, useRef, useState } from "react";
import { logout, useAuth } from "../lib/authStore";
import { navigateTo } from "../lib/navigation";
import { useNotifications } from "../lib/useNotifications";

const relativeTime = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diffMinutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (diffMinutes < 1) return "vừa xong";
  if (diffMinutes < 60) return `${diffMinutes} phút trước`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} giờ trước`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} ngày trước`;
};

function NotificationBell() {
  const { items, unread, readOne, readAll } = useNotifications();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const handleOutside = (event) => {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const handleOpen = async (notification) => {
    if (!notification.read_at) {
      try {
        await readOne(notification.id);
      } catch {
        /* bỏ qua */
      }
    }
    setOpen(false);
    if (notification.action_url) navigateTo(notification.action_url);
  };

  return (
    <div className="notif" ref={wrapRef}>
      <button
        type="button"
        className="notif-trigger"
        onClick={() => setOpen((value) => !value)}
        aria-label={`Thông báo${unread ? ` (${unread} chưa đọc)` : ""}`}
        aria-expanded={open}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6.5 9.5a5.5 5.5 0 0 1 11 0c0 3.4.7 5 1.5 6H5c.8-1 1.5-2.6 1.5-6Z" />
          <path d="M10 18.5a2 2 0 0 0 4 0" />
        </svg>
        {unread > 0 && <b className="notif-count">{unread > 9 ? "9+" : unread}</b>}
      </button>

      {open && (
        <div className="notif-panel">
          <header>
            <strong>Thông báo</strong>
            {unread > 0 && (
              <button type="button" onClick={readAll}>
                Đánh dấu tất cả đã đọc
              </button>
            )}
          </header>

          {items.length === 0 ? (
            <p className="notif-empty">Chưa có thông báo nào.</p>
          ) : (
            <ul>
              {items.map((item) => (
                <li key={item.id} className={item.read_at ? "" : "is-unread"}>
                  <button type="button" onClick={() => handleOpen(item)}>
                    <strong>{item.title}</strong>
                    <span>{item.body}</span>
                    <small>{relativeTime(item.created_at)}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default function SiteHeader({ autoHide = false, heroSelector = "#home" }) {
  const user = useAuth();
  const hasMembership = user?.membership?.status === "ACTIVE";
  const isTrainer = user?.role === "PT";

  useEffect(() => {
    const header = document.querySelector(".site-header");
    const hero = document.querySelector(heroSelector);
    if (!header || !autoHide || !hero) return undefined;

    let lastY = window.scrollY;
    let ticking = false;
    const syncHeader = () => {
      const currentY = window.scrollY;
      const delta = currentY - lastY;
      const pastHero = currentY > hero.offsetTop + hero.offsetHeight - header.offsetHeight;
      header.classList.toggle("is-on-light", pastHero);
      if (!pastHero || currentY < 24) header.classList.remove("is-hidden");
      else if (delta > 1) header.classList.add("is-hidden");
      else if (delta < -1) header.classList.remove("is-hidden");
      lastY = currentY;
      ticking = false;
    };
    const requestSync = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(syncHeader);
      }
    };
    window.addEventListener("scroll", requestSync, { passive: true });
    window.addEventListener("lenis-scroll", requestSync);
    window.addEventListener("resize", requestSync);
    syncHeader();
    return () => {
      window.removeEventListener("scroll", requestSync);
      window.removeEventListener("lenis-scroll", requestSync);
      window.removeEventListener("resize", requestSync);
      header.classList.remove("is-hidden", "is-on-light");
    };
  }, [autoHide, heroSelector]);

  return (
    <header className={"site-header " + (autoHide ? "" : "is-on-light")}>
      <a className="brand gym-brand" href="/" aria-label="IRONIX Fitness home"><span>IRON</span>IX</a>
      <nav className="nav" aria-label="Điều hướng chính">
        <a href="/">Home</a>
        <a href="/products">Sản phẩm</a>
        {isTrainer ? (
          <>
            <a href="/pt">Buổi dạy</a>
            <a href="/pt-schedule">Lịch của bạn</a>
          </>
        ) : (
          <>
            <a href={hasMembership ? "/schedule" : "/plans"}>{hasMembership ? "Lịch tập" : "Gói tập"}</a>
            <a href="/pt-booking">Đặt PT</a>
          </>
        )}
        <a href="/#cleanJournal">Kiến thức</a>
      </nav>
      <div className="header-actions">
        <button
          type="button"
          aria-label="Check-in QR"
          title={hasMembership ? "Mở mã QR check-in" : "Đăng ký hội viên để check-in"}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.8 8.5h10.4l.8 11H6l.8-11Z" /><path d="M9 9V6.8a3 3 0 0 1 6 0V9" /></svg>
        </button>
        {user && <NotificationBell />}
        <span className="divider" aria-hidden="true" />
        {user ? (
          <AccountMenu user={user} isTrainer={isTrainer} />
        ) : (
          <a href="/login" aria-label="Đăng nhập" title="Đăng nhập">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.5" r="3.2" /><path d="M5.5 20c.6-4 2.8-6 6.5-6s5.9 2 6.5 6" /></svg>
          </a>
        )}
      </div>
    </header>
  );
}

/**
 * Biểu tượng tài khoản kèm menu trượt xuống khi hover (hoặc khi focus bàn phím).
 * Menu đóng ngay sau khi chọn một mục để thao tác không bị vướng.
 */
function AccountMenu({ user, isTrainer }) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef(null);
  const profileHref = isTrainer ? "/pt" : "/profile";
  const profileLabel = isTrainer ? "Buổi dạy" : "Hồ sơ hội viên";

  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  const openMenu = () => {
    window.clearTimeout(closeTimer.current);
    setOpen(true);
  };

  // Trễ một nhịp ngắn để di chuột qua khoảng trống giữa icon và menu không bị đóng.
  const scheduleClose = () => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 140);
  };

  const handleLogout = () => {
    setOpen(false);
    logout();
    navigateTo("/");
  };

  return (
    <div className="account" onMouseEnter={openMenu} onMouseLeave={scheduleClose}>
      <a
        className="account-trigger"
        href={profileHref}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Tài khoản"
        title={user.fullName || user.email}
        onFocus={openMenu}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.5" r="3.2" /><path d="M5.5 20c.6-4 2.8-6 6.5-6s5.9 2 6.5 6" /></svg>
      </a>

      <div className={"account-menu" + (open ? " is-open" : "")} role="menu">
        <div className="account-menu-head">
          <strong>{user.fullName || user.email}</strong>
          <span>{user.email}</span>
          {user.memberCode ? <small>{user.memberCode}</small> : null}
        </div>

        <a role="menuitem" href={profileHref} onClick={() => setOpen(false)}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.5" r="3.2" /><path d="M5.5 20c.6-4 2.8-6 6.5-6s5.9 2 6.5 6" /></svg>
          {profileLabel}
        </a>

        {isTrainer ? (
          <a role="menuitem" href="/pt-schedule" onClick={() => setOpen(false)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14" rx="2" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" /></svg>
            Lịch của bạn
          </a>
        ) : null}

        <button type="button" role="menuitem" className="account-logout" onClick={handleLogout}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M15 4.5H6.5a1.5 1.5 0 0 0-1.5 1.5v12a1.5 1.5 0 0 0 1.5 1.5H15" />
            <path d="M18 8.5 21.5 12 18 15.5" />
            <path d="M21.5 12H10" />
          </svg>
          Đăng xuất
        </button>
      </div>
    </div>
  );
}
