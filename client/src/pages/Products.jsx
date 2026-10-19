import { useEffect, useMemo, useState } from "react";
import SiteHeader from "../components/SiteHeader";
import CurtainFooter from "../components/CurtainFooter";
import ProductArt from "../components/ProductArt";
import { listProducts } from "../lib/shopApi";
import { money } from "../lib/ptFormat";
import "./Products.css";

// Sản phẩm do quản trị viên quản lý ở /admin#shop; trang này chỉ đọc.
const toCard = (item) => ({
  id: item.id,
  group: (item.activity_type || "GYM").toLowerCase(),
  type: item.category_name || "Sản phẩm",
  name: item.name,
  price: item.price,
  art: item.art,
  note: item.description,
  badge: item.badge,
  soldOut: item.available_quantity <= 0
});

function ProductCard({ product, onAdd }) {
  return (
    <article className="product-card">
      <div className={`product-visual art-${product.art}`}>
        {product.badge && <span>{product.badge}</span>}
        <ProductArt type={product.art} />
        <button type="button" className="product-add" onClick={() => onAdd(product)} disabled={product.soldOut} aria-label={product.soldOut ? `${product.name} đã hết hàng` : `Thêm ${product.name} vào giỏ`}>
          {product.soldOut ? "Hết hàng" : <><span>+</span> Thêm vào giỏ</>}
        </button>
      </div>
      <div className="product-info">
        <p>{product.type}</p>
        <h3>{product.name}</h3>
        <small>{product.note}</small>
        <strong>{money(product.price)}</strong>
      </div>
    </article>
  );
}

export default function Products() {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [cart, setCart] = useState([]);
  const [notice, setNotice] = useState("");
  const [products, setProducts] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    listProducts()
      .then((items) => {
        if (cancelled) return;
        setProducts(items.map(toCard));
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(() => products.filter((product) => {
    const matchesGroup = filter === "all" || product.group === filter;
    const keyword = query.trim().toLocaleLowerCase("vi");
    return matchesGroup && (!keyword || `${product.name} ${product.type}`.toLocaleLowerCase("vi").includes(keyword));
  }), [products, filter, query]);

  const addToCart = (product) => {
    setCart((current) => [...current, product.id]);
    setNotice(`Đã thêm “${product.name}”`);
    window.setTimeout(() => setNotice(""), 1800);
  };

  const gymProducts = visible.filter((item) => item.group === "gym");
  const yogaProducts = visible.filter((item) => item.group === "yoga");

  return (
    <main className="products-page">
      <SiteHeader />
      <section className="shop-hero">
        <div className="shop-hero-copy">
          <p className="shop-kicker">IRONIX EQUIPMENT · 2026</p>
          <h1>Trang bị cho<br/><em>mọi chuyển động.</em></h1>
          <p>Từ buổi tập nặng đến nhịp thở chậm, chọn đúng dụng cụ để tập tốt hơn mỗi ngày.</p>
        </div>
        <div className="shop-hero-orbit" aria-hidden="true">
          <span className="orbit-label">GYM</span><span className="orbit-core">IX</span><span className="orbit-label">YOGA</span>
        </div>
        <div className="shop-hero-index"><strong>{status === "ready" ? products.length : "—"}</strong><span>Sản phẩm tuyển chọn</span></div>
      </section>

      <section className="shop-toolbar" aria-label="Tìm và lọc sản phẩm">
        <div className="shop-filters">
          {[["all", "Tất cả"], ["gym", "Gym"], ["yoga", "Yoga"]].map(([value, label]) => (
            <button key={value} type="button" className={filter === value ? "is-active" : ""} onClick={() => setFilter(value)}>{label}</button>
          ))}
        </div>
        <label className="shop-search">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm găng tay, whey, thảm..." />
        </label>
        <button className="shop-cart" type="button" aria-label={`Giỏ hàng có ${cart.length} sản phẩm`}>
          Giỏ hàng <span>{String(cart.length).padStart(2, "0")}</span>
        </button>
      </section>

      <div className="shop-catalog">
        {(filter === "all" || filter === "gym") && gymProducts.length > 0 && (
          <section className="product-section">
            <header><div><span>01</span><p>Strength collection</p></div><h2>Đồ tập <em>Gym</em></h2><p>Trang phục, phụ kiện và dinh dưỡng dành cho những buổi tập hiệu suất cao.</p></header>
            <div className="product-grid">{gymProducts.map((product) => <ProductCard key={product.id} product={product} onAdd={addToCart} />)}</div>
          </section>
        )}
        {(filter === "all" || filter === "yoga") && yogaProducts.length > 0 && (
          <section className="product-section yoga-section">
            <header><div><span>02</span><p>Mindful collection</p></div><h2>Đồ tập <em>Yoga</em></h2><p>Dụng cụ và trang phục mềm mại, ổn định cho từng tư thế và nhịp thở.</p></header>
            <div className="product-grid">{yogaProducts.map((product) => <ProductCard key={product.id} product={product} onAdd={addToCart} />)}</div>
          </section>
        )}
        {status === "loading" && <div className="shop-empty"><strong>Đang tải sản phẩm…</strong></div>}
        {status === "error" && <div className="shop-empty"><strong>Không tải được sản phẩm</strong><p>Kiểm tra kết nối rồi tải lại trang.</p></div>}
        {status === "ready" && visible.length === 0 && <div className="shop-empty"><strong>Không tìm thấy sản phẩm</strong><p>Thử một từ khóa khác hoặc xem toàn bộ bộ sưu tập.</p><button onClick={() => { setQuery(""); setFilter("all"); }}>Xem tất cả</button></div>}
      </div>

      <section className="shop-promise">
        <p>IRONIX MEMBER BENEFITS</p>
        <div><article><span>01</span><h3>Đổi trả 14 ngày</h3><p>Đổi kích cỡ miễn phí với sản phẩm còn nguyên tem.</p></article><article><span>02</span><h3>Chọn lọc kỹ</h3><p>Sản phẩm được huấn luyện viên IRONIX kiểm tra thực tế.</p></article><article><span>03</span><h3>Ưu đãi hội viên</h3><p>Giảm thêm 10% khi mua tại quầy cho hội viên đang hoạt động.</p></article></div>
      </section>

      <CurtainFooter />
      <div className={`cart-toast ${notice ? "is-visible" : ""}`} role="status">{notice}<span>✓</span></div>
    </main>
  );
}


