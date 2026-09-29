import { useCallback, useEffect, useMemo, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { useAuth } from "../lib/authStore";
import { useToast } from "../lib/useToast";
import { navigateTo } from "../lib/navigation";
import { addTimeOff, deleteTimeOff, getMySchedule, saveMySchedule } from "../lib/ptApi";
import { WEEKDAYS, formatDateTime, formatTime } from "../lib/ptFormat";
import "./PTDashboard.css";
import "./PTSchedule.css";

const GYM_OFFSET = "+07:00";

const WEEKDAYS_MON_FRI = [1, 2, 3, 4, 5];

const PRESETS = [
  { label: "Tối trong tuần", hint: "T2–T6 · 17:00–21:00", days: WEEKDAYS_MON_FRI, start: "17:00", end: "21:00" },
  { label: "Sáng trong tuần", hint: "T2–T6 · 06:00–10:00", days: WEEKDAYS_MON_FRI, start: "06:00", end: "10:00" },
  { label: "Cuối tuần", hint: "T7, CN · 08:00–12:00", days: [6, 7], start: "08:00", end: "12:00" }
];

const toMinutes = (value) => {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
};

const emptyWeek = () => Object.fromEntries(WEEKDAYS.map((day) => [day.value, []]));

function fromApi(items) {
  const week = emptyWeek();
  items.forEach((item) => week[item.weekday].push({ start: item.start_time, end: item.end_time }));
  return week;
}

function toApi(week) {
  return WEEKDAYS.flatMap((day) =>
    week[day.value].map((range) => ({ weekday: day.value, start_time: range.start, end_time: range.end }))
  );
}

/** Lỗi của một ngày, hoặc chuỗi rỗng nếu hợp lệ. */
function dayError(ranges, sessionMinutes) {
  const sorted = [...ranges].sort((a, b) => a.start.localeCompare(b.start));
  for (const range of sorted) {
    if (!range.start || !range.end) return "Nhập đủ giờ bắt đầu và kết thúc.";
    if (toMinutes(range.end) - toMinutes(range.start) < sessionMinutes) {
      return `Mỗi khung cần dài ít nhất ${sessionMinutes} phút.`;
    }
  }
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].start < sorted[i - 1].end) return "Các khung giờ đang chồng lấn nhau.";
  }
  return "";
}

function todayInGym() {
  // "YYYY-MM-DD" theo giờ Việt Nam cho thuộc tính min của ô chọn ngày.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
}

export default function PTSchedule() {
  const user = useAuth();
  const isTrainer = user?.role === "PT";

  const [loaded, setLoaded] = useState(false);
  const [week, setWeek] = useState(emptyWeek);
  const [savedJson, setSavedJson] = useState("[]");
  const [sessionMinutes, setSessionMinutes] = useState(60);
  const [timezone, setTimezone] = useState("GMT+7");
  const [timeOff, setTimeOff] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [justOnboarded, setJustOnboarded] = useState(false);

  const [offDate, setOffDate] = useState(todayInGym);
  const [offFrom, setOffFrom] = useState("08:00");
  const [offTo, setOffTo] = useState("12:00");
  const [offAllDay, setOffAllDay] = useState(false);
  const [offReason, setOffReason] = useState("");

  const [notice, notify] = useToast(3600);

  const applyResponse = useCallback((data) => {
    const nextWeek = fromApi(data.weekly);
    setWeek(nextWeek);
    setSavedJson(JSON.stringify(toApi(nextWeek)));
    setSessionMinutes(data.session_minutes);
    setTimezone(data.timezone);
    setTimeOff(data.time_off);
    setConflicts(data.conflicts);
  }, []);

  useEffect(() => {
    if (!isTrainer) return;
    getMySchedule()
      .then((data) => {
        applyResponse(data);
        setLoaded(true);
      })
      .catch((error) => notify(error.message || "Không tải được lịch làm việc."));
  }, [applyResponse, isTrainer, notify]);

  const errors = useMemo(
    () => Object.fromEntries(WEEKDAYS.map((day) => [day.value, dayError(week[day.value], sessionMinutes)])),
    [week, sessionMinutes]
  );
  const hasErrors = Object.values(errors).some(Boolean);
  const dirty = JSON.stringify(toApi(week)) !== savedJson;
  const onboarding = loaded && savedJson === "[]";

  const summary = useMemo(() => {
    let minutes = 0;
    let sessions = 0;
    let days = 0;
    WEEKDAYS.forEach((day) => {
      if (week[day.value].length) days += 1;
      week[day.value].forEach((range) => {
        if (!range.start || !range.end) return;
        const span = Math.max(0, toMinutes(range.end) - toMinutes(range.start));
        minutes += span;
        sessions += Math.floor(span / sessionMinutes);
      });
    });
    return { hours: minutes / 60, sessions, days };
  }, [week, sessionMinutes]);

  const updateDay = (weekday, ranges) => setWeek((current) => ({ ...current, [weekday]: ranges }));

  const toggleDay = (weekday) => {
    updateDay(weekday, week[weekday].length ? [] : [{ start: "17:00", end: "21:00" }]);
  };

  const addRange = (weekday) => {
    const ranges = week[weekday];
    const last = ranges[ranges.length - 1];
    const start = last ? last.end : "17:00";
    const startMinutes = Math.min(toMinutes(start) + 60, 23 * 60);
    const end = `${String(Math.floor(startMinutes / 60)).padStart(2, "0")}:${String(startMinutes % 60).padStart(2, "0")}`;
    updateDay(weekday, [...ranges, { start, end: end > start ? end : "23:00" }]);
  };

  const editRange = (weekday, index, field, value) => {
    updateDay(
      weekday,
      week[weekday].map((range, i) => (i === index ? { ...range, [field]: value } : range))
    );
  };

  const removeRange = (weekday, index) => {
    updateDay(weekday, week[weekday].filter((_, i) => i !== index));
  };

  const applyPreset = (preset) => {
    const next = emptyWeek();
    preset.days.forEach((day) => {
      next[day] = [{ start: preset.start, end: preset.end }];
    });
    setWeek(next);
  };

  const handleSave = async () => {
    if (hasErrors) {
      notify("Hãy sửa các khung giờ đang báo lỗi trước khi lưu.");
      return;
    }
    const wasOnboarding = onboarding;
    setSaving(true);
    try {
      const data = await saveMySchedule(toApi(week));
      applyResponse(data);
      if (wasOnboarding && data.weekly.length) setJustOnboarded(true);
      notify(
        data.conflicts.length
          ? `Đã lưu. Có ${data.conflicts.length} buổi đã đặt nằm ngoài lịch mới.`
          : "Đã lưu lịch làm việc. Hội viên sẽ thấy giờ trống mới ngay."
      );
    } catch (error) {
      notify(error.message || "Không lưu được lịch làm việc.");
    } finally {
      setSaving(false);
    }
  };

  const handleAddTimeOff = async (event) => {
    event.preventDefault();
    const from = offAllDay ? "00:00" : offFrom;
    const to = offAllDay ? "23:59" : offTo;
    if (to <= from) {
      notify("Giờ kết thúc nghỉ phải sau giờ bắt đầu.");
      return;
    }
    try {
      const data = await addTimeOff({
        start_at: `${offDate}T${from}:00${GYM_OFFSET}`,
        end_at: `${offDate}T${to}:00${GYM_OFFSET}`,
        reason: offReason.trim() || null
      });
      applyResponse(data);
      setOffReason("");
      notify(
        data.conflicts.length
          ? `Đã thêm lịch nghỉ. ${data.conflicts.length} buổi đã đặt cần được huỷ.`
          : "Đã thêm lịch nghỉ, các giờ đó không còn nhận đặt."
      );
    } catch (error) {
      notify(error.message || "Không thêm được lịch nghỉ.");
    }
  };

  const handleDeleteTimeOff = async (item) => {
    try {
      applyResponse(await deleteTimeOff(item.id));
      notify("Đã xoá lịch nghỉ.");
    } catch (error) {
      notify(error.message || "Không xoá được lịch nghỉ.");
    }
  };

  if (!user || !isTrainer) {
    return (
      <main className="pt-page">
        <SiteHeader />
        <section className="pt-locked">
          <span>Trainer area</span>
          <h1>Lịch làm việc dành cho<br /><em>huấn luyện viên.</em></h1>
          <p>Đăng nhập bằng tài khoản PT để khai báo giờ làm việc hằng tuần.</p>
          <a href={user ? "/pt-booking" : "/login"}>{user ? "Đặt buổi cùng PT" : "Đăng nhập"} <b>→</b></a>
        </section>
        <CurtainFooter />
      </main>
    );
  }

  return (
    <main className="pt-page">
      <SiteHeader />

      <section className="pt-hero">
        <div>
          <p>{onboarding ? "Bước 1 · Thiết lập lịch làm việc" : `Lịch của bạn · ${timezone}`}</p>
          <h1>{onboarding ? <>Chào mừng,<br /><em>{user.fullName || "huấn luyện viên"}.</em></> : <>Lịch <em>làm việc.</em></>}</h1>
          <span>
            {onboarding
              ? "Chọn những giờ bạn nhận dạy mỗi tuần. Hội viên chỉ thấy và đặt được các ô trống trong khoảng này."
              : `Mỗi buổi ${sessionMinutes} phút. Hội viên đặt là xác nhận ngay — bạn không cần duyệt từng yêu cầu.`}
          </span>
        </div>
        <div className="pt-hero-stats">
          <div><strong>{summary.days}</strong><span>ngày / tuần</span></div>
          <div><strong>{summary.hours % 1 ? summary.hours.toFixed(1) : summary.hours}</strong><span>giờ / tuần</span></div>
          <div><strong>{summary.sessions}</strong><span>buổi tối đa</span></div>
        </div>
      </section>

      {justOnboarded ? (
        <section className="pts-banner">
          <div>
            <strong>Xong! Hội viên đã có thể đặt lịch với bạn.</strong>
            <span>Buổi mới sẽ hiện ở trang Buổi dạy kèm thông báo.</span>
          </div>
          <button type="button" onClick={() => navigateTo("/pt")}>Xem buổi dạy <b>→</b></button>
        </section>
      ) : null}

      {conflicts.length ? (
        <section className="pts-conflicts" role="alert">
          <strong>{conflicts.length} buổi đã đặt nằm ngoài lịch mới hoặc trùng lịch nghỉ</strong>
          <p>Buổi đã đặt không tự mất đi. Vào Buổi dạy để huỷ kèm lý do — hội viên được hoàn lượt.</p>
          <ul>
            {conflicts.map((booking) => (
              <li key={booking.id}>{formatDateTime(booking.start_at)} · {booking.member_name}</li>
            ))}
          </ul>
          <button type="button" onClick={() => navigateTo("/pt")}>Mở Buổi dạy <b>→</b></button>
        </section>
      ) : null}

      <section className="pt-grid pts-grid">
        <article className="pt-card pts-week">
          <header><span>01</span><h2>Giờ làm việc hằng tuần</h2></header>

          <div className="pts-presets">
            <span>Mẫu nhanh</span>
            {PRESETS.map((preset) => (
              <button key={preset.label} type="button" onClick={() => applyPreset(preset)}>
                {preset.label}<small>{preset.hint}</small>
              </button>
            ))}
            <button type="button" className="is-ghost" onClick={() => setWeek(emptyWeek())}>Xoá hết</button>
          </div>

          <ul className="pts-days">
            {WEEKDAYS.map((day) => {
              const ranges = week[day.value];
              const active = ranges.length > 0;
              return (
                <li key={day.value} className={active ? "is-active" : ""}>
                  <label className="pts-day-toggle">
                    <input type="checkbox" checked={active} onChange={() => toggleDay(day.value)} />
                    <span className="pts-switch" aria-hidden="true" />
                    <strong>{day.long}</strong>
                  </label>

                  <div className="pts-ranges">
                    {active ? (
                      ranges.map((range, index) => (
                        <div className="pts-range" key={index}>
                          <input
                            type="time"
                            step="1800"
                            value={range.start}
                            aria-label={`${day.long} bắt đầu`}
                            onChange={(event) => editRange(day.value, index, "start", event.target.value)}
                          />
                          <span>–</span>
                          <input
                            type="time"
                            step="1800"
                            value={range.end}
                            aria-label={`${day.long} kết thúc`}
                            onChange={(event) => editRange(day.value, index, "end", event.target.value)}
                          />
                          <button type="button" aria-label="Xoá khung giờ" onClick={() => removeRange(day.value, index)}>×</button>
                        </div>
                      ))
                    ) : (
                      <em>Nghỉ</em>
                    )}
                    {active ? (
                      <button type="button" className="pts-add" onClick={() => addRange(day.value)}>+ Thêm khung</button>
                    ) : null}
                    {errors[day.value] ? <p className="pts-error">{errors[day.value]}</p> : null}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="pts-save">
            <p>
              {dirty
                ? "Bạn có thay đổi chưa lưu."
                : onboarding
                  ? "Chọn ít nhất một ngày để hội viên thấy bạn trong danh sách PT."
                  : "Lịch đang được áp dụng."}
            </p>
            <button type="button" onClick={handleSave} disabled={saving || !dirty || hasErrors}>
              {saving ? "Đang lưu…" : onboarding ? "Lưu & bắt đầu nhận lịch" : "Lưu lịch làm việc"}
            </button>
          </div>
        </article>

        <article className="pt-card pts-off">
          <header><span>02</span><h2>Nghỉ đột xuất</h2></header>
          <p className="pts-hint">Chặn một khoảng thời gian để hội viên không đặt được. Buổi đã đặt trong khoảng đó vẫn giữ nguyên.</p>

          <form className="pt-slot-form" onSubmit={handleAddTimeOff}>
            <label><span>Ngày</span>
              <input type="date" value={offDate} min={todayInGym()} onChange={(e) => setOffDate(e.target.value)} required />
            </label>
            <label className="pts-allday">
              <span>Cả ngày</span>
              <input type="checkbox" checked={offAllDay} onChange={(e) => setOffAllDay(e.target.checked)} />
            </label>
            {!offAllDay ? (
              <>
                <label><span>Từ</span><input type="time" value={offFrom} onChange={(e) => setOffFrom(e.target.value)} required /></label>
                <label><span>Đến</span><input type="time" value={offTo} onChange={(e) => setOffTo(e.target.value)} required /></label>
              </>
            ) : null}
            <label className="pts-reason"><span>Lý do (không bắt buộc)</span>
              <input type="text" value={offReason} maxLength={255} onChange={(e) => setOffReason(e.target.value)} placeholder="Ví dụ: Đi thi chứng chỉ" />
            </label>
            <button type="submit">Thêm lịch nghỉ</button>
          </form>

          {timeOff.length === 0 ? (
            <p className="pt-empty">Chưa có lịch nghỉ nào sắp tới.</p>
          ) : (
            <ul className="pt-history-list">
              {timeOff.map((item) => (
                <li key={item.id} className="pts-off-item">
                  <div>
                    <strong>{formatDateTime(item.start_at)} → {formatTime(item.end_at)}</strong>
                    <span>{item.reason || "Không ghi lý do"}</span>
                  </div>
                  <button type="button" onClick={() => handleDeleteTimeOff(item)}>Xoá</button>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>

      <CurtainFooter />
      <div className={"pt-toast " + (notice ? "is-visible" : "")} aria-live="polite">{notice}</div>
    </main>
  );
}
