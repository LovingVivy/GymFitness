import { useCallback, useEffect, useMemo, useState } from "react";
import CurtainFooter from "../components/CurtainFooter";
import PaymentCheckout from "../components/PaymentCheckout";
import SiteHeader from "../components/SiteHeader";
import { refreshProfile, useAuth } from "../lib/authStore";
import { useToast } from "../lib/useToast";
import { navigateTo } from "../lib/navigation";
import {
  cancelBooking,
  createBooking,
  getPtCredits,
  listMyBookings,
  listTrainerSlots,
  listTrainers,
  purchasePtCredits
} from "../lib/ptApi";
import {
  SESSION_STATUS,
  formatDateTime,
  formatLocalDate,
  formatTime,
  isActiveSession,
  money,
  weekdayShort
} from "../lib/ptFormat";
import "./PTBooking.css";

const PT_PRICE = 200000;

function LockedScreen() {
  return (
    <main className="ptb-page">
      <SiteHeader />
      <section className="ptb-locked">
        <span>Personal training</span>
        <h1>Đăng nhập để đặt<br /><em>buổi tập cùng PT.</em></h1>
        <p>Chọn huấn luyện viên, chọn giờ trống và buổi tập được xác nhận ngay.</p>
        <a href="/login">Đăng nhập <b>→</b></a>
      </section>
      <CurtainFooter />
    </main>
  );
}

export default function PTBooking() {
  const user = useAuth();
  const [credits, setCredits] = useState({ purchased: 0, reserved: 0, used: 0, available: 0 });
  const [trainers, setTrainers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [activity, setActivity] = useState("");
  const [selectedTrainer, setSelectedTrainer] = useState(null);
  const [slots, setSlots] = useState([]);
  const [selectedDay, setSelectedDay] = useState("");
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [notes, setNotes] = useState("");
  const [buyQuantity, setBuyQuantity] = useState(5);
  const [busy, setBusy] = useState(false);
  // Giao dịch mua lượt đang chờ chuyển khoản: { paymentId, quantity, slot? }.
  // Có slot nghĩa là mua xong sẽ tự đặt luôn giờ đã chọn.
  const [checkout, setCheckout] = useState(null);

  const membership = user?.membership;

  const [notice, notify] = useToast(3800);

  const load = useCallback(async () => {
    try {
      const [wallet, trainerList, myBookings] = await Promise.all([
        getPtCredits(),
        listTrainers(),
        listMyBookings()
      ]);
      setCredits(wallet);
      setTrainers(trainerList);
      setBookings(myBookings);
    } catch (error) {
      notify(error.message || "Không tải được dữ liệu PT.");
    }
  }, [notify]);

  useEffect(() => {
    if (!user) return;
    load();
  }, [load, user]);

  const loadSlots = useCallback(
    async (trainer) => {
      try {
        const data = await listTrainerSlots(trainer.id);
        setSlots(data);
        setSelectedDay((current) =>
          data.some((slot) => slot.local_date === current) ? current : data[0]?.local_date || ""
        );
      } catch (error) {
        notify(error.message || "Không tải được giờ trống của PT.");
        setSlots([]);
      }
    },
    [notify]
  );

  const visibleTrainers = useMemo(
    () => (activity ? trainers.filter((trainer) => trainer.specialties.includes(activity)) : trainers),
    [activity, trainers]
  );

  const days = useMemo(() => {
    const groups = [];
    slots.forEach((slot) => {
      const group = groups.find((item) => item.date === slot.local_date);
      if (group) group.slots.push(slot);
      else groups.push({ date: slot.local_date, slots: [slot] });
    });
    return groups;
  }, [slots]);

  const daySlots = days.find((day) => day.date === selectedDay)?.slots ?? [];
  const upcoming = bookings.filter(isActiveSession);
  const history = bookings.filter((item) => !isActiveSession(item));

  const openTrainer = (trainer) => {
    setSelectedTrainer(trainer);
    setSelectedSlot(null);
    setSelectedDay("");
    loadSlots(trainer);
  };

  const startPurchase = async (slot = null) => {
    setBusy(true);
    try {
      const created = await purchasePtCredits(buyQuantity);
      setCheckout({ paymentId: created.payment_id, quantity: buyQuantity, slot });
    } catch (error) {
      notify(error.message || "Không thể mua lượt PT.");
    } finally {
      setBusy(false);
    }
  };

  const book = async (slot) => {
    const booking = await createBooking({
      trainer_id: selectedTrainer.id,
      start_at: slot.start_at,
      notes: notes.trim() || null
    });
    setNotes("");
    setSelectedSlot(null);
    notify(`Đã đặt buổi với ${booking.trainer_name} lúc ${formatDateTime(booking.start_at)}.`);
  };

  const handleBook = async () => {
    if (!selectedTrainer || !selectedSlot) return;
    if (credits.available < 1) {
      startPurchase(selectedSlot);
      return;
    }
    setBusy(true);
    try {
      await book(selectedSlot);
    } catch (error) {
      if (error.code === "NO_PT_CREDIT") {
        startPurchase(selectedSlot);
        return;
      }
      notify(error.message || "Không thể đặt buổi.");
    } finally {
      setBusy(false);
      await Promise.all([load(), selectedTrainer ? loadSlots(selectedTrainer) : null]);
    }
  };

  const handlePaid = async () => {
    const { quantity, slot } = checkout;
    setCheckout(null);
    await refreshProfile().catch(() => null);
    if (slot && selectedTrainer) {
      try {
        await book(slot);
      } catch (error) {
        notify(`Đã cộng ${quantity} lượt nhưng chưa đặt được giờ: ${error.message}`);
      }
    } else {
      notify(`Đã cộng ${quantity} lượt PT vào ví.`);
    }
    await Promise.all([load(), selectedTrainer ? loadSlots(selectedTrainer) : null]);
  };

  const handleCancel = async (booking) => {
    const refundable = booking.refund_deadline && new Date(booking.refund_deadline) > new Date();
    const message = refundable
      ? `Huỷ buổi ${formatDateTime(booking.start_at)}? Bạn sẽ được hoàn 1 lượt.`
      : `Buổi ${formatDateTime(booking.start_at)} còn chưa tới 12 tiếng. Huỷ bây giờ sẽ mất lượt. Vẫn huỷ?`;
    if (!window.confirm(message)) return;
    try {
      const result = await cancelBooking(booking.id);
      notify(result.refunded ? "Đã huỷ buổi và hoàn 1 lượt vào ví." : "Đã huỷ buổi. Lượt của buổi này đã được tính.");
      await Promise.all([load(), selectedTrainer ? loadSlots(selectedTrainer) : null]);
    } catch (error) {
      notify(error.message || "Không thể huỷ buổi.");
    }
  };

  if (!user) return <LockedScreen />;

  const needsCredit = credits.available < 1;

  return (
    <main className="ptb-page">
      <SiteHeader />

      <section className="ptb-hero">
        <div>
          <p>Personal training · {user.memberCode || user.role}</p>
          <h1>Đặt buổi cùng <em>huấn luyện viên.</em></h1>
          <span>
            {membership
              ? `Gói ${membership.name} còn ${membership.daysRemaining} ngày · Đặt là xác nhận ngay`
              : "Chưa có gói hội viên đang hoạt động"}
          </span>
        </div>
        <div className="ptb-wallet">
          <div><strong>{credits.available}</strong><span>lượt khả dụng</span></div>
          <div><strong>{credits.reserved}</strong><span>đã đặt</span></div>
          <div><strong>{credits.used}</strong><span>đã dùng</span></div>
          <div><strong>{credits.purchased}</strong><span>đã mua</span></div>
        </div>
      </section>

      {!membership ? (
        <section className="ptb-grid">
          <article className="ptb-card ptb-span">
            <div className="ptb-empty">
              <p>Cần có gói hội viên đang hoạt động trước khi đặt PT. Bạn có thể mua kèm lượt PT ngay khi đăng ký gói.</p>
              <a href="/plans">Chọn gói tập →</a>
            </div>
          </article>
        </section>
      ) : (
        <section className="ptb-grid">
          <article className="ptb-card">
            <header><span>01</span><h2>Chọn huấn luyện viên</h2></header>
            <div className="ptb-filter">
              <button type="button" className={activity === "" ? "is-active" : ""} onClick={() => setActivity("")}>Tất cả</button>
              <button type="button" className={activity === "GYM" ? "is-active" : ""} onClick={() => setActivity("GYM")}>Gym</button>
              <button type="button" className={activity === "YOGA" ? "is-active" : ""} onClick={() => setActivity("YOGA")}>Yoga</button>
            </div>

            {visibleTrainers.length === 0 ? (
              <p className="ptb-empty-text">Chưa có huấn luyện viên phù hợp đang nhận lịch.</p>
            ) : (
              <ul className="ptb-trainers">
                {visibleTrainers.map((trainer) => (
                  <li key={trainer.id} className={selectedTrainer?.id === trainer.id ? "is-selected" : ""}>
                    <button type="button" onClick={() => openTrainer(trainer)}>
                      <div>
                        <strong>{trainer.full_name}</strong>
                        <small>{trainer.employee_code} · {trainer.specialties.join(" · ")}</small>
                        <em>Làm việc {trainer.schedule_weekdays.map(weekdayShort).join(" · ")}</em>
                      </div>
                      <b>→</b>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="ptb-card">
            <header><span>02</span><h2>Ví lượt PT</h2></header>
            <p className="ptb-hint">
              Mỗi buổi 60 phút dùng 1 lượt. Huỷ trước giờ tập ít nhất 12 tiếng được hoàn lượt; PT huỷ luôn hoàn lượt.
            </p>
            <div className="ptb-buy">
              <label>
                <span>Số buổi</span>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={buyQuantity}
                  onChange={(event) => setBuyQuantity(Math.max(1, Math.min(30, Number(event.target.value) || 1)))}
                />
              </label>
              <button type="button" onClick={() => startPurchase()} disabled={busy}>
                {busy ? "Đang tạo mã QR…" : `Mua ${buyQuantity} buổi · ${money(buyQuantity * PT_PRICE)}`}
              </button>
            </div>
          </article>

          <article className="ptb-card ptb-span">
            <header><span>03</span><h2>Chọn giờ tập</h2></header>
            {!selectedTrainer ? (
              <p className="ptb-empty-text">Chọn một huấn luyện viên để xem giờ trống trong 14 ngày tới.</p>
            ) : days.length === 0 ? (
              <p className="ptb-empty-text">{selectedTrainer.full_name} đã kín lịch trong 14 ngày tới. Hãy thử huấn luyện viên khác.</p>
            ) : (
              <>
                <div className="ptb-days" role="tablist" aria-label="Chọn ngày">
                  {days.map((day) => (
                    <button
                      key={day.date}
                      type="button"
                      role="tab"
                      aria-selected={day.date === selectedDay}
                      className={day.date === selectedDay ? "is-active" : ""}
                      onClick={() => {
                        setSelectedDay(day.date);
                        setSelectedSlot(null);
                      }}
                    >
                      <strong>{formatLocalDate(day.date)}</strong>
                      <small>{day.slots.length} giờ trống</small>
                    </button>
                  ))}
                </div>

                <div className="ptb-times">
                  {daySlots.map((slot) => (
                    <button
                      key={slot.start_at}
                      type="button"
                      className={selectedSlot?.start_at === slot.start_at ? "is-selected" : ""}
                      onClick={() => setSelectedSlot(slot)}
                    >
                      {slot.local_start}
                    </button>
                  ))}
                </div>

                {selectedSlot ? (
                  <div className="ptb-confirm">
                    <p>
                      Buổi 60 phút với <strong>{selectedTrainer.full_name}</strong> lúc{" "}
                      <strong>{selectedSlot.local_start}–{selectedSlot.local_end}, {formatLocalDate(selectedSlot.local_date)}</strong>
                    </p>
                    <input
                      type="text"
                      value={notes}
                      maxLength={500}
                      onChange={(event) => setNotes(event.target.value)}
                      placeholder="Ghi chú cho PT, ví dụ mục tiêu buổi tập (không bắt buộc)"
                    />
                    <button type="button" onClick={handleBook} disabled={busy}>
                      {busy
                        ? "Đang xử lý…"
                        : needsCredit
                          ? `Mua ${buyQuantity} buổi & đặt giờ này · ${money(buyQuantity * PT_PRICE)}`
                          : "Đặt buổi · dùng 1 lượt"}
                    </button>
                    {needsCredit ? <small>Bạn đã hết lượt. Sau khi thanh toán, giờ này sẽ được đặt tự động.</small> : null}
                  </div>
                ) : null}
              </>
            )}
          </article>

          <article className="ptb-card ptb-span">
            <header><span>04</span><h2>Buổi PT của tôi</h2></header>
            {bookings.length === 0 ? (
              <p className="ptb-empty-text">Bạn chưa đặt buổi PT nào.</p>
            ) : (
              <ul className="ptb-booking-list">
                {[...upcoming, ...history].map((booking) => {
                  const status = SESSION_STATUS[booking.status] ?? { label: booking.status, tone: "is-muted" };
                  const active = isActiveSession(booking);
                  const started = new Date(booking.start_at) <= new Date();
                  return (
                    <li key={booking.id} className={active ? "" : "is-past"}>
                      <div className="ptb-booking-head">
                        <strong>{booking.trainer_name}</strong>
                        <b className={"ptb-badge " + status.tone}>{status.label}</b>
                      </div>
                      <p>{formatDateTime(booking.start_at)} → {formatTime(booking.end_at)} · {booking.activity_type}</p>
                      {booking.notes ? <small>“{booking.notes}”</small> : null}
                      {booking.cancellation_reason ? (
                        <em className="ptb-reason">
                          {booking.cancelled_by_role === "TRAINER" ? "PT huỷ" : "Bạn huỷ"}: {booking.cancellation_reason}
                        </em>
                      ) : null}
                      {active && !started ? (
                        <div className="ptb-booking-actions">
                          <span>
                            {new Date(booking.refund_deadline) > new Date()
                              ? `Huỷ miễn phí trước ${formatDateTime(booking.refund_deadline)}`
                              : "Đã quá hạn huỷ miễn phí"}
                          </span>
                          <button type="button" onClick={() => handleCancel(booking)}>Huỷ buổi</button>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </article>
        </section>
      )}

      <section className="ptb-links">
        <button type="button" onClick={() => navigateTo("/profile")}>Về hồ sơ hội viên <b>→</b></button>
      </section>

      <CurtainFooter />

      {checkout ? (
        <PaymentCheckout
          key={checkout.paymentId}
          paymentId={checkout.paymentId}
          title={`${checkout.quantity} buổi PT 1:1`}
          step={checkout.slot ? "Mua lượt & đặt giờ" : "Mua lượt PT"}
          onPaid={handlePaid}
          onClose={() => setCheckout(null)}
        />
      ) : null}
      <div className={"ptb-toast " + (notice ? "is-visible" : "")} aria-live="polite">{notice}</div>
    </main>
  );
}
