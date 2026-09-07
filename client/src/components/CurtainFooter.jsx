import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import "./CurtainFooter.css";

gsap.registerPlugin(ScrollTrigger);

const defaultColumns = [
  {
    title: "Khám phá",
    links: [
      { label: "Gói tập", href: "/#products" },
      { label: "Tính năng", href: "/#philosophy" },
      { label: "Kiến thức", href: "/#cleanJournal" }
    ]
  },
  {
    title: "Hỗ trợ",
    links: [
      { label: "Liên hệ", href: "#home" },
      { label: "Điều khoản", href: "#home" },
      { label: "Bảo mật", href: "#home" }
    ]
  },
  {
    title: "Cộng đồng",
    links: [
      { label: "Instagram", href: "#home" },
      { label: "Pinterest", href: "#home" },
      { label: "TikTok", href: "#home" }
    ]
  }
];

export default function CurtainFooter({
  brand = "IRONIX Fitness",
  wordmark = "IRONIX.",
  description = "Nền tảng quản lý phòng gym cho trải nghiệm vận hành mạnh mẽ và liền mạch.",
  image = "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1800&q=85",
  imageAlt = "Không gian phòng gym IRONIX",
  columns = defaultColumns
}) {
  const rootRef = useRef(null);
  const photoRef = useRef(null);
  const newsletterShellRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    const photo = photoRef.current;
    const newsletterShell = newsletterShellRef.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (!root || !photo || !newsletterShell || reducedMotion.matches) {
      return undefined;
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        photo,
        { y: 54, scale: 1.055 },
        {
          y: -54,
          scale: 1.055,
          ease: "none",
          scrollTrigger: {
            trigger: root,
            start: "top bottom",
            end: "bottom top",
            scrub: 1,
            invalidateOnRefresh: true
          }
        }
      );

      gsap.fromTo(
        newsletterShell,
        { y: 18 },
        {
          y: -18,
          ease: "none",
          scrollTrigger: {
            trigger: root,
            start: "top 78%",
            end: "bottom bottom",
            scrub: 1,
            invalidateOnRefresh: true
          }
        }
      );
    }, root);

    const handleReducedMotionChange = () => ScrollTrigger.refresh();
    reducedMotion.addEventListener("change", handleReducedMotionChange);

    return () => {
      reducedMotion.removeEventListener("change", handleReducedMotionChange);
      ctx.revert();
    };
  }, []);

  return (
    <section className="curtain-footer" ref={rootRef}>
      <section className="curtain-footer__scene" aria-label="Newsletter signup">
        <div className="curtain-footer__image-window">
          <img className="curtain-footer__photo" ref={photoRef} src={image} alt={imageAlt} />
        </div>

        <aside className="curtain-footer__newsletter">
          <div className="curtain-footer__newsletter-shell" ref={newsletterShellRef}>
            <h2>
              KEEP MOVING
              <br />
              WITH US
            </h2>

            <p>
              Nhận lịch lớp mới, mẹo tập luyện
              <br />
              và ưu đãi hội viên từ IRONIX.
            </p>

            <form className="curtain-footer__subscribe" onSubmit={(event) => event.preventDefault()}>
              <input type="email" placeholder="NHẬP EMAIL CỦA BẠN" aria-label="Địa chỉ email" />
              <button type="submit" aria-label="Subscribe">
                &rarr;
              </button>
            </form>
          </div>
        </aside>
      </section>

      <footer className="real-footer curtain-footer__real">
        <div className="curtain-footer__grid">
          <div>
            <h3>{brand}</h3>
            <p>{description}</p>
          </div>

          {columns.map((column) => (
            <div key={column.title}>
              <h3>{column.title}</h3>
              {column.links.map((link) => (
                <a key={`${column.title}-${link.label}`} href={link.href}>
                  {link.label}
                </a>
              ))}
            </div>
          ))}
        </div>

        <div className="curtain-footer__wordmark">{wordmark}</div>
      </footer>
    </section>
  );
}
