import { useState } from "react";
import { resetPassword } from "../lib/authStore";
import { navigateTo } from "../lib/navigation";
import "./Auth.css";

const COVER =
  "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=1800&q=90";

/** Trang mở từ liên kết trong email "Đặt lại mật khẩu": /reset-password?token=... */
export default function ResetPassword() {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (password !== confirm) {
      setMessage("Mật khẩu xác nhận chưa trùng khớp.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const result = await resetPassword(token, password);
      setDone(true);
      setMessage(result.message);
      window.setTimeout(() => navigateTo("/login"), 2200);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page auth-page--login">
      <section className="auth-cover" aria-label="Đặt lại mật khẩu IRONIX">
        <img src={COVER} alt="Không gian tập luyện IRONIX" />
        <div className="auth-cover-shade" />
        <a className="auth-brand" href="/" aria-label="Về trang chủ IRONIX"><span>IRON</span>IX</a>
        <a className="auth-home-link" href="/"><span>←</span> Trang chủ</a>
        <div className="auth-cover-copy">
          <p>Account recovery</p>
          <h1>New password,<br /><em>same strong you.</em></h1>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-top">
          <span>Nhớ ra mật khẩu?</span>
          <a href="/login">Đăng nhập</a>
        </div>

        <div className="auth-form-wrap">
          <p className="auth-kicker">Reset password</p>
          <h2>Tạo mật khẩu mới.</h2>
          {!token ? (
            <p className="auth-intro">
              Liên kết không hợp lệ. Hãy mở đúng liên kết trong email, hoặc yêu cầu liên kết mới ở trang
              {" "}<a href="/login">đăng nhập</a> (mục “Quên mật khẩu?”).
            </p>
          ) : (
            <>
              <p className="auth-intro">
                Mật khẩu tối thiểu 8 ký tự. Liên kết chỉ dùng được một lần và hết hạn sau ít phút.
              </p>
              <form className="auth-form" onSubmit={submit}>
                <div className="auth-field">
                  <input
                    id="password"
                    type={show ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    placeholder=" "
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    disabled={done}
                  />
                  <label htmlFor="password">Mật khẩu mới</label>
                  <button className="auth-password-toggle" type="button" onClick={() => setShow((value) => !value)}>
                    {show ? "Ẩn" : "Hiện"}
                  </button>
                  <span className="auth-field-line" aria-hidden="true" />
                </div>
                <div className="auth-field">
                  <input
                    id="confirmPassword"
                    type={show ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={8}
                    placeholder=" "
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    required
                    disabled={done}
                  />
                  <label htmlFor="confirmPassword">Xác nhận mật khẩu</label>
                  <span className="auth-field-line" aria-hidden="true" />
                </div>
                <button className="auth-submit" type="submit" disabled={busy || done}>
                  <span>{busy ? "Đang lưu…" : done ? "Đã đổi mật khẩu" : "Đặt mật khẩu mới"}</span>
                  <span className="auth-submit-arrow">→</span>
                </button>
              </form>
            </>
          )}
          {message ? <p className="auth-intro" role="status">{message}</p> : null}
        </div>
      </section>
    </main>
  );
}
