import { useCallback, useEffect, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { getOverview } from "../lib/adminApi";
import { useAuth } from "../lib/authStore";
import { can, P } from "../lib/permissions";
import { money } from "../lib/ptFormat";
import { useToast } from "../lib/useToast";
import AccountsTab from "./admin/AccountsTab";
import AuditTab from "./admin/AuditTab";
import CheckinsTab from "./admin/CheckinsTab";
import PaymentsTab from "./admin/PaymentsTab";
import PlansTab from "./admin/PlansTab";
import RevenueTab from "./admin/RevenueTab";
import ShopTab from "./admin/ShopTab";
import "./Admin.css";

// Mỗi tab là một "màn hình" gắn với một quyền (RBAC). Backend vẫn kiểm tra lại mọi request.
const TABS = [
  { id: "revenue", label: "Báo cáo", permission: P.REPORTS_VIEW },
  { id: "accounts", label: "Tài khoản", permission: P.USERS_VIEW },
  { id: "plans", label: "Gói tập", permission: P.PLANS_VIEW },
  { id: "shop", label: "Cửa hàng", permission: P.PRODUCTS_VIEW },
  { id: "payments", label: "Thanh toán", permission: P.PAYMENTS_VIEW },
  { id: "checkins", label: "Ra vào", permission: P.CHECKINS_VIEW },
  { id: "audit", label: "Nhật ký", permission: P.AUDIT_VIEW }
];

const growth = (percent, fallback) =>
  percent === null || percent === undefined
    ? fallback
    : `${percent >= 0 ? "▲" : "▼"} ${Math.abs(percent).toLocaleString("vi-VN")}% so với tháng trước`;

const tabFromHash = () => window.location.hash.replace("#", "");

export default function Admin() {
  const user = useAuth();
  const isAdmin = can(user, P.DASHBOARD_VIEW);
  const tabs = TABS.filter((item) => can(user, item.permission));
  const [requested, setTab] = useState(tabFromHash);
  const tab = tabs.some((item) => item.id === requested) ? requested : tabs[0]?.id;
  const [overview, setOverview] = useState(null);
  const [notice, notify] = useToast(3600);

  const loadOverview = useCallback(() => {
    getOverview()
      .then(setOverview)
      .catch((error) => notify(error.message || "Không tải được số liệu tổng quan."));
  }, [notify]);

  useEffect(() => {
    if (isAdmin) loadOverview();
  }, [isAdmin, loadOverview]);

  // Liên kết kiểu /admin#shop (thông báo, gõ tay) đổi tab mà không cần tải lại trang.
  useEffect(() => {
    const syncTab = () => setTab(tabFromHash());
    window.addEventListener("hashchange", syncTab);
    return () => window.removeEventListener("hashchange", syncTab);
  }, []);

  const selectTab = (id) => {
    setTab(id);
    window.history.replaceState({}, "", `/admin#${id}`);
  };

  if (!isAdmin) {
    return (
      <main className="adm-page">
        <SiteHeader />
        <section className="adm-locked">
          <span>Admin</span>
          <h1>Khu vực dành cho<br /><em>quản trị viên.</em></h1>
          <p>Đăng nhập bằng tài khoản quản trị hoặc quản lý để quản lý tài khoản, gói tập, cửa hàng, thanh toán và xem báo cáo.</p>
          <a href="/login">Đăng nhập <b>→</b></a>
        </section>
        <CurtainFooter />
      </main>
    );
  }

  const stats = overview
    ? [
        {
          value: overview.members,
          label: "hội viên",
          sub: `+${overview.new_members_this_month} tháng này · ${growth(overview.member_growth_percent, "chưa có tháng trước để so")}`
        },
        { value: overview.active_members, label: "hội viên còn gói", sub: `${overview.trainers} huấn luyện viên` },
        {
          value: money(overview.revenue_this_month),
          label: "doanh thu tháng này",
          sub: growth(overview.revenue_growth_percent, "chưa có doanh thu tháng trước")
        },
        { value: overview.pending_payments, label: "giao dịch chờ thanh toán", sub: `${overview.products} sản phẩm đang bán` }
      ]
    : [];

  return (
    <main className="adm-page">
      <SiteHeader />

      <section className="adm-hero">
        <div>
          <p>{user.role === "ADMIN" ? "Quản trị" : "Quản lý"} · {user.fullName || user.email}</p>
          <h1>Bảng điều <em>khiển.</em></h1>
        </div>
        <div className="adm-stats">
          {stats.map((stat) => (
            <div key={stat.label}>
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
              {stat.sub ? <small>{stat.sub}</small> : null}
            </div>
          ))}
        </div>
      </section>

      <nav className="adm-tabs" role="tablist" aria-label="Khu vực quản trị">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "is-active" : ""}
            onClick={() => selectTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <section className="adm-content">
        {tab === "revenue" ? <RevenueTab notify={notify} overview={overview} user={user} /> : null}
        {tab === "accounts" ? <AccountsTab notify={notify} currentUserId={user.id} onChange={loadOverview} user={user} /> : null}
        {tab === "plans" ? <PlansTab notify={notify} user={user} /> : null}
        {tab === "shop" ? <ShopTab notify={notify} onChange={loadOverview} user={user} /> : null}
        {tab === "payments" ? <PaymentsTab notify={notify} onChange={loadOverview} user={user} /> : null}
        {tab === "checkins" ? <CheckinsTab notify={notify} onChange={loadOverview} user={user} /> : null}
        {tab === "audit" ? <AuditTab notify={notify} /> : null}
      </section>

      <CurtainFooter />
      <div className={"adm-toast " + (notice ? "is-visible" : "")} aria-live="polite">{notice}</div>
    </main>
  );
}
