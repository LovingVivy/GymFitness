import { useEffect } from "react";

export default function SiteHeader({ autoHide = false, heroSelector = "#home" }) {
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
    <header className={`site-header ${autoHide ? "" : "is-on-light"}`}>
      <a className="brand gym-brand" href="/" aria-label="IRONIX Fitness home"><span>IRON</span>IX</a>
      <nav className="nav" aria-label="Điều hướng chính">
        <a href="/">Home</a>
        <a href="/products">Sản phẩm</a>
        <a href="/plans">Gói tập</a>
        <a href="/#philosophy">Tính năng</a>
        <a href="/#cleanJournal">Kiến thức</a>
      </nav>
      <div className="header-actions">
        <button type="button" aria-label="Check-in QR">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.8 8.5h10.4l.8 11H6l.8-11Z" /><path d="M9 9V6.8a3 3 0 0 1 6 0V9" /></svg>
        </button>
        <span className="divider" aria-hidden="true" />
        <a href="/login" aria-label="Tài khoản">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.5" r="3.2" /><path d="M5.5 20c.6-4 2.8-6 6.5-6s5.9 2 6.5 6" /></svg>
        </a>
      </div>
    </header>
  );
}
