import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Một thông báo nổi tại một thời điểm. Thông báo mới huỷ hẹn giờ của thông báo
 * cũ, nên nó không bị ẩn sớm khi hai thao tác diễn ra liên tiếp.
 */
export function useToast(duration = 3600) {
  const [notice, setNotice] = useState("");
  const timer = useRef(null);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const notify = useCallback(
    (message) => {
      window.clearTimeout(timer.current);
      setNotice(message);
      timer.current = window.setTimeout(() => setNotice(""), duration);
    },
    [duration]
  );

  return [notice, notify];
}
