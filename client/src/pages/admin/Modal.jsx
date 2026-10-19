import { useEffect } from "react";
import { createPortal } from "react-dom";

/** Hộp thoại dùng chung cho các form quản trị. Esc hoặc bấm nền để đóng. */
export default function Modal({ title, onClose, children, footer }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="adm-overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="adm-modal" role="dialog" aria-modal="true" aria-labelledby="admModalTitle">
        <header>
          <h2 id="admModalTitle">{title}</h2>
          <button type="button" className="adm-close" onClick={onClose} aria-label="Đóng">×</button>
        </header>
        <div className="adm-modal-body">{children}</div>
        {footer ? <footer>{footer}</footer> : null}
      </div>
    </div>,
    document.body
  );
}

export function Field({ label, hint, children, wide = false }) {
  return (
    <label className={"adm-field" + (wide ? " is-wide" : "")}>
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}
