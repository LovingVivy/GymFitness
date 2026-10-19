import { useEffect, useMemo, useRef, useState } from "react";
import { money } from "../lib/ptFormat";

// Bảng màu đã kiểm tra bằng validator (nền tối #141414): CVD ΔE 26.8, tương phản >= 3:1.
export const SERIES = [
  { key: "membership_total", label: "Gói hội viên", color: "#7d9e18" },
  { key: "pt_total", label: "Buổi PT", color: "#3b82d6" }
];

const HEIGHT = 280;
const MARGIN = { top: 26, right: 12, bottom: 34, left: 58 };
const BAR_MAX = 24;
const GAP = 2;
const RADIUS = 4;

/** "1,2 tr" / "850 N" — nhãn trục gọn, số đầy đủ nằm trong tooltip và bảng. */
function compact(value) {
  if (value >= 1e9) return `${(value / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`;
  if (value >= 1e6) return `${(value / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tr`;
  if (value >= 1e3) return `${Math.round(value / 1e3)} N`;
  return String(value);
}

function niceMax(value, integer) {
  // Trục đếm (hội viên): bội số của 4 để 5 vạch chia đều là số nguyên.
  if (integer && value <= 4) return 4;
  if (value <= 0) return 1_000_000;
  const exponent = 10 ** Math.floor(Math.log10(value));
  const fraction = value / exponent;
  const step = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
  const top = step * exponent;
  return integer ? Math.ceil(top / 4) * 4 : top;
}

/** Cột có đầu bo 4px phía trên, đáy vuông trên đường nền. */
function topRoundedRect(x, y, width, height) {
  const r = Math.min(RADIUS, width / 2, height);
  return `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
}

const paymentCount = (bucket) => `${bucket.payment_count} giao dịch`;

/**
 * Biểu đồ cột theo kỳ. Mặc định là doanh thu (cột chồng theo SERIES); truyền
 * `series`, `totalKey`, `format` để vẽ số liệu khác, ví dụ hội viên mới.
 */
export default function RevenueChart({
  buckets,
  series = SERIES,
  totalKey = "total",
  format = money,
  footnote = paymentCount,
  integer = false,
  ariaLabel = "Biểu đồ doanh thu theo kỳ, xem bảng số liệu bên dưới"
}) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(720);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return undefined;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;

  const { max, ticks } = useMemo(() => {
    const top = niceMax(Math.max(0, ...buckets.map((bucket) => bucket[totalKey])), integer);
    return { max: top, ticks: [0, 0.25, 0.5, 0.75, 1].map((step) => step * top) };
  }, [buckets, totalKey, integer]);

  const band = innerW / Math.max(1, buckets.length);
  const barW = Math.min(BAR_MAX, band * 0.6);
  const y = (value) => innerH - (value / max) * innerH;
  // Ẩn bớt nhãn trục x khi cột quá sát nhau.
  const labelEvery = band < 46 ? 2 : 1;
  const last = buckets.length - 1;

  return (
    <div className="rev-chart" ref={wrapRef}>
      {/* Một chuỗi thì tiêu đề thẻ đã gọi tên nó, không cần chú giải. */}
      {series.length > 1 ? (
        <ul className="rev-legend" aria-label="Chú giải">
          {series.map((item) => (
            <li key={item.key}><i style={{ background: item.color }} />{item.label}</li>
          ))}
        </ul>
      ) : null}

      <svg width={width} height={HEIGHT} role="img" aria-label={ariaLabel}>
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {ticks.map((tick) => (
            <g key={tick} transform={`translate(0,${y(tick)})`}>
              <line x2={innerW} className="rev-grid" />
              <text x={-10} dy="0.32em" textAnchor="end" className="rev-axis">{compact(tick)}</text>
            </g>
          ))}

          {buckets.map((bucket, index) => {
            const cx = band * index + band / 2;
            const x = cx - barW / 2;
            let base = innerH;
            const segments = series.map((item) => ({ ...item, value: bucket[item.key] })).filter(
              (segment) => segment.value > 0
            );
            return (
              <g key={bucket.period_start}>
                {hover === index ? (
                  <rect x={band * index + 2} y={0} width={band - 4} height={innerH} className="rev-band" />
                ) : null}
                {segments.map((segment, segIndex) => {
                  const h = (segment.value / max) * innerH;
                  const isTop = segIndex === segments.length - 1;
                  // Khe 2px màu nền tách các đoạn chồng nhau.
                  const drawH = Math.max(0, h - (segIndex > 0 ? GAP : 0));
                  const top = base - h;
                  base = top;
                  return isTop ? (
                    <path key={segment.key} d={topRoundedRect(x, top, barW, drawH)} fill={segment.color} />
                  ) : (
                    <rect key={segment.key} x={x} y={top} width={barW} height={drawH} fill={segment.color} />
                  );
                })}
                {index === last && bucket[totalKey] > 0 ? (
                  <text x={cx} y={y(bucket[totalKey]) - 8} textAnchor="middle" className="rev-value">
                    {compact(bucket[totalKey])}
                  </text>
                ) : null}
                {index % labelEvery === 0 || index === last ? (
                  <text x={cx} y={innerH + 20} textAnchor="middle" className="rev-axis">{bucket.label}</text>
                ) : null}
                <rect
                  x={band * index}
                  y={0}
                  width={band}
                  height={innerH}
                  fill="transparent"
                  onMouseEnter={() => setHover(index)}
                  onMouseLeave={() => setHover(null)}
                />
              </g>
            );
          })}
          <line y1={innerH} y2={innerH} x2={innerW} className="rev-baseline" />
        </g>
      </svg>

      {hover !== null ? (
        <div
          className="rev-tooltip"
          style={{
            left: Math.min(width - 190, Math.max(0, MARGIN.left + band * hover + band / 2 - 90)),
            top: 36
          }}
        >
          <strong>{buckets[hover].label}</strong>
          <span className="rev-tooltip-total">{format(buckets[hover][totalKey])}</span>
          {series.length > 1
            ? series.map((item) => (
                <span key={item.key}>
                  <i style={{ background: item.color }} />
                  {item.label}<b>{format(buckets[hover][item.key])}</b>
                </span>
              ))
            : null}
          <small>{footnote(buckets[hover])}</small>
        </div>
      ) : null}
    </div>
  );
}
