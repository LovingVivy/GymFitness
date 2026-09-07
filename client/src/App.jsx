import { useEffect, useRef, useState } from "react";
import Auth from "./pages/Auth.jsx";
import Home from "./pages/Home.jsx";
import PlanRegistration from "./pages/PlanRegistration.jsx";
import Products from "./pages/Products.jsx";
import "./App.css";

const LoginPage = () => <Auth mode="login" />;
const SignupPage = () => <Auth mode="signup" />;

const routeMap = {
  "/": Home,
  "/login": LoginPage,
  "/signup": SignupPage,
  "/plans": PlanRegistration,
  "/products": Products
};

const coverDuration = 650;
const revealDuration = 700;
const resolveRoute = () => (routeMap[window.location.pathname] ? window.location.pathname : "/");

export default function App() {
  const [route, setRoute] = useState(resolveRoute);
  const [transitionPhase, setTransitionPhase] = useState("idle");
  const routeRef = useRef(route);
  const timersRef = useRef([]);
  const transitioningRef = useRef(false);

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  useEffect(() => {
    document.body.classList.toggle("is-page-transitioning", transitionPhase !== "idle");
    return () => document.body.classList.remove("is-page-transitioning");
  }, [transitionPhase]);

  useEffect(() => {
    const clearTimers = () => {
      timersRef.current.forEach((timer) => window.clearTimeout(timer));
      timersRef.current = [];
    };

    const commitRoute = (url, historyAction) => {
      const nextRoute = routeMap[url.pathname] ? url.pathname : "/";
      const nextUrl = `${url.pathname}${url.search}${url.hash}`;

      if (historyAction === "push") window.history.pushState({}, "", nextUrl);
      setRoute(nextRoute);
      routeRef.current = nextRoute;
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    };

    const navigate = (url, historyAction = "push") => {
      const nextRoute = routeMap[url.pathname] ? url.pathname : "/";

      if (nextRoute === routeRef.current) {
        if (historyAction === "push") {
          window.history.pushState({}, "", `${url.pathname}${url.search}${url.hash}`);
        }
        if (url.hash) document.querySelector(url.hash)?.scrollIntoView({ block: "start" });
        return;
      }

      if (transitioningRef.current) return;

      clearTimers();
      transitioningRef.current = true;
      setTransitionPhase("covering");

      timersRef.current.push(
        window.setTimeout(() => {
          commitRoute(url, historyAction);
          setTransitionPhase("revealing");

          timersRef.current.push(
            window.setTimeout(() => {
              setTransitionPhase("idle");
              transitioningRef.current = false;
            }, revealDuration)
          );
        }, coverDuration)
      );
    };

    const handleClick = (event) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      const link = event.target.closest("a[href]");
      if (!link || link.target || link.hasAttribute("download")) return;

      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || !routeMap[url.pathname]) return;

      event.preventDefault();
      navigate(url);
    };

    const handlePopState = () => navigate(new URL(window.location.href), "none");

    document.addEventListener("click", handleClick);
    window.addEventListener("popstate", handlePopState);

    return () => {
      clearTimers();
      document.removeEventListener("click", handleClick);
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  const Page = routeMap[route] || Home;

  return (
    <>
      <div className="page-shell">
        <Page key={route} />
      </div>

      <div
        className={`page-transition-layer ${
          transitionPhase === "covering"
            ? "is-covering"
            : transitionPhase === "revealing"
              ? "is-revealing"
              : ""
        }`}
        aria-hidden="true"
      >
        <div className="page-transition-mark"><span>IRON</span>IX</div>
      </div>
    </>
  );
}
