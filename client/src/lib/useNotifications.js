import { useCallback, useEffect, useRef, useState } from "react";
import { getToken, useAuth } from "./authStore";
import { getUnreadCount, listNotifications, markAllNotificationsRead, markNotificationRead } from "./ptApi";

const POLL_INTERVAL_MS = 20000;

/**
 * Thông báo trong ứng dụng: nạp khi mở trang, làm mới định kỳ và khi có
 * sự kiện đọc. Chỉ chạy khi đã đăng nhập.
 */
export function useNotifications() {
  const user = useAuth();
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setItems([]);
      setUnread(0);
      return;
    }
    setLoading(true);
    try {
      const data = await listNotifications();
      setItems(data.items);
      setUnread(data.unread);
    } catch {
      /* im lặng: chuông không nên làm phiền khi mạng lỗi */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (!user) return undefined;

    const tick = async () => {
      if (document.visibilityState === "visible" && getToken()) {
        try {
          const data = await getUnreadCount();
          setUnread(data.unread);
        } catch {
          /* bỏ qua */
        }
      }
    };
    timer.current = window.setInterval(tick, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer.current);
  }, [refresh, user]);

  const readOne = useCallback(async (notificationId) => {
    const data = await markNotificationRead(notificationId);
    setItems(data.items);
    setUnread(data.unread);
  }, []);

  const readAll = useCallback(async () => {
    const data = await markAllNotificationsRead();
    setItems(data.items);
    setUnread(data.unread);
  }, []);

  return { items, unread, loading, refresh, readOne, readAll };
}
