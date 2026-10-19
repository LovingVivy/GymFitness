import { useEffect, useState } from "react";
import { request } from "./api";

let cached = null;

/**
 * Giá một lượt PT do backend cấu hình (PT_SESSION_PRICE). Mọi PT dùng chung giá này.
 * Trả null khi chưa tải xong để giao diện không hiện một con số đoán trước.
 */
export function usePtPrice() {
  const [price, setPrice] = useState(cached);

  useEffect(() => {
    if (cached !== null) return undefined;
    let alive = true;
    request("/pt-credits/price")
      .then((data) => {
        cached = data.unit_price;
        if (alive) setPrice(cached);
      })
      .catch(() => {
        /* lỗi mạng: giữ null, nút mua hiện "đang tải giá" */
      });
    return () => {
      alive = false;
    };
  }, []);

  return price;
}
