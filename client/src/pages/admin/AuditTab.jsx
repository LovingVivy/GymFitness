import { Fragment, useCallback, useEffect, useState } from "react";
import { listAuditLogs } from "../../lib/adminApi";
import { ROLE_LABELS } from "../../lib/permissions";
import { formatDateTime } from "../../lib/ptFormat";
import { ExportButton } from "./TableTools";

const PAGE_SIZE = 20;

const ENTITIES = {
  user: "Tài khoản",
  membership_plan: "Gói tập",
  product: "Sản phẩm",
  payment: "Giao dịch"
};

const ACTIONS = {
  USER_CREATE: "Tạo tài khoản",
  USER_UPDATE: "Sửa tài khoản",
  USER_DELETE: "Xoá tài khoản",
  USER_RESET_PASSWORD: "Đặt lại mật khẩu",
  PASSWORD_RESET: "Tự đặt lại mật khẩu",
  TWO_FACTOR_ENABLE: "Bật xác thực 2 bước",
  TWO_FACTOR_DISABLE: "Tắt xác thực 2 bước",
  PLAN_CREATE: "Thêm gói",
  PLAN_UPDATE: "Sửa gói",
  PLAN_DELETE: "Xoá gói",
  PRODUCT_CREATE: "Thêm sản phẩm",
  PRODUCT_UPDATE: "Sửa sản phẩm",
  PRODUCT_DELETE: "Xoá sản phẩm",
  PAYMENT_CONFIRM: "Xác nhận thu tiền",
  PAYMENT_VOID: "Huỷ giao dịch",
  ADMIN_BOOTSTRAP: "Tạo admin mặc định"
};

const pretty = (value) => (value ? JSON.stringify(value, null, 2) : "—");

/** Nhật ký thao tác: ai làm gì, lúc nào; dữ liệu trước/sau là lịch sử phiên bản. */
export default function AuditTab({ notify }) {
  const [entity, setEntity] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const [data, setData] = useState({ items: [], total: 0 });

  const load = useCallback(() => {
    listAuditLogs({ entity_type: entity, search: query, date_from: dateFrom, date_to: dateTo, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((error) => notify(error.message || "Không tải được nhật ký thao tác."));
  }, [entity, query, dateFrom, dateTo, page, notify]);

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

  return (
    <div className="adm-panel">
      <div className="adm-toolbar">
        <input
          className="adm-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tìm người thực hiện hoặc hành động…"
          aria-label="Tìm trong nhật ký"
        />
        <select value={entity} onChange={filter(setEntity)} aria-label="Lọc đối tượng">
          <option value="">Mọi đối tượng</option>
          {Object.entries(ENTITIES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label className="adm-date">Từ <input type="date" value={dateFrom} onChange={filter(setDateFrom)} /></label>
        <label className="adm-date">Đến <input type="date" value={dateTo} onChange={filter(setDateTo)} /></label>
        <ExportButton
          report="audit_logs"
          filters={{ entity_type: entity, search: query, date_from: dateFrom, date_to: dateTo }}
          notify={notify}
        />
      </div>

      <div className="adm-card">
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead>
              <tr>
                <th>Thời điểm</th>
                <th>Người thực hiện</th>
                <th>Hành động</th>
                <th>Đối tượng</th>
                <th aria-label="Chi tiết" />
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr><td colSpan={5} className="adm-empty">Chưa có thao tác nào phù hợp.</td></tr>
              ) : (
                data.items.map((item) => (
                  <Fragment key={item.id}>
                    <tr>
                      <td><small>{formatDateTime(item.created_at)}</small></td>
                      <td>
                        <strong>{item.actor_name || item.actor_email || "Hệ thống"}</strong>
                        {item.actor_role ? <small>{ROLE_LABELS[item.actor_role] || item.actor_role}</small> : null}
                      </td>
                      <td><span className="adm-tag">{ACTIONS[item.action] || item.action}</span></td>
                      <td>
                        <span>{ENTITIES[item.entity_type] || item.entity_type}</span>
                        <small>{item.entity_id || "—"}</small>
                      </td>
                      <td className="adm-row-actions">
                        {item.before_data || item.after_data ? (
                          <button type="button" onClick={() => setOpen(open === item.id ? null : item.id)}>
                            {open === item.id ? "Ẩn" : "Trước / sau"}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                    {open === item.id ? (
                      <tr>
                        <td colSpan={5}>
                          <div className="adm-diff">
                            <div><small>Trước</small><pre>{pretty(item.before_data)}</pre></div>
                            <div><small>Sau</small><pre>{pretty(item.after_data)}</pre></div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="adm-pager">
          <span>{data.total} thao tác</span>
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Trước</button>
          <span>Trang {page}/{pages}</span>
          <button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Sau →</button>
        </div>
      </div>
    </div>
  );
}
