import { useCallback, useEffect, useState } from "react";
import { confirmPayment, downloadInvoice, listPayments, voidPayment } from "../../lib/adminApi";
import { can, P } from "../../lib/permissions";
import { formatDateTime, money } from "../../lib/ptFormat";
import Modal, { Field } from "./Modal";
import { ExportButton, SortHeader } from "./TableTools";

const PAGE_SIZE = 15;

const STATUS = {
  PENDING: { label: "Chờ thanh toán", tone: "is-warning" },
  PAID: { label: "Đã thu", tone: "is-ok" },
  VOID: { label: "Đã huỷ", tone: "is-muted" },
  FAILED: { label: "Thất bại", tone: "is-muted" },
  REFUNDED: { label: "Đã hoàn", tone: "is-muted" }
};
const PURPOSES = { MEMBERSHIP: "Gói hội viên", PT_CREDIT: "Buổi PT", PRODUCT_ORDER: "Đơn hàng" };
const METHODS = { QR: "QR chuyển khoản", CASH: "Tiền mặt", BANK_TRANSFER: "Chuyển khoản", CARD: "Thẻ" };

const describe = (payment) =>
  [payment.plan_name, payment.pt_quantity ? `${payment.pt_quantity} buổi PT` : null].filter(Boolean).join(" + ") ||
  PURPOSES[payment.purpose] ||
  payment.purpose;

function ConfirmForm({ payment, onSubmit, onClose }) {
  const [method, setMethod] = useState("CASH");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSubmit(method);
    } catch (err) {
      setError(err.message || "Không xác nhận được giao dịch.");
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`Xác nhận đã thu · ${payment.payment_number}`}
      onClose={onClose}
      footer={
        <>
          {error ? <p className="adm-error">{error}</p> : <span />}
          <div className="adm-actions">
            <button type="button" className="adm-btn is-ghost" onClick={onClose}>Đóng</button>
            <button type="submit" form="admConfirmForm" className="adm-btn" disabled={saving}>
              {saving ? "Đang xác nhận…" : `Đã thu ${money(payment.amount)}`}
            </button>
          </div>
        </>
      }
    >
      <form id="admConfirmForm" className="adm-form" onSubmit={submit}>
        <p className="adm-wide adm-note">
          <strong>{payment.member_name || "Khách"}</strong> · {describe(payment)}. Xác nhận sẽ kích hoạt quyền lợi ngay và không hoàn tác được.
        </p>
        {payment.bank_note ? <p className="adm-wide adm-warn">Ghi chú ngân hàng: {payment.bank_note}</p> : null}
        <Field label="Hình thức thu tiền" wide>
          <select value={method} onChange={(event) => setMethod(event.target.value)}>
            {Object.entries(METHODS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
      </form>
    </Modal>
  );
}

function VoidForm({ payment, onSubmit, onClose }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSubmit(reason.trim());
    } catch (err) {
      setError(err.message || "Không huỷ được giao dịch.");
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`Huỷ giao dịch · ${payment.payment_number}`}
      onClose={onClose}
      footer={
        <>
          {error ? <p className="adm-error">{error}</p> : <span />}
          <div className="adm-actions">
            <button type="button" className="adm-btn is-ghost" onClick={onClose}>Đóng</button>
            <button type="submit" form="admVoidForm" className="adm-btn is-danger" disabled={saving}>
              {saving ? "Đang huỷ…" : "Huỷ giao dịch"}
            </button>
          </div>
        </>
      }
    >
      <form id="admVoidForm" className="adm-form" onSubmit={submit}>
        <p className="adm-wide adm-note">
          Huỷ giao dịch {money(payment.amount)} của <strong>{payment.member_name || "khách"}</strong>. Gói tập và lượt PT đang chờ trong giao dịch này cũng bị huỷ; hội viên phải đăng ký lại nếu muốn mua.
        </p>
        <Field label="Lý do (không bắt buộc)" wide>
          <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={255} placeholder="Ví dụ: Khách đổi sang gói năm" autoFocus />
        </Field>
      </form>
    </Modal>
  );
}

export default function PaymentsTab({ notify, onChange, user }) {
  const [sort, setSort] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [purpose, setPurpose] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, paid_total: 0 });
  const [confirming, setConfirming] = useState(null);
  const [voiding, setVoiding] = useState(null);

  const load = useCallback(() => {
    listPayments({ search: query, status, purpose, date_from: dateFrom, date_to: dateTo, sort, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((error) => notify(error.message || "Không tải được danh sách giao dịch."));
  }, [query, status, purpose, dateFrom, dateTo, sort, page, notify]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const filter = (setter) => (event) => {
    setter(event.target.value);
    setPage(1);
  };
  const refresh = () => {
    load();
    onChange();
  };

  return (
    <div className="adm-panel">
      <div className="adm-toolbar">
        <input
          className="adm-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tìm mã giao dịch, mã ngân hàng, tên hoặc mã hội viên…"
          aria-label="Tìm giao dịch"
        />
        <select value={status} onChange={filter(setStatus)} aria-label="Lọc trạng thái">
          <option value="">Mọi trạng thái</option>
          {Object.entries(STATUS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
        </select>
        <select value={purpose} onChange={filter(setPurpose)} aria-label="Lọc loại giao dịch">
          <option value="">Mọi loại</option>
          {Object.entries(PURPOSES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label className="adm-date">Từ <input type="date" value={dateFrom} onChange={filter(setDateFrom)} /></label>
        <label className="adm-date">Đến <input type="date" value={dateTo} onChange={filter(setDateTo)} /></label>
        {can(user, P.REPORTS_EXPORT) ? (
          <ExportButton
            report="payments"
            filters={{ search: query, status, purpose, date_from: dateFrom, date_to: dateTo, sort }}
            notify={notify}
          />
        ) : null}
      </div>

      <div className="adm-card">
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead>
              <tr>
                <SortHeader label="Giao dịch" column="created_at" first="desc" sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th>Hội viên</th>
                <th>Nội dung</th>
                <SortHeader label="Số tiền" column="amount" first="desc" numeric sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th>Trạng thái</th>
                <th aria-label="Thao tác" />
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr><td colSpan={6} className="adm-empty">Không có giao dịch phù hợp.</td></tr>
              ) : (
                data.items.map((payment) => {
                  const state = STATUS[payment.status] || { label: payment.status, tone: "" };
                  return (
                    <tr key={payment.id}>
                      <td>
                        <strong>{payment.payment_number}</strong>
                        <small>Tạo {formatDateTime(payment.created_at)}</small>
                        {payment.external_reference ? <small>Mã ngân hàng {payment.external_reference}</small> : null}
                      </td>
                      <td>
                        <span>{payment.member_name || "—"}</span>
                        <small>{[payment.member_code, payment.member_phone || payment.member_email].filter(Boolean).join(" · ")}</small>
                      </td>
                      <td>
                        <span>{describe(payment)}</span>
                        <small>{METHODS[payment.method] || payment.method}</small>
                      </td>
                      <td className="is-num"><b>{money(payment.amount)}</b></td>
                      <td>
                        <span className={"adm-badge " + state.tone}>{state.label}</span>
                        {payment.paid_at ? <small>{formatDateTime(payment.paid_at)}</small> : null}
                        {payment.status === "PENDING" && payment.bank_note ? <small className="adm-warn">{payment.bank_note}</small> : null}
                        {payment.status === "VOID" && payment.failure_reason ? <small>{payment.failure_reason}</small> : null}
                      </td>
                      <td className="adm-row-actions">
                        {payment.status === "PENDING" && can(user, P.PAYMENTS_CONFIRM) ? (
                          <button type="button" onClick={() => setConfirming(payment)}>Xác nhận đã thu</button>
                        ) : null}
                        {payment.status === "PENDING" && can(user, P.PAYMENTS_VOID) ? (
                          <button type="button" className="is-danger" onClick={() => setVoiding(payment)}>Huỷ</button>
                        ) : null}
                        {payment.status === "PAID" ? (
                          <button
                            type="button"
                            onClick={() => downloadInvoice(payment.id).catch((error) => notify(error.message || "Không tải được hoá đơn."))}
                          >
                            Hoá đơn PDF
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <div className="adm-pager">
          <span>{data.total} giao dịch · đã thu {money(data.paid_total)}</span>
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Trước</button>
          <span>Trang {page}/{pages}</span>
          <button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Sau →</button>
        </div>
      </div>

      {confirming ? (
        <ConfirmForm
          payment={confirming}
          onClose={() => setConfirming(null)}
          onSubmit={async (method) => {
            await confirmPayment(confirming.id, method);
            notify(`Đã xác nhận ${confirming.payment_number}, quyền lợi đã được kích hoạt.`);
            setConfirming(null);
            refresh();
          }}
        />
      ) : null}
      {voiding ? (
        <VoidForm
          payment={voiding}
          onClose={() => setVoiding(null)}
          onSubmit={async (reason) => {
            await voidPayment(voiding.id, reason || null);
            notify(`Đã huỷ giao dịch ${voiding.payment_number}.`);
            setVoiding(null);
            refresh();
          }}
        />
      ) : null}
    </div>
  );
}
