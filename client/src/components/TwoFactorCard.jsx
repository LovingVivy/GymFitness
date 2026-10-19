import { useState } from "react";
import { disableTwoFactor, enableTwoFactor, setupTwoFactor } from "../lib/authStore";

/**
 * Bật/tắt xác thực 2 bước (TOTP). Bật: quét mã QR bằng ứng dụng Authenticator
 * rồi nhập mã 6 số; khoá chỉ được lưu khi mã đúng. Tắt: cần mật khẩu và mã hiện tại.
 */
export default function TwoFactorCard({ enabled, notify }) {
  const [setup, setSetup] = useState(null);
  const [disabling, setDisabling] = useState(false);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setSetup(null);
    setDisabling(false);
    setCode("");
    setPassword("");
  };

  const start = async () => {
    setBusy(true);
    try {
      setSetup(await setupTwoFactor());
    } catch (error) {
      notify(error.message || "Không bắt đầu được cài đặt.");
    } finally {
      setBusy(false);
    }
  };

  const confirmEnable = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await enableTwoFactor(setup.setup_token, code.trim());
      notify(result.message);
      reset();
    } catch (error) {
      notify(error.message || "Mã chưa đúng.");
    } finally {
      setBusy(false);
    }
  };

  const confirmDisable = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await disableTwoFactor(password, code.trim());
      notify(result.message);
      reset();
    } catch (error) {
      notify(error.message || "Không tắt được xác thực 2 bước.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="profile-card security-card" id="security">
      <header>
        <div><span>05</span><p>Bảo mật tài khoản</p></div>
        <b className={enabled ? "is-active" : ""}>{enabled ? "2FA đang bật" : "2FA đang tắt"}</b>
      </header>

      <div className="security-body">
        <h3>Xác thực 2 bước</h3>
        <p>
          Ngoài mật khẩu, mỗi lần đăng nhập cần thêm mã 6 số từ ứng dụng Authenticator trên điện thoại.
          Kẻ lấy được mật khẩu vẫn không vào được tài khoản.
        </p>

        {setup ? (
          <form className="security-form" onSubmit={confirmEnable}>
            {/* Hiển thị SVG như ảnh: trình duyệt không chạy mã trong <img>. */}
            <img
              className="security-qr"
              src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
              alt="Mã QR cài đặt xác thực 2 bước"
            />
            <ol>
              <li>Mở Google Authenticator / Microsoft Authenticator và quét mã QR.</li>
              <li>Không quét được? Nhập khoá thủ công: <code>{setup.secret}</code></li>
              <li>Nhập mã 6 số ứng dụng đang hiển thị để hoàn tất.</li>
            </ol>
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9 ]{6,7}"
              maxLength={7}
              placeholder="Mã 6 số"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
              autoFocus
            />
            <div className="security-actions">
              <button type="button" className="security-ghost" onClick={reset}>Huỷ</button>
              <button type="submit" disabled={busy}>{busy ? "Đang kiểm tra…" : "Bật xác thực 2 bước"}</button>
            </div>
          </form>
        ) : disabling ? (
          <form className="security-form" onSubmit={confirmDisable}>
            <input
              type="password"
              autoComplete="current-password"
              placeholder="Mật khẩu hiện tại"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoFocus
            />
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9 ]{6,7}"
              maxLength={7}
              placeholder="Mã 6 số"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
            />
            <div className="security-actions">
              <button type="button" className="security-ghost" onClick={reset}>Huỷ</button>
              <button type="submit" disabled={busy}>{busy ? "Đang xử lý…" : "Tắt xác thực 2 bước"}</button>
            </div>
          </form>
        ) : (
          <div className="security-actions">
            {enabled ? (
              <button type="button" className="security-ghost" onClick={() => setDisabling(true)}>Tắt xác thực 2 bước</button>
            ) : (
              <button type="button" onClick={start} disabled={busy}>{busy ? "Đang tạo mã…" : "Bật xác thực 2 bước"}</button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
