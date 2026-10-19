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

// Hình minh hoạ quản trị viên chọn được cho một sản phẩm (lưu ở attributes.art).
export const ART_OPTIONS = [
  ["gloves", "Găng tay"],
  ["shirt", "Áo"],
  ["shorts", "Quần short"],
  ["bag", "Túi"],
  ["whey", "Hộp dinh dưỡng"],
  ["shaker", "Bình lắc"],
  ["bar", "Thanh protein"],
  ["mat", "Thảm"],
  ["block", "Gạch tập"],
  ["strap", "Dây"],
  ["legging", "Quần dài"],
  ["bra", "Áo bra"],
  ["sling", "Túi đeo chéo"]
];

const FALLBACK = "bag";

export default function ProductArt({ type }) {
  return <svg viewBox="0 0 120 120" aria-hidden="true">{paths[type] || paths[FALLBACK]}</svg>;
}
