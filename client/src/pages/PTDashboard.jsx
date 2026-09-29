import { useCallback, useEffect, useMemo, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import { useAuth } from "../lib/authStore";
import { useToast } from "../lib/useToast";
import { navigateTo } from "../lib/navigation";
import {
  cancelBooking,
  completeBooking,
  getMySchedule,
  getMyTrainerProfile,
  listTeachingSessions,
  markNoShow
} from "../lib/ptApi";
import {
  SESSION_STATUS,
  dayKey,
  formatDateTime,
  formatDay,
  formatTime,
  isActiveSession,
  money
} from "../lib/ptFormat";
import "./PTDashboard.css";

const CANCEL_PRESETS = ["Ốm đột xuất", "Có việc gia đình", "Trùng lịch công tác", "Phòng tập bảo trì"];

function LockedScreen({ signedIn }) {
  return (
    <main className="pt-page">
      <SiteHeader />
      <section className="pt-locked">
        <span>Trainer area</span>
        <h1>{signedIn ? <>Tài khoản này không phải<br /><em>huấn luyện viên.</em></> : <>Khu vực dành cho<br /><em>huấn luyện viên.</em></>}</h1>
        <p>Trang Buổi dạy chỉ dành cho tài khoản có vai trò PT.</p>
        <a href={signedIn ? "/pt-booking" : "/login"}>{signedIn ? "Đặt buổi cùng PT" : "Đăng nhập"} <b>→</b></a>
      </section>
      <CurtainFooter />
    </main>
  );
}

function SessionCard({ booking, children }) {
  const status = SESSION_STATUS[booking.status] ?? { label: booking.status, tone: "is-muted" };
  return (
    <li>
      <div className="pt-request-head">
        <div>
          <strong>{booking.member_name || "Hội viên"}</strong>
          <small>{booking.member_code} · {booking.member_phone || booking.member_email}</small>
        </div>
        <b className={"pt-badge " + status.tone}>{status.label}</b>
      </div>
      <p className="pt-request-time">
        {formatDateTime(booking.start_at)} → {formatTime(booking.end_at)}
        <span> · {booking.activity_type}</span>
      </p>
      {booking.notes ? <p className="pt-request-note">“{booking.notes}”</p> : null}
      {booking.cancellation_reason ? (
        <p className="pt-request-note">
          {booking.cancelled_by_role === "TRAINER" ? "Bạn huỷ" : "Hội viên huỷ"}: {booking.cancellation_reason}
        </p>
      ) : null}
      {children}
    </li>
  );
}

export default function PTDashboard() {
  const user = useAuth();
  const isTrainer = user?.role === "PT";

  const [profile, setProfile] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [cancellingId, setCancellingId] = useState("");
  const [cancelReason, setCancelReason] = useState(CANCEL_PRESETS[0]);
  const [now, setNow] = useState(() => Date.now());

  const [notice, notify] = useToast(3200);

  const load = useCallback(async () => {
    if (!isTrainer) return;
    try {
      const [trainerProfile, schedule, teaching] = await Promise.all([
        getMyTrainerProfile(),
        getMySchedule(),
        listTeachingSessions()
      ]);
      // Onboarding: PT chưa khai lịch thì chưa ai đặt được — đưa sang "Lịch của bạn".
      if (schedule.weekly.length === 0) {
        navigateTo("/pt-schedule");
        return;
      }
      setProfile(trainerProfile);
      setSessions(teaching);
      setNow(Date.now());
    } catch (error) {
      notify(error.message || "Không tải được buổi dạy.");
    }
  }, [isTrainer, notify]);

  useEffect(() => {
    load();
  }, [load]);

  // Buổi chuyển từ "sắp tới" sang "cần chốt" khi tới giờ mà không cần tải lại trang.
  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(tick);
  }, []);

  const { toClose, upcoming, history, todayCount } = useMemo(() => {
    const active = sessions.filter(isActiveSession);
    const started = (item) => new Date(item.start_at).getTime() <= now;
    const today = dayKey(new Date(now));
    return {
      toClose: active.filter(started),
      upcoming: active.filter((item) => !started(item)),
      history: sessions.filter((item) => !isActiveSession(item)),
      todayCount: active.filter((item) => dayKey(item.start_at) === today).length
    };
  }, [sessions, now]);

  const upcomingByDay = useMemo(() => {
    const groups = [];
    upcoming.forEach((booking) => {
      const key = dayKey(booking.start_at);
      const group = groups.find((item) => item.key === key);
      if (group) group.items.push(booking);
      else groups.push({ key, label: formatDay(booking.start_at), items: [booking] });
    });
    return groups;
  }, [upcoming]);

  if (!user || !isTrainer) return <LockedScreen signedIn={Boolean(user)} />;

  const run = async (action, message) => {
    try {
      await action();
      notify(message);
      await load();
    } catch (error) {
      notify(error.message || "Không thể cập nhật buổi dạy.");
    }
  };

  const handleCancel = (booking) => {
    if (!cancelReason.trim()) {
      notify("Vui lòng nhập lý do huỷ để thông báo cho hội viên.");
      return;
    }
    run(async () => {
      await cancelBooking(booking.id, cancelReason.trim());
      setCancellingId("");
      setCancelReason(CANCEL_PRESETS[0]);
    }, "Đã huỷ buổi, hội viên được hoàn lượt và nhận thông báo.");
  };

  return (
    <main className="pt-page">
      <SiteHeader />

      <section className="pt-hero">
        <div>
          <p>Buổi dạy · {profile?.employee_code || "PT"}</p>
          <h1>Buổi dạy của <em>{profile?.full_name || user.fullName}.</em></h1>
          <span>
            {profile?.specialties?.join(" · ") || "—"}
            {profile ? ` · ${money(profile.hourly_rate)}/buổi` : ""}
          </span>
        </div>
        <div className="pt-hero-stats">
          <div><strong>{todayCount}</strong><span>hôm nay</span></div>
          <div><strong>{upcoming.length}</strong><span>sắp tới</span></div>
          <div><strong>{toClose.length}</strong><span>cần chốt</span></div>
        </div>
      </section>

      <section className="pt-grid">
        <article className="pt-card">
          <header><span>01</span><h2>Cần chốt sau buổi tập</h2></header>
          {toClose.length === 0 ? (
            <p className="pt-empty">Không có buổi nào chờ chốt. Sau giờ tập, đánh dấu hoàn thành hoặc vắng mặt tại đây.</p>
          ) : (
            <ul className="pt-request-list">
              {toClose.map((booking) => (
                <SessionCard key={booking.id} booking={booking}>
                  <div className="pt-request-actions">
                    <button
                      type="button"
                      className="is-primary"
                      onClick={() => run(() => completeBooking(booking.id), "Đã ghi nhận buổi tập hoàn thành.")}
                    >
                      Hoàn thành
                    </button>
                    <button
                      type="button"
                      onClick={() => run(() => markNoShow(booking.id), "Đã ghi nhận hội viên vắng mặt.")}
                    >
                      Vắng mặt
                    </button>
                  </div>
                </SessionCard>
              ))}
            </ul>
          )}
        </article>

        <article className="pt-card">
          <header><span>02</span><h2>Sắp tới</h2></header>
          {upcomingByDay.length === 0 ? (
            <p className="pt-empty">
              Chưa có buổi nào được đặt. Hội viên thấy các giờ trống theo{" "}
              <a className="pt-inline-link" href="/pt-schedule">lịch làm việc</a> của bạn.
            </p>
          ) : (
            upcomingByDay.map((group) => (
              <div key={group.key} className="pt-day-group">
                <h3>{group.label}</h3>
                <ul className="pt-request-list">
                  {group.items.map((booking) => (
                    <SessionCard key={booking.id} booking={booking}>
                      {cancellingId === booking.id ? (
                        <div className="pt-reject-box">
                          <div className="pt-reject-presets">
                            {CANCEL_PRESETS.map((preset) => (
                              <button
                                key={preset}
                                type="button"
                                className={cancelReason === preset ? "is-active" : ""}
                                onClick={() => setCancelReason(preset)}
                              >
                                {preset}
                              </button>
                            ))}
                          </div>
                          <input
                            type="text"
                            value={cancelReason}
                            onChange={(event) => setCancelReason(event.target.value)}
                            placeholder="Lý do huỷ (bắt buộc, gửi cho hội viên)"
                          />
                          <div className="pt-reject-actions">
                            <button type="button" className="is-danger" onClick={() => handleCancel(booking)}>Huỷ buổi & hoàn lượt</button>
                            <button type="button" onClick={() => setCancellingId("")}>Giữ buổi</button>
                          </div>
                        </div>
                      ) : (
                        <div className="pt-request-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setCancellingId(booking.id);
                              setCancelReason(CANCEL_PRESETS[0]);
                            }}
                          >
                            Huỷ buổi
                          </button>
                        </div>
                      )}
                    </SessionCard>
                  ))}
                </ul>
              </div>
            ))
          )}
        </article>

        <article className="pt-card pt-history pt-span">
          <header><span>03</span><h2>Lịch sử</h2></header>
          {history.length === 0 ? (
            <p className="pt-empty">Chưa có buổi nào kết thúc hoặc bị huỷ.</p>
          ) : (
            <ul className="pt-history-list">
              {history.map((booking) => {
                const status = SESSION_STATUS[booking.status] ?? { label: booking.status, tone: "is-muted" };
                return (
                  <li key={booking.id}>
                    <strong>{formatDateTime(booking.start_at)}</strong>
                    <span>{booking.member_name} · {booking.member_code}</span>
                    <b className={"pt-badge " + status.tone}>{status.label}</b>
                    {booking.cancellation_reason ? <em>Lý do huỷ: {booking.cancellation_reason}</em> : null}
                  </li>
                );
              })}
            </ul>
          )}
        </article>
      </section>

      <section className="pt-links">
        <button type="button" onClick={() => navigateTo("/pt-schedule")}>
          Lịch của bạn <b>→</b>
        </button>
      </section>

      <CurtainFooter />
      <div className={"pt-toast " + (notice ? "is-visible" : "")} aria-live="polite">{notice}</div>
    </main>
  );
}
