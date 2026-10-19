import { useEffect, useRef, useState } from "react";
import { downloadFile, getJob, startExport } from "../../lib/adminApi";

/**
 * Column header that cycles its sort: first click sorts by `first` direction,
 * second click reverses, third click returns to the list's default order.
 */
export function SortHeader({ label, column, sort, onSort, numeric = false, first = "asc" }) {
  const asc = column;
  const desc = `-${column}`;
  const active = sort === asc || sort === desc;
  const isDesc = sort === desc;
  const [start, then] = first === "desc" ? [desc, asc] : [asc, desc];
  const next = !active ? start : sort === start ? then : "";

  return (
    <th
      className={"adm-sortable" + (numeric ? " is-num" : "") + (active ? " is-sorted" : "")}
      aria-sort={active ? (isDesc ? "descending" : "ascending") : "none"}
    >
      <button type="button" onClick={() => onSort(next)} aria-label={`Sắp xếp theo ${label}`}>
        {label}
        <span aria-hidden="true">{active ? (isDesc ? "↓" : "↑") : "↕"}</span>
      </button>
    </th>
  );
}

const FORMATS = [
  ["xlsx", "Excel (.xlsx)"],
  ["csv", "CSV"],
  ["pdf", "PDF"]
];

const cleanFilters = (filters) =>
  Object.fromEntries(
    Object.entries(filters || {}).filter(([, value]) => value !== "" && value !== null && value !== undefined && value !== false)
  );

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

/**
 * "Xuất file" menu: queues an export job on the server, polls until the file
 * is ready, then downloads it. Large exports never block the API.
 */
export function ExportButton({ report, filters, notify, label = "Xuất file" }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => {
      if (!ref.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const run = async (format) => {
    setOpen(false);
    setBusy(format);
    try {
      let job = await startExport(report, format, cleanFilters(filters));
      const started = Date.now();
      while (job.status === "PENDING" || job.status === "RUNNING") {
        if (Date.now() - started > 120_000) throw new Error("Xuất file đang mất nhiều thời gian, vui lòng thử lại sau.");
        await wait(800);
        job = await getJob(job.id);
      }
      if (job.status === "FAILED") throw new Error(job.error_message || "Xuất file thất bại.");
      const name = await downloadFile(job.download_url, job.file_name);
      notify(`Đã xuất ${name}.`);
    } catch (error) {
      notify(error.message || "Không xuất được file.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="adm-export" ref={ref}>
      <button
        type="button"
        className="adm-btn is-ghost"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={Boolean(busy)}
        onClick={() => setOpen((value) => !value)}
      >
        {busy ? `Đang xuất ${busy.toUpperCase()}…` : `${label} ↓`}
      </button>
      {open ? (
        <div className="adm-export-menu" role="menu">
          {FORMATS.map(([format, text]) => (
            <button key={format} type="button" role="menuitem" onClick={() => run(format)}>{text}</button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
