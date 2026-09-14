import { useMemo, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { updateCurrentUser, useAuth } from "../lib/authStore";
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

const availableTrainers = [
  { id: "pt-01", name: "Trần Hoàng Nam", initials: "HN", specialty: "Strength & Hypertrophy", experience: "6 năm kinh nghiệm", slots: ["07:00", "18:30"] },
  { id: "pt-02", name: "Lê Minh Khoa", initials: "MK", specialty: "Functional Fitness", experience: "5 năm kinh nghiệm", slots: ["09:00", "17:30"] },
  { id: "pt-03", name: "Nguyễn Thanh Vy", initials: "TV", specialty: "Yoga & Mobility", experience: "7 năm kinh nghiệm", slots: ["08:00", "19:00"] },
  { id: "pt-04", name: "Phạm Gia Hân", initials: "GH", specialty: "Fat loss coaching", experience: "4 năm kinh nghiệm", slots: ["10:30", "20:00"] }
];

const dayName = new Intl.DateTimeFormat("vi-VN", { weekday: "short" });
const monthName = new Intl.DateTimeFormat("vi-VN", { month: "long", year: "numeric" });
const fullDate = new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });

function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return year + "-" + month + "-" + day;
}

function startOfToday() {
  const today = new Date();
  return new Date(today.getFullYear(), today.getMonth(), today.getDate());
}

export default function Schedule() {
  const user = useAuth();
  const initialMode = user?.membership?.category || "Gym";
  const [mode, setMode] = useState(initialMode);
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState(null);
  const [notice, setNotice] = useState("");

  const monthDays = useMemo(() => {
    const count = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 0).getDate();
    return Array.from(
      { length: count },
      (_, index) => new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), index + 1)
    );
  }, [visibleMonth]);

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

  const showNotice = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2800);
  };

  const openTrainerPicker = (date, isPast) => {
    if (isPast) {
      showNotice("Không thể đặt PT cho ngày đã qua.");
      return;
    }
    if (!user.ptCredits?.remaining) {
      showNotice("Bạn chưa còn lượt PT. Hãy mua thêm tại trang gói tập.");
      return;
    }
    setSelectedDate(date);
  };

  const handleContextMenu = (event, date, isPast) => {
    event.preventDefault();
    openTrainerPicker(date, isPast);
  };

  const bookTrainer = (trainer) => {
    const dateKey = toDateKey(selectedDate);
    const existing = user.appointments || [];
    if (existing.some((appointment) => appointment.date === dateKey)) {
      showNotice("Ngày này đã có một yêu cầu PT.");
      setSelectedDate(null);
      return;
    }

    updateCurrentUser({
      appointments: [
        ...existing,
        {
          id: crypto.randomUUID(),
          date: dateKey,
          trainerId: trainer.id,
          trainerName: trainer.name,
          status: "REQUESTED",
          time: trainer.slots[0]
        }
      ],
      ptCredits: {
        ...user.ptCredits,
        remaining: Math.max(0, user.ptCredits.remaining - 1),
        reserved: user.ptCredits.reserved + 1
      }
    });
    setSelectedDate(null);
    showNotice("Đã gửi yêu cầu tới PT " + trainer.name + ". Một lượt PT đang được giữ.");
  };

  const changeMonth = (offset) => {
    setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
    setSelectedDate(null);
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
        <header className="schedule-toolbar">
          <div>
            <span>Lịch theo tháng · {monthDays.length} ngày</span>
            <h2>{monthName.format(visibleMonth)}</h2>
            <p>Cuộn ngang để xem lịch. Nhấp chuột phải vào ngày bạn muốn để chọn PT.</p>
          </div>
          <div className="schedule-controls">
            <div className="schedule-tabs">
              {Object.keys(programs).map((item) => (
                <button key={item} type="button" className={mode === item ? "is-active" : ""} onClick={() => setMode(item)}>
                  {item}
                </button>
              ))}
            </div>
            <div className="month-switch">
              <button type="button" onClick={() => changeMonth(-1)} aria-label="Tháng trước">←</button>
              <button type="button" onClick={() => changeMonth(1)} aria-label="Tháng sau">→</button>
            </div>
          </div>
        </header>

        <div className="timeline-viewport">
          <div className="calendar-grid">
            {monthDays.map((date, index) => {
              const [activity, time, duration] = programs[mode][index % programs[mode].length];
              const today = startOfToday();
              const isPast = date < today;
              const isToday = date.getTime() === today.getTime();
              const appointment = user.appointments?.find((item) => item.date === toDateKey(date));

              return (
                <article
                  className={(isPast ? "is-past " : "") + (isToday ? "is-today " : "") + (appointment ? "has-appointment" : "")}
                  key={date.toISOString()}
                  onContextMenu={(event) => handleContextMenu(event, date, isPast)}
                >
                  <div className="calendar-date">
                    <span>{dayName.format(date)}</span>
                    <strong>{String(date.getDate()).padStart(2, "0")}</strong>
                    <small>{isToday ? "Hôm nay" : toDateKey(date)}</small>
                  </div>
                  <div className="calendar-session">
                    <span>{mode} program</span>
                    <h3>{activity}</h3>
                    <p>{time} · {duration}</p>
                  </div>
                  {appointment ? (
                    <div className="appointment-chip">
                      <span>Đang chờ PT</span>
                      <strong>{appointment.trainerName}</strong>
                      <small>{appointment.time}</small>
                    </div>
                  ) : activity !== "Rest day" && (
                    <button type="button" disabled={isPast} onClick={() => openTrainerPicker(date, isPast)}>
                      Chọn PT <span>+</span>
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <CurtainFooter />

      {selectedDate && (
        <div className="pt-picker-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setSelectedDate(null);
        }}>
          <section className="pt-picker" role="dialog" aria-modal="true" aria-labelledby="ptPickerTitle">
            <header>
              <div>
                <span>Available trainers</span>
                <h2 id="ptPickerTitle">Chọn PT đang rảnh.</h2>
                <p>{fullDate.format(selectedDate)} · còn {user.ptCredits.remaining} lượt PT</p>
              </div>
              <button type="button" onClick={() => setSelectedDate(null)} aria-label="Đóng">×</button>
            </header>
            <div className="trainer-list">
              {availableTrainers.map((trainer) => (
                <button type="button" className="trainer-option" key={trainer.id} onClick={() => bookTrainer(trainer)}>
                  <span className="trainer-avatar">{trainer.initials}</span>
                  <span className="trainer-copy">
                    <small><i /> Đang rảnh</small>
                    <strong>{trainer.name}</strong>
                    <em>{trainer.specialty} · {trainer.experience}</em>
                  </span>
                  <span className="trainer-slots">{trainer.slots.map((slot) => <b key={slot}>{slot}</b>)}</span>
                  <span className="trainer-arrow">→</span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}

      <div className={"schedule-toast " + (notice ? "is-visible" : "")}>{notice}</div>
    </main>
  );
}
