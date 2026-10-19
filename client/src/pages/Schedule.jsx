import { useCallback, useEffect, useMemo, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { refreshProfile, useAuth } from "../lib/authStore";
import { navigateTo } from "../lib/navigation";
import { createBooking, listBookableTrainers, listMyBookings, listTrainerSlots } from "../lib/ptApi";
import { GYM_TIME_ZONE, formatTime } from "../lib/ptFormat";
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

// Buổi PT hiện trên lịch: đang chờ tới giờ tập hoặc đã tập xong.
const CHIP_LABELS = { REQUESTED: "Đã đặt PT", ACCEPTED: "Đã đặt PT", COMPLETED: "Đã tập cùng PT" };

const dayName = new Intl.DateTimeFormat("vi-VN", { weekday: "short" });
const monthName = new Intl.DateTimeFormat("vi-VN", { month: "long", year: "numeric" });
const fullDate = new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
const gymDateKey = new Intl.DateTimeFormat("en-CA", { timeZone: GYM_TIME_ZONE });

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

/** "Nguyễn Nhật Nam" -> "NN": chữ đầu của hai từ cuối. */
const initials = (name) =>
  (name || "PT")
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();

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
  const [bookings, setBookings] = useState([]);
  // null = đang tải; mảng = PT đặt được kèm giờ trống trong ngày đang chọn.
  const [options, setOptions] = useState(null);
  const [busy, setBusy] = useState(false);

  const hasMembership = Boolean(user?.membership);

  const monthDays = useMemo(() => {
    const count = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 0).getDate();
    return Array.from(
      { length: count },
      (_, index) => new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), index + 1)
    );
  }, [visibleMonth]);

  const loadBookings = useCallback(() => {
    listMyBookings()
      .then(setBookings)
      .catch(() => {
        /* lịch vẫn dùng được khi chưa tải được buổi PT */
      });
  }, []);

  useEffect(() => {
    if (hasMembership) loadBookings();
  }, [hasMembership, loadBookings]);

  // Mỗi ngày hiện một buổi PT: ưu tiên buổi sớm nhất còn hiệu lực.
  const bookingByDate = useMemo(() => {
    const map = new Map();
    [...bookings]
      .filter((booking) => CHIP_LABELS[booking.status])
      .sort((a, b) => new Date(a.start_at) - new Date(b.start_at))
      .forEach((booking) => {
        const key = gymDateKey.format(new Date(booking.start_at));
        if (!map.has(key)) map.set(key, booking);
      });
    return map;
  }, [bookings]);

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
    window.setTimeout(() => setNotice(""), 3200);
  };

  const closePicker = () => {
    setSelectedDate(null);
    setOptions(null);
  };

  // PT có chuyên môn trùng gói tập, kèm các ô 60 phút còn trống đúng ngày được chọn.
  const openTrainerPicker = async (date, isPast) => {
    if (isPast) {
      showNotice("Không thể đặt PT cho ngày đã qua.");
      return;
    }
    const dateKey = toDateKey(date);
    setSelectedDate(date);
    setOptions(null);
    try {
      const trainers = await listBookableTrainers();
      const slotLists = await Promise.all(trainers.map((trainer) => listTrainerSlots(trainer.id)));
      setOptions(
        trainers
          .map((trainer, index) => ({
            trainer,
            slots: slotLists[index].filter((slot) => slot.local_date === dateKey)
          }))
          .filter((option) => option.slots.length > 0)
      );
    } catch (error) {
      showNotice(error.message || "Không tải được danh sách huấn luyện viên.");
      closePicker();
    }
  };

  const handleContextMenu = (event, date, isPast) => {
    event.preventDefault();
    openTrainerPicker(date, isPast);
  };

  const buyCredits = () => navigateTo(`/pt-booking?date=${toDateKey(selectedDate)}`);

  const bookSlot = async (trainer, slot) => {
    if (!user.ptCredits?.remaining) {
      buyCredits();
      return;
    }
    setBusy(true);
    try {
      await createBooking({ trainer_id: trainer.id, start_at: slot.start_at, notes: null });
      closePicker();
      showNotice(`Đã đặt buổi với ${trainer.full_name} lúc ${slot.local_start}. Huấn luyện viên đã nhận thông báo.`);
      loadBookings();
      refreshProfile().catch(() => null);
    } catch (error) {
      if (error.code === "NO_PT_CREDIT") {
        buyCredits();
        return;
      }
      showNotice(error.message || "Không thể đặt buổi.");
    } finally {
      setBusy(false);
    }
  };

  const changeMonth = (offset) => {
    setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
    closePicker();
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
              const booking = bookingByDate.get(toDateKey(date));

              return (
                <article
                  className={(isPast ? "is-past " : "") + (isToday ? "is-today " : "") + (booking ? "has-appointment" : "")}
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
                  {booking ? (
                    <a className="appointment-chip" href="/pt-booking">
                      <span>{CHIP_LABELS[booking.status]}</span>
                      <strong>{booking.trainer_name}</strong>
                      <small>{formatTime(booking.start_at)} – {formatTime(booking.end_at)}</small>
                    </a>
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
          if (event.target === event.currentTarget) closePicker();
        }}>
          <section className="pt-picker" role="dialog" aria-modal="true" aria-labelledby="ptPickerTitle">
            <header>
              <div>
                <span>Huấn luyện viên {user.membership.category}</span>
                <h2 id="ptPickerTitle">Chọn PT và giờ tập.</h2>
                <p>{fullDate.format(selectedDate)} · còn {user.ptCredits.remaining} lượt PT</p>
              </div>
              <button type="button" onClick={closePicker} aria-label="Đóng">×</button>
            </header>

            {options === null ? (
              <p className="pt-picker-empty">Đang tải giờ trống…</p>
            ) : options.length === 0 ? (
              <div className="pt-picker-empty">
                <p>Chưa có huấn luyện viên {user.membership.category} nào còn giờ trống trong ngày này. Giờ đặt được nằm trong 14 ngày tới và cách hiện tại ít nhất 2 tiếng.</p>
                <a href="/pt-booking">Xem các ngày khác →</a>
              </div>
            ) : (
              <div className="trainer-list">
                {!user.ptCredits?.remaining ? (
                  <p className="pt-picker-note">Bạn chưa có lượt PT. Chọn một giờ để chuyển sang trang mua lượt và đặt buổi.</p>
                ) : null}
                {options.map(({ trainer, slots }) => (
                  <div className="trainer-option is-real" key={trainer.id}>
                    <span className="trainer-avatar">{initials(trainer.full_name)}</span>
                    <span className="trainer-copy">
                      <small><i /> {slots.length} giờ trống</small>
                      <strong>{trainer.full_name}</strong>
                      <em>{trainer.employee_code} · {trainer.specialties.join(" · ")}</em>
                    </span>
                    <span className="trainer-slots">
                      {slots.map((slot) => (
                        <button
                          type="button"
                          key={slot.start_at}
                          disabled={busy}
                          onClick={() => bookSlot(trainer, slot)}
                          aria-label={`Đặt ${trainer.full_name} lúc ${slot.local_start}`}
                        >
                          {slot.local_start}
                        </button>
                      ))}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      <div className={"schedule-toast " + (notice ? "is-visible" : "")}>{notice}</div>
    </main>
  );
}
