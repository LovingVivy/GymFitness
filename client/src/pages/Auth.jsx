import { useEffect, useRef, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import "./Auth.css";

const coverImages = {
  login:
    "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=1800&q=90",
  signup:
    "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1800&q=90"
};

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M21.8 12.2c0-.7-.1-1.5-.2-2.2H12v4.2h5.5a4.7 4.7 0 0 1-2 3.1V20h3.3c1.9-1.8 3-4.4 3-7.8Z" />
      <path fill="#34A853" d="M12 22c2.7 0 5-.9 6.8-2.4l-3.3-2.7c-.9.6-2.1 1-3.5 1-2.6 0-4.8-1.8-5.6-4.1H3v2.8A10.3 10.3 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.4 13.8A6 6 0 0 1 6 12c0-.6.1-1.2.4-1.8V7.4H3A10 10 0 0 0 2 12c0 1.6.4 3.2 1 4.6l3.4-2.8Z" />
      <path fill="#EA4335" d="M12 6.1c1.5 0 2.8.5 3.8 1.5l2.9-2.8A9.7 9.7 0 0 0 3 7.4l3.4 2.8C7.2 7.9 9.4 6.1 12 6.1Z" />
    </svg>
  );
}

function AuthField({ id, label, type = "text", autoComplete, action, required = true }) {
  return (
    <div className="auth-field">
      <input id={id} name={id} type={type} placeholder=" " autoComplete={autoComplete} required={required} />
      <label htmlFor={id}>{label}</label>
      {action}
      <span className="auth-field-line" aria-hidden="true" />
    </div>
  );
}

export default function Auth({ mode }) {
  const isSignup = mode === "signup";
  const [showPassword, setShowPassword] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [toast, setToast] = useState("");
  const toastTimer = useRef(null);

  useEffect(() => {
    setForgotMode(false);
    setShowPassword(false);
  }, [mode]);

  useEffect(() => () => window.clearTimeout(toastTimer.current), []);

  const notify = (message) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 2600);
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    if (!event.currentTarget.reportValidity()) return;

    if (isSignup) {
      const data = new FormData(event.currentTarget);
      if (data.get("password") !== data.get("confirmPassword")) {
        notify("Mật khẩu xác nhận chưa trùng khớp.");
        return;
      }
    }

    notify(
      forgotMode
        ? "Đã tạo yêu cầu đặt lại mật khẩu."
        : isSignup
          ? "Đăng ký demo thành công."
          : "Đăng nhập demo thành công."
    );
  };

  return (
    <main className={`auth-page auth-page--${mode}`}>
      <section className="auth-cover" aria-label={isSignup ? "Đăng ký IRONIX" : "Đăng nhập IRONIX"}>
        <img src={coverImages[mode]} alt="Không gian tập luyện IRONIX" />
        <div className="auth-cover-shade" />

        <a className="auth-brand" href="/" aria-label="Về trang chủ IRONIX">
          <span>IRON</span>IX
        </a>

        <a className="auth-home-link" href="/">
          <span>←</span> Trang chủ
        </a>

        <div className="auth-cover-copy">
          <p>{isSignup ? "Start your journey" : "Welcome back, athlete"}</p>
          <h1>
            {isSignup ? (
              <>Your strongest<br /><em>chapter starts here.</em></>
            ) : (
              <>Consistency builds<br /><em>the strongest you.</em></>
            )}
          </h1>
          <div className="auth-cover-meta">
            <span>Train smart</span>
            <span>Track progress</span>
            <span>Stay consistent</span>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-top">
          <span>{isSignup ? "Đã có tài khoản?" : "Chưa là hội viên?"}</span>
          <a href={isSignup ? "/login" : "/signup"}>
            {isSignup ? "Đăng nhập" : "Tạo tài khoản"}
          </a>
        </div>

        <div className="auth-form-wrap" key={`${mode}-${forgotMode}`}>
          <p className="auth-kicker">
            {forgotMode ? "Account recovery" : isSignup ? "Join IRONIX" : "Member access"}
          </p>
          <h2>
            {forgotMode ? "Khôi phục tài khoản." : isSignup ? "Bắt đầu hành trình." : "Chào mừng trở lại."}
          </h2>
          <p className="auth-intro">
            {forgotMode
              ? "Nhập email đã đăng ký. Chúng tôi sẽ gửi hướng dẫn tạo mật khẩu mới."
              : isSignup
                ? "Tạo tài khoản để quản lý gói tập, đặt lớp và theo dõi tiến độ của bạn."
                : "Đăng nhập để check-in, quản lý lịch tập và tiếp tục mục tiêu của bạn."}
          </p>

          {!forgotMode && (
            <>
              <button className="auth-google" type="button" onClick={() => notify("Google login sẽ hoạt động khi kết nối backend.")}>
                <GoogleIcon />
                <span>{isSignup ? "Đăng ký với Google" : "Đăng nhập với Google"}</span>
              </button>
              <div className="auth-divider"><span>hoặc tiếp tục với email</span></div>
            </>
          )}

          <form className="auth-form" onSubmit={handleSubmit}>
            {isSignup && !forgotMode && (
              <AuthField id="fullName" label="Họ và tên" autoComplete="name" />
            )}

            <AuthField id="email" label="Địa chỉ email" type="email" autoComplete="email" />

            {isSignup && !forgotMode && (
              <AuthField id="phone" label="Số điện thoại" type="tel" autoComplete="tel" />
            )}

            {!forgotMode && (
              <AuthField
                id="password"
                label="Mật khẩu"
                type={showPassword ? "text" : "password"}
                autoComplete={isSignup ? "new-password" : "current-password"}
                action={(
                  <button className="auth-password-toggle" type="button" onClick={() => setShowPassword((value) => !value)}>
                    {showPassword ? "Ẩn" : "Hiện"}
                  </button>
                )}
              />
            )}

            {isSignup && !forgotMode && (
              <AuthField
                id="confirmPassword"
                label="Xác nhận mật khẩu"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
              />
            )}

            {!forgotMode && (
              <div className="auth-options">
                <label className="auth-check">
                  <input type="checkbox" required={isSignup} />
                  <span>{isSignup ? "Tôi đồng ý với điều khoản sử dụng" : "Ghi nhớ đăng nhập"}</span>
                </label>
                {!isSignup && (
                  <button className="auth-forgot" type="button" onClick={() => setForgotMode(true)}>
                    Quên mật khẩu?
                  </button>
                )}
              </div>
            )}

            <button className="auth-submit" type="submit">
              <span>{forgotMode ? "Gửi hướng dẫn" : isSignup ? "Tạo tài khoản" : "Đăng nhập"}</span>
              <span className="auth-submit-arrow">→</span>
            </button>

            {forgotMode && (
              <button className="auth-back" type="button" onClick={() => setForgotMode(false)}>
                ← Quay lại đăng nhập
              </button>
            )}
          </form>

          <p className="auth-legal">
            Bằng việc tiếp tục, bạn đồng ý với Điều khoản sử dụng và Chính sách bảo mật của IRONIX.
          </p>
        </div>
      </section>

      <CurtainFooter />

      <div className={`auth-toast ${toast ? "is-visible" : ""}`} aria-live="polite">
        <span className="auth-toast-dot" /> {toast}
      </div>
    </main>
  );
}


