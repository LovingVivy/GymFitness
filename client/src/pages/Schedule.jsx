import { useMemo, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { useAuth } from "../lib/authStore";
import "./Schedule.css";

const programs = {
  Gym: [
    ["Upper Body Strength", "18:30", "60 phút"],
    ["Cardio & Core", "07:00", "45 phút"],
    ["Lower Body Power", "18:00", "60 phút"],
    ["Mobility Recovery", "19:00", "40 phút"],
    ["Full Body", "17:30", "60 phút"],
    ["Active Rest", "08:00", "30 phút"],
    ["Rest day", "—", "Phục hồi"]
  ],
  Yoga: [
    ["Hatha nền tảng", "07:00", "45 phút"],
    ["Breathwork", "18:30", "30 phút"],
    ["Vinyasa Flow", "07:30", "50 phút"],
    ["Mobility", "19:00", "35 phút"],
    ["Balance Yoga", "17:30", "45 phút"],
    ["Yin phục hồi", "08:00", "60 phút"],
    ["Rest day", "—", "Phục hồi"]
  ]
};

const dayName = new Intl.DateTimeFormat("vi-VN", { weekday: "short" });
const monthName = new Intl.DateTimeFormat("vi-VN", { month: "long", year: "numeric" });

export default function Schedule() {
  const user = useAuth();
  const initialMode = user?.membership?.category || "Gym";
  const [mode, setMode] = useState(initialMode);
  const [notice, setNotice] = useState("");

  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setDate(date.getDate() + index);
    return date;
  }), []);

  if (!user?.membership) {
    return (
      <main className="schedule-page">
        <SiteHeader />
        <section className="schedule-locked">
          <span>Member schedule</span>
          <h1>Lịch tập dành cho<br /><em>hội viên IRONIX.</em></h1>
          <p>Đăng ký một gói hội viên để mở lịch Gym/Yoga và đặt buổi cùng PT.</p>
          <a href={user ? "/plans" : "/login"}>{user ? "Chọn gói tập" : "Đăng nhập"} →</a>
        </section>
        <CurtainFooter />
      </main>
    );
  }

  const requestPt = (date) => {
    if (!user.ptCredits?.remaining) {
      setNotice("Bạn chưa còn lượt PT. Hãy mua thêm tại trang gói tập.");
    } else {
      setNotice("Đã tạo yêu cầu PT cho ngày " + date.toLocaleDateString("vi-VN") + " (demo).");
    }
    window.setTimeout(() => setNotice(""), 2800);
  };

  return (
    <main className="schedule-page">
      <SiteHeader />
      <section className="schedule-hero">
        <div>
          <p>Training calendar</p>
          <h1>Lịch tập<br /><em>của bạn.</em></h1>
        </div>
        <aside>
          <span>Gói hiện tại</span>
          <strong>{user.membership.name}</strong>
          <small>{user.ptCredits.remaining} lượt PT còn lại</small>
        </aside>
      </section>

      <section className="schedule-shell">
        <header>
          <div><span>Tuần hiện tại</span><h2>{monthName.format(days[0])}</h2></div>
          <div className="schedule-tabs">
            {Object.keys(programs).map((item) => (
              <button key={item} type="button" className={mode === item ? "is-active" : ""} onClick={() => setMode(item)}>
                {item}
              </button>
            ))}
          </div>
        </header>

        <div className="calendar-grid">
          {days.map((date, index) => {
            const [activity, time, duration] = programs[mode][index];
            return (
              <article className={index === 0 ? "is-today" : ""} key={date.toISOString()}>
                <div className="calendar-date">
                  <span>{dayName.format(date)}</span>
                  <strong>{date.getDate()}</strong>
                  {index === 0 && <small>Hôm nay</small>}
                </div>
                <div className="calendar-session">
                  <span>{String(index + 1).padStart(2, "0")} · {mode}</span>
                  <h3>{activity}</h3>
                  <p>{time} · {duration}</p>
                </div>
                {activity !== "Rest day" && (
                  <button type="button" onClick={() => requestPt(date)}>Gọi PT <span>+</span></button>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <CurtainFooter />
      <div className={"schedule-toast " + (notice ? "is-visible" : "")}>{notice}</div>
    </main>
  );
}
