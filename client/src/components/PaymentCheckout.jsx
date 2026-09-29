import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getCheckout, simulatePaid } from "../lib/paymentApi";
import "./PaymentCheckout.css";

const POLL_INTERVAL_MS = 3000;

const money = (value) => new Intl.NumberFormat("vi-VN").format(value) + "đ";

function formatCountdown(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function CopyValue({ label, value }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(String(value));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* trình duyệt chặn clipboard thì người dùng tự chọn và sao chép */
    }
  };

  return (
    <div className="pay-row">
      <span>{label}</span>
      <strong>{value}</strong>
      <button type="button" onClick={copy}>{copied ? "Đã chép" : "Chép"}</button>
    </div>
  );
}

/**
 * Màn hình thanh toán chuyển khoản QR.
 *
 * Hiển thị VietQR rồi hỏi backend mỗi vài giây. Quyền lợi chỉ được kích hoạt
 * khi ngân hàng báo đã nhận tiền (webhook), nên frontend chỉ chờ và đọc
 * trạng thái — không bao giờ tự đánh dấu đã thanh toán.
 */
export default function PaymentCheckout({ paymentId, title, step, onPaid, onClose }) {
  const [checkout, setCheckout] = useState(null);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [simulating, setSimulating] = useState(false);
  const paidRef = useRef(false);
  // Giữ callback mới nhất mà không khởi động lại vòng hỏi trạng thái mỗi lần render.
  const onPaidRef = useRef(onPaid);
  useEffect(() => {
    onPaidRef.current = onPaid;
  }, [onPaid]);

  const handleStatus = useCallback((data) => {
    setCheckout(data);
    if (data.status === "PAID" && !paidRef.current) {
      paidRef.current = true;
      window.setTimeout(() => onPaidRef.current?.(data), 1200);
    }
  }, []);

  // Hỏi trạng thái lặp lại cho tới khi PAID hoặc đóng cửa sổ.
  useEffect(() => {
    let cancelled = false;
    let timer;

    const poll = async () => {
      try {
        const data = await getCheckout(paymentId);
        if (cancelled) return;
        setError("");
        handleStatus(data);
        if (data.status !== "PENDING") return;
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Không kiểm tra được trạng thái thanh toán.");
      }
      timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [paymentId, handleStatus]);

  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape" && checkout?.status !== "PAID") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [checkout?.status, onClose]);

  const handleSimulate = async () => {
    setSimulating(true);
    try {
      await simulatePaid(paymentId);
      handleStatus(await getCheckout(paymentId));
    } catch (err) {
      setError(err.message || "Không giả lập được thanh toán.");
    } finally {
      setSimulating(false);
    }
  };

  const status = checkout?.status;
  const remainingMs = checkout?.expires_at ? new Date(checkout.expires_at).getTime() - now : null;
  const expired = status === "PENDING" && (checkout?.expired || (remainingMs !== null && remainingMs <= 0));

  // Portal ra body: các trang có hiệu ứng transform làm position:fixed lệch khỏi màn hình.
  return createPortal(
    <div className="pay-overlay" role="dialog" aria-modal="true" aria-labelledby="payTitle">
      <div className="pay-card">
        <header className="pay-head">
          <div>
            {step ? <p>{step}</p> : null}
            <h2 id="payTitle">{title || "Thanh toán chuyển khoản"}</h2>
          </div>
          {status !== "PAID" ? (
            <button type="button" className="pay-close" onClick={onClose} aria-label="Đóng">×</button>
          ) : null}
        </header>

        {!checkout ? (
          <div className="pay-loading">
            <span className="pay-spinner" />
            <p>{error || "Đang tạo mã thanh toán…"}</p>
          </div>
        ) : status === "PAID" ? (
          <div className="pay-success">
            <span className="pay-check">✓</span>
            <h3>Đã nhận {money(checkout.amount)}</h3>
            <p>Thanh toán thành công. Đang cập nhật quyền lợi của bạn…</p>
          </div>
        ) : (
          <div className="pay-body">
            <div className="pay-qr">
              {checkout.qr_image_url ? (
                <img src={checkout.qr_image_url} alt={`Mã VietQR thanh toán ${money(checkout.amount)}`} />
              ) : (
                <div className="pay-qr-missing">
                  Chưa cấu hình tài khoản nhận tiền
                  <small>PAYMENT_BANK_CODE / PAYMENT_ACCOUNT_NO trong backend/.env</small>
                </div>
              )}
              {expired ? <div className="pay-qr-expired">Mã QR đã hết hạn</div> : null}
            </div>

            <div className="pay-info">
              <p className="pay-amount">{money(checkout.amount)}</p>
              {checkout.bank ? (
                <>
                  <CopyValue label="Ngân hàng" value={checkout.bank.bank_code} />
                  <CopyValue label="Số tài khoản" value={checkout.bank.account_no} />
                  {checkout.bank.account_name ? (
                    <div className="pay-row"><span>Chủ tài khoản</span><strong>{checkout.bank.account_name}</strong></div>
                  ) : null}
                </>
              ) : null}
              <CopyValue label="Số tiền" value={Math.round(checkout.amount)} />
              <CopyValue label="Nội dung" value={checkout.transfer_content} />

              <p className="pay-warning">
                Giữ nguyên <b>nội dung chuyển khoản</b> để hệ thống tự nhận diện giao dịch.
              </p>

              <div className={"pay-waiting " + (expired ? "is-expired" : "")}>
                {expired ? (
                  <p>Mã đã quá hạn. Nếu bạn đã chuyển khoản, hệ thống vẫn sẽ ghi nhận khi ngân hàng báo về.</p>
                ) : (
                  <>
                    <span className="pay-spinner" />
                    <p>
                      Đang chờ ngân hàng xác nhận…
                      {remainingMs !== null ? <b> {formatCountdown(remainingMs)}</b> : null}
                    </p>
                  </>
                )}
              </div>

              {error ? <p className="pay-error">{error}</p> : null}

              {checkout.simulation_enabled ? (
                <button type="button" className="pay-simulate" onClick={handleSimulate} disabled={simulating}>
                  {simulating ? "Đang giả lập…" : "Giả lập đã nhận tiền (dev)"}
                </button>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
