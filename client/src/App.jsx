import { useEffect, useState } from "react";
import Admin from "./pages/Admin.jsx";
import Auth from "./pages/Auth.jsx";
import Home from "./pages/Home.jsx";
import PlanRegistration from "./pages/PlanRegistration.jsx";
import Products from "./pages/Products.jsx";
import Profile from "./pages/Profile.jsx";
import PTBooking from "./pages/PTBooking.jsx";
import PTDashboard from "./pages/PTDashboard.jsx";
import PTSchedule from "./pages/PTSchedule.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import Schedule from "./pages/Schedule.jsx";
import { getCurrentUser, getToken, logout, refreshProfile } from "./lib/authStore.js";
import "./App.css";

const LoginPage = () => <Auth mode="login" />;
const SignupPage = () => <Auth mode="signup" />;

const routeMap = {
  "/": Home,
  "/login": LoginPage,
  "/signup": SignupPage,
  "/plans": PlanRegistration,
  "/products": Products,
  "/profile": Profile,
  "/schedule": Schedule,
  "/pt": PTDashboard,
  "/pt-schedule": PTSchedule,
  "/admin": Admin,
  "/reset-password": ResetPassword,
  "/pt-booking": PTBooking
};

const resolveRoute = () => (routeMap[window.location.pathname] ? window.location.pathname : "/");

export default function App() {
  const [route, setRoute] = useState(resolveRoute);

  // Nạp lại hồ sơ thật khi mở app: dữ liệu gói tập và ngày còn lại luôn mới.
  // Session demo cũ (có user nhưng không có token thật) bị xoá, và token hết
  // hạn cũng bị xoá bởi refreshProfile.
  useEffect(() => {
    if (!getToken()) {
      if (getCurrentUser()) logout();
      return;
    }
    refreshProfile().catch(() => {
      /* lỗi mạng thì giữ nguyên session đang có */
    });
  }, []);

  useEffect(() => {
    const handleClick = (event) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target.closest("a[href]");
      if (!link || link.target || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || !routeMap[url.pathname]) return;

      event.preventDefault();
      const nextRoute = routeMap[url.pathname] ? url.pathname : "/";
      window.history.pushState({}, "", url.pathname + url.search + url.hash);
      setRoute(nextRoute);
      if (url.hash) {
        document.querySelector(url.hash)?.scrollIntoView({ block: "start" });
      }
    };

    const handlePopState = () => setRoute(resolveRoute());
    document.addEventListener("click", handleClick);
    window.addEventListener("popstate", handlePopState);
    return () => {
      document.removeEventListener("click", handleClick);
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [route]);

  const Page = routeMap[route] || Home;

  return <div className="page-shell"><Page key={route} /></div>;
}
