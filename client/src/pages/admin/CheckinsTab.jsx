import { useCallback, useEffect, useState } from "react";
import { checkout, createCheckin, listCheckins } from "../../lib/adminApi";
import { can, P } from "../../lib/permissions";
import { ExportButton, SortHeader } from "./TableTools";
import { formatDateTime, formatTime } from "../../lib/ptFormat";

const PAGE_SIZE = 30;

const gymDate = (offsetDays = 0) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(
    new Date(Date.now() + offsetDays * 86_400_000)
  );

const duration = (minutes) => {
  if (minutes === null || minutes === undefined) return "—";
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours} giờ ${minutes % 60} phút` : `${minutes} phút`;
};

export default function CheckinsTab({ notify, onChange, user }) {
  const [sort, setSort] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [busy, setBusy] = useState(false);
  const [dateFrom, setDateFrom] = useState(() => gymDate(-6));
  const [dateTo, setDateTo] = useState(() => gymDate());
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [insideOnly, setInsideOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0 });

  const load = useCallback(() => {
    listCheckins({
      date_from: dateFrom,
      date_to: dateTo,
      search: query,
      inside_only: insideOnly,
      sort,
      page,
      page_size: PAGE_SIZE
    })
      .then(setData)
      .catch((error) => notify(error.message || "Không tải được lịch sử ra vào."));
  }, [dateFrom, dateTo, query, insideOnly, sort, page, notify]);

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

  const handleCheckin = async (event) => {
    event.preventDefault();
    if (!identifier.trim()) return;
    setBusy(true);
    try {
      const result = await createCheckin(identifier.trim());
      notify(`Đã check-in: ${result.member_name}.`);
      setIdentifier("");
      load();
      onChange();
    } catch (error) {
      notify(error.message || "Không check-in được.");
    } finally {
      setBusy(false);
    }
  };

  const handleCheckout = async (log) => {
    try {
      await checkout(log.id);
      notify(`Đã check-out: ${log.member_name}.`);
      load();
      onChange();
    } catch (error) {
      notify(error.message || "Không check-out được.");
    }
  };

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div className="adm-panel">
      <form className="adm-card adm-checkin-form" onSubmit={handleCheckin}>
        <div>
          <h3>Check-in tại quầy</h3>
          <p className="adm-muted">Nhập mã hội viên (MEM…), email hoặc số điện thoại. Hội viên cần có gói còn hiệu lực.</p>
        </div>
        <input
          value={identifier}
          onChange={(event) => setIdentifier(event.target.value)}
          placeholder="MEM000001"
          aria-label="Mã hội viên, email hoặc số điện thoại"
        />
        <button type="submit" className="adm-btn" disabled={busy}>{busy ? "Đang xử lý…" : "Check-in"}</button>
      </form>

      <div className="adm-toolbar">
        <input
          className="adm-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tìm tên, mã hội viên, email, số điện thoại…"
          aria-label="Tìm lượt ra vào"
        />
        <label className="adm-date">Từ
          <input type="date" value={dateFrom} max={dateTo} disabled={insideOnly} onChange={(event) => { setDateFrom(event.target.value); setPage(1); }} />
        </label>
        <label className="adm-date">Đến
          <input type="date" value={dateTo} min={dateFrom} disabled={insideOnly} onChange={(event) => { setDateTo(event.target.value); setPage(1); }} />
        </label>
        <label className="adm-check">
          <input type="checkbox" checked={insideOnly} onChange={(event) => { setInsideOnly(event.target.checked); setPage(1); }} />
          Chỉ người đang trong phòng
        </label>
        {can(user, P.REPORTS_EXPORT) ? (
          <ExportButton
            report="checkins"
            filters={{ search: query, date_from: dateFrom, date_to: dateTo, inside_only: insideOnly, sort }}
            notify={notify}
          />
        ) : null}
      </div>

      <div className="adm-card">
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead>
              <tr>
                <SortHeader label="Hội viên" column="member_name" sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <SortHeader label="Giờ vào" column="check_in_at" first="desc" sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th>Giờ ra</th>
                <th>Thời gian tập</th>
                <th>Gói</th>
                <th>Cách</th>
                <th aria-label="Thao tác" />
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr><td colSpan={7} className="adm-empty">Không có lượt ra vào trong khoảng này.</td></tr>
              ) : (
                data.items.map((log) => (
                  <tr key={log.id}>
                    <td>
                      <strong>{log.member_name}</strong>
                      <small>{log.member_code}{log.member_phone ? ` · ${log.member_phone}` : ""}</small>
                    </td>
                    <td>{formatDateTime(log.check_in_at)}</td>
                    <td>{log.check_out_at ? formatTime(log.check_out_at) : <span className="adm-badge is-ok">Đang trong phòng</span>}</td>
                    <td>{duration(log.duration_minutes)}</td>
                    <td>{log.plan_name || "—"}</td>
                    <td>
                      <span className="adm-tag">{log.method === "QR" ? "QR" : "Tại quầy"}</span>
                      {log.created_by_name ? <small>{log.created_by_name}</small> : null}
                    </td>
                    <td className="adm-row-actions">
                      {!log.check_out_at ? <button type="button" onClick={() => handleCheckout(log)}>Check-out</button> : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="adm-pager">
          <span>{data.total} lượt</span>
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Trước</button>
          <span>Trang {page}/{pages}</span>
          <button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Sau →</button>
        </div>
      </div>
    </div>
  );
}
