import { useMemo, useState } from "react";
import SiteHeader from "../components/SiteHeader";
import CurtainFooter from "../components/CurtainFooter";
import "./Products.css";

const products = [
  { id: 1, group: "gym", type: "Phụ kiện", name: "Găng tay Grip Pro", price: 289000, art: "gloves", note: "Da microfiber · Đệm gel chống trượt", badge: "Bán chạy" },
  { id: 2, group: "gym", type: "Trang phục", name: "Áo Training Dry-Fit", price: 359000, art: "shirt", note: "Thoáng khí · Co giãn 4 chiều", badge: "Mới" },
  { id: 3, group: "gym", type: "Trang phục", name: "Quần short Flex 7\"", price: 329000, art: "shorts", note: "Lớp lót kép · Túi khóa kéo" },
  { id: 4, group: "gym", type: "Túi tập", name: "Túi mini Locker", price: 449000, art: "bag", note: "Ngăn giày riêng · Chống thấm" },
  { id: 5, group: "gym", type: "Dinh dưỡng", name: "Whey Protein Isolate", price: 1290000, art: "whey", note: "25g protein · Vị chocolate", badge: "Top 1" },
  { id: 6, group: "gym", type: "Phụ kiện", name: "Bình lắc Core 700ml", price: 169000, art: "shaker", note: "BPA free · Lưới chống vón" },
  { id: 7, group: "gym", type: "Dinh dưỡng", name: "Thanh Protein Crunch", price: 49000, art: "bar", note: "20g protein · Ít đường" },
  { id: 8, group: "yoga", type: "Dụng cụ", name: "Thảm Yoga Align 5mm", price: 699000, art: "mat", note: "Cao su tự nhiên · Bám chắc", badge: "Khuyên dùng" },
  { id: 9, group: "yoga", type: "Dụng cụ", name: "Gạch tập Balance", price: 159000, art: "block", note: "EVA mật độ cao · Bo cạnh mềm" },
  { id: 10, group: "yoga", type: "Dụng cụ", name: "Dây hỗ trợ Flow", price: 129000, art: "strap", note: "Khóa kim loại · Dài 2.4m" },
  { id: 11, group: "yoga", type: "Trang phục", name: "Quần Legging Motion", price: 479000, art: "legging", note: "Cạp cao · Không lộ đường may", badge: "Mới" },
  { id: 12, group: "yoga", type: "Trang phục", name: "Áo Bra Calm Support", price: 389000, art: "bra", note: "Nâng đỡ vừa · Vải mát" },
  { id: 13, group: "yoga", type: "Túi tập", name: "Túi thảm Yoga Sling", price: 299000, art: "sling", note: "Đeo chéo · Vải canvas bền" }
];

const money = (value) => new Intl.NumberFormat("vi-VN").format(value) + "đ";

function ProductArt({ type }) {
  const paths = {
    gloves: <><path d="M38 75V38c0-7 9-7 9 0v18-27c0-7 10-7 10 0v25-31c0-7 10-7 10 0v31-25c0-7 10-7 10 0v32l8-10c5-6 13 1 9 7L77 82c-5 7-12 11-21 11-10 0-18-8-18-18Z"/><path d="M40 65h38"/></>,
    shirt: <path d="M38 28 51 20h18l13 8 18 12-12 18-10-6v45H42V52l-10 6-12-18 18-12Z"/>,
    shorts: <><path d="M34 25h52l6 70-30-6-2-35-2 35-30 6 6-70Z"/><path d="M34 39h52M60 25v29"/></>,
    bag: <><rect x="18" y="42" width="84" height="49" rx="10"/><path d="M39 42c0-18 42-18 42 0M18 59h84M79 65h11"/></>,
    whey: <><path d="M31 31h58l-5 67H36l-5-67Z"/><path d="M27 22h66v12H27zM45 62c8-13 22-13 30 0-8 13-22 13-30 0Z"/></>,
    shaker: <><path d="M39 29h42l-6 70H45l-6-70Z"/><path d="M35 20h50v12H35zM43 57h34M52 20V12h17l8 8"/></>,
    bar: <><path d="M18 42 91 28l11 50-73 14-11-50Z"/><path d="m31 40 10 48m42-55 9 48M46 58l31-6"/></>,
    mat: <><path d="M24 47h69v41H24c-11 0-11-17 0-17h68"/><ellipse cx="92" cy="67.5" rx="10" ry="20.5"/></>,
    block: <><path d="m26 45 57-17 14 47-57 17-14-47Z"/><path d="m35 48 42-12 10 34-42 12-10-34Z"/></>,
    strap: <><path d="M31 29c31-19 58 3 54 30-3 22-27 30-44 19-18-11-12-34 7-37 17-3 31 13 22 27-8 13-30 7-27-8"/><rect x="25" y="24" width="14" height="15" rx="2"/></>,
    legging: <path d="M39 20h42l-4 34 10 48H65l-5-35-5 35H33l10-48-4-34Z"/>,
    bra: <><path d="M37 27c7 3 14 5 23 5s16-2 23-5l9 52c-21 12-43 12-64 0l9-52Z"/><path d="M28 65h64M44 30c0 21 32 21 32 0"/></>,
    sling: <><path d="m31 33 54 20-17 45-54-20 17-45Z"/><path d="M31 33c7-20 37-17 54 20M41 37 24 83"/></>
  };
  return <svg viewBox="0 0 120 120" aria-hidden="true">{paths[type]}</svg>;
}

function ProductCard({ product, onAdd }) {
  return (
    <article className="product-card">
      <div className={`product-visual art-${product.art}`}>
        {product.badge && <span>{product.badge}</span>}
        <ProductArt type={product.art} />
        <button type="button" className="product-add" onClick={() => onAdd(product)} aria-label={`Thêm ${product.name} vào giỏ`}>
          <span>+</span> Thêm vào giỏ
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

  const visible = useMemo(() => products.filter((product) => {
    const matchesGroup = filter === "all" || product.group === filter;
    const keyword = query.trim().toLocaleLowerCase("vi");
    return matchesGroup && (!keyword || `${product.name} ${product.type}`.toLocaleLowerCase("vi").includes(keyword));
  }), [filter, query]);

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
        <div className="shop-hero-index"><strong>13</strong><span>Sản phẩm tuyển chọn</span></div>
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
        {visible.length === 0 && <div className="shop-empty"><strong>Không tìm thấy sản phẩm</strong><p>Thử một từ khóa khác hoặc xem toàn bộ bộ sưu tập.</p><button onClick={() => { setQuery(""); setFilter("all"); }}>Xem tất cả</button></div>}
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


