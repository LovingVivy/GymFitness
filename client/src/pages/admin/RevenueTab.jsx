import { useEffect, useState } from "react";
import RevenueChart, { SERIES } from "../../components/RevenueChart";
import { getMemberGrowth, getRevenue } from "../../lib/adminApi";
import { can, P } from "../../lib/permissions";
import { ExportButton } from "./TableTools";
import { money } from "../../lib/ptFormat";

const PERIODS = [
  { id: "WEEK", label: "Tuần", range: "12 tuần gần nhất", current: "Tuần này" },
  { id: "MONTH", label: "Tháng", range: "12 tháng gần nhất", current: "Tháng này" },
  { id: "QUARTER", label: "Quý", range: "8 quý gần nhất", current: "Quý này" },
  { id: "YEAR", label: "Năm", range: "5 năm gần nhất", current: "Năm nay" }
];

// Cùng màu xanh dương đã kiểm tra của biểu đồ doanh thu (nền #141414).
const MEMBER_SERIES = [{ key: "new_members", label: "Hội viên mới", color: "#3b82d6" }];

const count = (value) => Number(value || 0).toLocaleString("vi-VN");

const changeText = (change, fallback = "Chưa có kỳ trước để so sánh") =>
  change === null || change === undefined
    ? fallback
    : `${change >= 0 ? "▲" : "▼"} ${Math.abs(change).toLocaleString("vi-VN")}% so với kỳ trước`;

function RevenueSection({ report, meta }) {
  const [showTable, setShowTable] = useState(false);
  const current = report.buckets.at(-1);

  return (
    <>
      <div className="adm-kpis">
        <div className="adm-kpi is-hero">
          <span>Doanh thu · {meta.current.toLowerCase()}</span>
          <strong>{money(current.total)}</strong>
          <small>{changeText(report.change_percent)}</small>
        </div>
        <div className="adm-kpi">
          <span>Tổng {meta.range}</span>
          <strong>{money(report.total)}</strong>
          <small>{report.payment_count} giao dịch</small>
        </div>
        {SERIES.map((series) => (
          <div className="adm-kpi" key={series.key}>
            <span><i style={{ background: series.color }} />{series.label}</span>
            <strong>{money(report[series.key])}</strong>
            <small>
              {report.total > 0 ? `${Math.round((report[series.key] / report.total) * 100)}% tổng doanh thu` : "—"}
            </small>
          </div>
        ))}
      </div>

      <div className="adm-card">
        <div className="adm-card-head">
          <h3>Doanh thu theo {meta.label.toLowerCase()}</h3>
          <button type="button" className="adm-link" onClick={() => setShowTable((value) => !value)}>
            {showTable ? "Ẩn bảng số liệu" : "Xem bảng số liệu"}
          </button>
        </div>
        <RevenueChart buckets={report.buckets} />

        {showTable ? (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr><th>Kỳ</th><th className="is-num">Gói hội viên</th><th className="is-num">Buổi PT</th><th className="is-num">Tổng</th><th className="is-num">Giao dịch</th></tr>
              </thead>
              <tbody>
                {[...report.buckets].reverse().map((bucket) => (
                  <tr key={bucket.period_start}>
                    <td>{bucket.label}</td>
                    <td className="is-num">{money(bucket.membership_total)}</td>
                    <td className="is-num">{money(bucket.pt_total)}</td>
                    <td className="is-num"><b>{money(bucket.total)}</b></td>
                    <td className="is-num">{bucket.payment_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </>
  );
}

function MemberSection({ report, meta, overview }) {
  const [showTable, setShowTable] = useState(false);
  const current = report.buckets.at(-1);
  const activeShare =
    overview && overview.members > 0 ? Math.round((overview.active_members / overview.members) * 100) : null;

  return (
    <>
      <div className="adm-kpis">
        <div className="adm-kpi is-hero">
          <span>Tổng hội viên</span>
          <strong>{count(report.total_members)}</strong>
          <small>{changeText(report.total_growth_percent)}</small>
        </div>
        <div className="adm-kpi">
          <span>Hội viên mới · {meta.current.toLowerCase()}</span>
          <strong>{count(current.new_members)}</strong>
          <small>{changeText(report.change_percent)}</small>
        </div>
        <div className="adm-kpi">
          <span>Mới trong {meta.range}</span>
          <strong>{count(report.new_members)}</strong>
          <small>
            Trung bình {(report.new_members / report.buckets.length).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} hội viên/{meta.label.toLowerCase()}
          </small>
        </div>
        <div className="adm-kpi">
          <span>Đang còn gói tập</span>
          <strong>{overview ? count(overview.active_members) : "—"}</strong>
          <small>{activeShare === null ? "—" : `${activeShare}% tổng hội viên`}</small>
        </div>
      </div>

      <div className="adm-card">
        <div className="adm-card-head">
          <h3>Hội viên mới theo {meta.label.toLowerCase()}</h3>
          <button type="button" className="adm-link" onClick={() => setShowTable((value) => !value)}>
            {showTable ? "Ẩn bảng số liệu" : "Xem bảng số liệu"}
          </button>
        </div>
        <RevenueChart
          buckets={report.buckets}
          series={MEMBER_SERIES}
          totalKey="new_members"
          integer
          format={(value) => `${count(value)} hội viên mới`}
          footnote={(bucket) => `Tổng cuối kỳ: ${count(bucket.total_members)} hội viên`}
          ariaLabel="Biểu đồ hội viên mới theo kỳ, xem bảng số liệu bên dưới"
        />

        {showTable ? (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr><th>Kỳ</th><th className="is-num">Hội viên mới</th><th className="is-num">Tổng hội viên</th><th className="is-num">Tăng trưởng</th></tr>
              </thead>
              <tbody>
                {[...report.buckets].reverse().map((bucket) => {
                  const before = bucket.total_members - bucket.new_members;
                  return (
                    <tr key={bucket.period_start}>
                      <td>{bucket.label}</td>
                      <td className="is-num">{count(bucket.new_members)}</td>
                      <td className="is-num"><b>{count(bucket.total_members)}</b></td>
                      <td className="is-num">
                        {before > 0 ? `${((bucket.new_members / before) * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </>
  );
}

export default function RevenueTab({ notify, overview, user }) {
  const [period, setPeriod] = useState("MONTH");
  const [revenue, setRevenue] = useState(null);
  const [members, setMembers] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getRevenue(period)
      .then((data) => !cancelled && setRevenue(data))
      .catch((error) => notify(error.message || "Không tải được báo cáo doanh thu."));
    getMemberGrowth(period)
      .then((data) => !cancelled && setMembers(data))
      .catch((error) => notify(error.message || "Không tải được báo cáo hội viên."));
    return () => {
      cancelled = true;
    };
  }, [period, notify]);

  const meta = PERIODS.find((item) => item.id === period);
  // Vừa đổi kỳ: số liệu của kỳ cũ không khớp nhãn mới nên ẩn tới khi tải xong.
  const revenueReady = revenue && revenue.period === period ? revenue : null;
  const membersReady = members && members.period === period ? members : null;

  return (
    <div className="adm-panel">
      <div className="adm-toolbar">
        <div className="adm-segment" role="radiogroup" aria-label="Chu kỳ báo cáo">
          {PERIODS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="radio"
              aria-checked={period === item.id}
              className={period === item.id ? "is-active" : ""}
              onClick={() => setPeriod(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <span className="adm-muted">{meta.range} · giao dịch đã thanh toán · giờ Việt Nam</span>
        {can(user, P.REPORTS_EXPORT) ? (
          <div className="adm-toolbar-group">
            <ExportButton report="revenue" label="Xuất doanh thu" filters={{ period }} notify={notify} />
            <ExportButton report="member_growth" label="Xuất hội viên" filters={{ period }} notify={notify} />
          </div>
        ) : null}
      </div>

      {revenueReady ? <RevenueSection report={revenueReady} meta={meta} /> : <p className="adm-empty">Đang tải báo cáo doanh thu…</p>}
      {membersReady ? <MemberSection report={membersReady} meta={meta} overview={overview} /> : <p className="adm-empty">Đang tải báo cáo hội viên…</p>}
    </div>
  );
}
