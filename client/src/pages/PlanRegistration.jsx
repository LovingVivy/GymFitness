import { useEffect, useMemo, useState } from "react";
import { usePtPrice } from "../lib/usePtPrice";
import SiteHeader from "../components/SiteHeader";
import CurtainFooter from "../components/CurtainFooter";
import PaymentCheckout from "../components/PaymentCheckout";
import { createSubscription, listPlans, refreshProfile, updateProfile, useAuth } from "../lib/authStore";
import { navigateTo } from "../lib/navigation";
import "./PlanRegistration.css";

// Thông tin quảng bá thêm cho các gói có sẵn; gói do admin tạo dùng mô tả trong database.
const PLAN_META = {
  GYM_MONTHLY: { note: "Linh hoạt gia hạn mỗi tháng" },
  GYM_YEARLY: { originalPrice: 6000000, note: "Tiết kiệm 1.800.000đ" },
  YOGA_MONTHLY: { note: "Linh hoạt gia hạn mỗi tháng" },
  YOGA_YEARLY: { originalPrice: 4200000, note: "Tiết kiệm 1.260.000đ" }
};

// Dự phòng khi chưa tải được danh sách gói từ API.
const FALLBACK_PLANS = [
  { code: "GYM_MONTHLY", name: "Gym theo tháng", activity_type: "GYM", duration_months: 1, price: 500000 },
  { code: "GYM_YEARLY", name: "Gym theo năm", activity_type: "GYM", duration_months: 12, price: 4200000 },
  { code: "YOGA_MONTHLY", name: "Yoga theo tháng", activity_type: "YOGA", duration_months: 1, price: 350000 },
  { code: "YOGA_YEARLY", name: "Yoga theo năm", activity_type: "YOGA", duration_months: 12, price: 2940000 }
];

function toOption(item) {
  const months = item.duration_months;
  const period = months ? `${months} tháng` : `${item.duration_days} ngày`;
  const per = months === 12 ? "năm" : months === 1 ? "tháng" : period;
  const category = item.activity_type === "YOGA" ? "Yoga" : "Gym";
  const extra = PLAN_META[item.code] ?? {};
  return {
    key: item.code,
    id: item.id,
    name: item.name,
    category,
    price: Number(item.price),
    period,
    per,
    originalPrice: extra.originalPrice,
    note: extra.note ?? item.description ?? `Thời hạn ${period}`,
    isLong: (months ?? 0) >= 12
  };
}

const healthyWeightTables = {
  male: [[150, "47–54"], [155, "50–58"], [160, "54–61"], [165, "57–65"], [170, "60–69"], [175, "64–73"], [180, "67–77"], [185, "71–81"]],
  female: [[150, "42–49"], [155, "45–53"], [160, "48–56"], [165, "51–59"], [170, "54–63"], [175, "57–67"], [180, "60–70"], [185, "64–74"]]
};

const gymSchedules = {
  strength: [
    ["Thứ 2", "Thân trên", "60 phút"],
    ["Thứ 3", "Cardio nhẹ + Core", "40 phút"],
    ["Thứ 4", "Thân dưới", "60 phút"],
    ["Thứ 5", "Phục hồi chủ động", "30 phút"],
    ["Thứ 6", "Toàn thân", "60 phút"],
    ["Cuối tuần", "Nghỉ / đi bộ", "Tự do"]
  ],
  fatloss: [
    ["Thứ 2", "Strength toàn thân", "55 phút"],
    ["Thứ 3", "Zone 2 Cardio", "40 phút"],
    ["Thứ 4", "Strength thân dưới", "55 phút"],
    ["Thứ 5", "HIIT ngắn", "25 phút"],
    ["Thứ 6", "Strength thân trên", "55 phút"],
    ["Cuối tuần", "Đi bộ + Mobility", "45 phút"]
  ],
  fitness: [
    ["Thứ 2", "Full Body", "50 phút"],
    ["Thứ 3", "Mobility + đi bộ nhanh", "40 phút"],
    ["Thứ 4", "Cardio", "35 phút"],
    ["Thứ 5", "Nghỉ phục hồi", "—"],
    ["Thứ 6", "Functional Fitness", "50 phút"],
    ["Cuối tuần", "Lớp nhóm yêu thích", "45 phút"]
  ]
};

const yogaSchedule = [
  ["Thứ 2", "Hatha nền tảng", "45 phút"],
  ["Thứ 3", "Đi bộ nhẹ / nghỉ", "30 phút"],
  ["Thứ 4", "Vinyasa cơ bản", "45 phút"],
  ["Thứ 5", "Thở + Mobility", "25 phút"],
  ["Thứ 6", "Yoga thăng bằng", "40 phút"],
  ["Cuối tuần", "Yin / phục hồi", "45–60 phút"]
];


const formatCurrency = (value) => new Intl.NumberFormat("vi-VN").format(value) + "đ";

const EXPERIENCE_CODES = {
  beginner: "BEGINNER",
  intermediate: "INTERMEDIATE",
  advanced: "ADVANCED"
};

const GOAL_CODES = {
  fitness: "GENERAL_HEALTH",
  strength: "MUSCLE_GAIN",
  fatloss: "WEIGHT_LOSS"
};

export default function PlanRegistration() {
  const user = useAuth();
  const ptPrice = usePtPrice();
  const [selectedPlan, setSelectedPlan] = useState("GYM_YEARLY");
  const [ptSessions, setPtSessions] = useState(0);
  const [goal, setGoal] = useState("fitness");
  const [scheduleMode, setScheduleMode] = useState("gym");
  const [weightTableMode, setWeightTableMode] = useState("male");
  const [height, setHeight] = useState(170);
  const [weight, setWeight] = useState(65);
  const [toast, setToast] = useState("");
  const [catalogue, setCatalogue] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  // Cửa sổ thanh toán đang mở: { paymentId, title, step }. Gói + PT chung một mã QR.
  const [checkout, setCheckout] = useState(null);

  useEffect(() => {
    listPlans()
      .then(setCatalogue)
      .catch(() => setToast("Không tải được danh sách gói tập."));
  }, []);

  const bmi = useMemo(() => {
    const heightInMeters = Number(height) / 100;
    if (!heightInMeters || !weight) return null;
    return (Number(weight) / heightInMeters ** 2).toFixed(1);
  }, [height, weight]);

  const bmiLabel = !bmi
    ? "Chưa đủ dữ liệu"
    : bmi < 18.5
      ? "Nhẹ cân"
      : bmi < 25
        ? "Trong khoảng tham khảo"
        : bmi < 30
          ? "Trên khoảng tham khảo"
          : "Cần chú ý";

  // Danh sách gói lấy từ database nên gói admin vừa thêm hiện ngay.
  const options = useMemo(() => (catalogue.length ? catalogue : FALLBACK_PLANS).map(toOption), [catalogue]);
  const plan = options.find((item) => item.key === selectedPlan) ?? options[0];

  useEffect(() => {
    if (options.length && !options.some((item) => item.key === selectedPlan)) {
      setSelectedPlan(options[0].key);
    }
  }, [options, selectedPlan]);
  const ptTotal = ptSessions * (ptPrice ?? 0);
  const total = plan.price + ptTotal;

  const submitRegistration = async (event) => {
    event.preventDefault();

    if (!user) {
      localStorage.setItem("ironix_return_to", "/plans");
      navigateTo("/login");
      return;
    }

    if (user.role !== "USER") {
      setToast("Tài khoản nhân sự không mua gói hội viên. Hãy dùng tài khoản hội viên.");
      return;
    }

    if (ptSessions > 0 && !ptPrice) {
      setToast("Đang tải giá buổi PT, vui lòng thử lại sau giây lát.");
      return;
    }

    if (!event.currentTarget.reportValidity()) return;

    if (!plan?.id) {
      setToast("Gói tập chưa sẵn sàng, vui lòng thử lại sau.");
      return;
    }

    const data = new FormData(event.currentTarget);
    setSubmitting(true);
    try {
      // Lưu chỉ số cơ thể vào hồ sơ thật trước khi kích hoạt gói.
      await updateProfile({
        full_name: data.get("fullName"),
        date_of_birth: data.get("dateOfBirth") || null,
        height_cm: Number(height),
        weight_kg: Number(weight),
        experience_level: EXPERIENCE_CODES[data.get("experience")] ?? "BEGINNER",
        fitness_goal: GOAL_CODES[goal] ?? "GENERAL_HEALTH",
        weekly_training_sessions: Number(data.get("weeklySessions"))
      });

      const created = await createSubscription(plan.id, ptSessions);
      setCheckout({
        paymentId: created.payment.id,
        title: ptSessions > 0 ? `${plan.name} + ${ptSessions} buổi PT` : plan.name,
        step: "Gói hội viên"
      });
    } catch (error) {
      setToast(error.message || "Không thể hoàn tất đăng ký gói.");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePaid = async () => {
    setCheckout(null);
    await refreshProfile().catch(() => null);
    // Có lượt PT thì đưa thẳng sang chọn huấn luyện viên và giờ tập đầu tiên.
    const next = ptSessions > 0 ? "/pt-booking" : "/profile";
    setToast(
      ptSessions > 0
        ? "Thanh toán thành công. Chọn PT và giờ tập đầu tiên nhé!"
        : "Thanh toán thành công. Đang mở hồ sơ hội viên..."
    );
    window.setTimeout(() => navigateTo(next), 850);
  };

  const handleCloseCheckout = () => {
    setCheckout(null);
    setToast("Giao dịch vẫn chờ thanh toán. Bạn có thể tạo lại mã QR bất cứ lúc nào.");
  };

  return (
    <main className="plan-page">
      <SiteHeader />

      <section className="plan-hero">
        <p className="plan-eyebrow">Membership registration</p>
        <h1>Chọn kế hoạch.<br /><em>Bắt đầu mạnh mẽ.</em></h1>
        <p>Một mức phí rõ ràng, đầy đủ quyền sử dụng phòng tập và có thể bổ sung PT theo nhu cầu.</p>
      </section>

      <form className="plan-layout" onSubmit={submitRegistration}>
        <div className="plan-main">
          <section className="plan-section" aria-labelledby="membershipTitle">
            <div className="plan-section-heading">
              <span>01</span>
              <div>
                <h2 id="membershipTitle">Gói hội viên</h2>
                <p>Chọn chu kỳ phù hợp với cam kết tập luyện của bạn.</p>
              </div>
            </div>

            <div className="membership-grid">
              {options.map((option) => {
                const { key, price } = option;
                const isYearly = option.isLong;
                const shortPrice = price >= 1000000
                  ? `${(price / 1000000).toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}M`
                  : `${price / 1000}K`;

                return (
                  <label className={`membership-card ${isYearly ? "membership-card--featured" : ""} ${selectedPlan === key ? "is-selected" : ""}`} key={key}>
                    <input type="radio" name="plan" value={key} checked={selectedPlan === key} onChange={() => setSelectedPlan(key)} />
                    <span className="membership-radio" />
                    <span className="membership-tag">{option.category} · {option.originalPrice ? `Giảm ${Math.round((1 - price / option.originalPrice) * 100)}%` : isYearly ? "Dài hạn" : "Linh hoạt"}</span>
                    <h3>{option.name}</h3>
                    <div className="membership-price"><strong>{shortPrice}</strong><span>/ {option.per}</span></div>
                    {option.originalPrice ? <div className="membership-original">Giá gốc {formatCurrency(option.originalPrice)}</div> : null}
                    <p>{option.note}</p>
                    <ul>
                      <li>Không giới hạn buổi {option.category}</li>
                      <li>Đặt lịch trực tuyến trên hệ thống</li>
                      <li>{isYearly ? "Ưu tiên booking và đánh giá định kỳ" : "Theo dõi lịch sử luyện tập"}</li>
                    </ul>
                  </label>
                );
              })}
            </div>
          </section>

          <section className="plan-section" aria-labelledby="ptTitle">
            <div className="plan-section-heading">
              <span>02</span>
              <div>
                <h2 id="ptTitle">Huấn luyện viên cá nhân</h2>
                <p>Bổ sung PT theo từng buổi, không ràng buộc số lượng.</p>
              </div>
            </div>

            <div className="pt-card">
              <div className="pt-card-copy">
                <span className="pt-badge">PT 1:1</span>
                <h3>200.000đ <small>/ buổi</small></h3>
                <p>Đánh giá kỹ thuật, xây dựng giáo án và theo sát tiến độ cùng huấn luyện viên.</p>
              </div>
              <div className="pt-counter" aria-label="Số buổi PT">
                <button type="button" onClick={() => setPtSessions((value) => Math.max(0, value - 1))}>−</button>
                <div><strong>{ptSessions}</strong><span>buổi</span></div>
                <button type="button" onClick={() => setPtSessions((value) => Math.min(30, value + 1))}>+</button>
              </div>
            </div>
          </section>

          <section className="plan-section" aria-labelledby="bodyTitle">
            <div className="plan-section-heading">
              <span>03</span>
              <div>
                <h2 id="bodyTitle">Thông tin cơ thể & mục tiêu</h2>
                <p>Dữ liệu giúp hệ thống đưa ra lịch trình khởi đầu phù hợp hơn.</p>
              </div>
            </div>

            <div className="body-grid">
              <label className="plan-field"><span>Họ và tên</span><input name="fullName" type="text" defaultValue={user?.fullName || ""} placeholder="Nguyễn Văn A" required /></label>
              <label className="plan-field"><span>Ngày sinh</span><input name="dateOfBirth" type="date" max={new Date().toISOString().slice(0, 10)} /></label>
              <label className="plan-field"><span>Chiều cao (cm)</span><input name="height" type="number" min="120" max="230" value={height} onChange={(event) => setHeight(event.target.value)} required /></label>
              <label className="plan-field"><span>Cân nặng (kg)</span><input name="weight" type="number" min="30" max="250" step="0.1" value={weight} onChange={(event) => setWeight(event.target.value)} required /></label>
              <label className="plan-field"><span>Kinh nghiệm</span><select name="experience" defaultValue="beginner"><option value="beginner">Mới bắt đầu</option><option value="intermediate">Đã tập 6–18 tháng</option><option value="advanced">Trên 18 tháng</option></select></label>
              <label className="plan-field"><span>Số ngày có thể tập</span><select name="weeklySessions" defaultValue="3"><option value="2">2 ngày / tuần</option><option value="3">3 ngày / tuần</option><option value="4">4 ngày / tuần</option><option value="5">5+ ngày / tuần</option></select></label>
            </div>

            <div className="goal-selector">
              <span>Mục tiêu chính</span>
              <div>
                <button type="button" className={goal === "fitness" ? "is-active" : ""} onClick={() => setGoal("fitness")}>Thể lực tổng quát</button>
                <button type="button" className={goal === "strength" ? "is-active" : ""} onClick={() => setGoal("strength")}>Tăng cơ & sức mạnh</button>
                <button type="button" className={goal === "fatloss" ? "is-active" : ""} onClick={() => setGoal("fatloss")}>Giảm mỡ</button>
              </div>
            </div>

            <div className="body-result">
              <div><span>BMI tham khảo</span><strong>{bmi || "—"}</strong></div>
              <p>{bmiLabel}. Chỉ số này chỉ dùng để tham khảo ban đầu và không thay thế đánh giá chuyên môn.</p>
            </div>
          </section>

          <section className="plan-section" aria-labelledby="scheduleTitle">
            <div className="plan-section-heading">
              <span>04</span>
              <div>
                <h2 id="scheduleTitle">Lịch trình đề xuất</h2>
                <p>Gym và Yoga là hai lịch độc lập để bạn tham khảo theo chương trình đã chọn.</p>
              </div>
            </div>
            <div className="schedule-switch" aria-label="Chọn loại lịch tập">
              <button type="button" className={scheduleMode === "gym" ? "is-active" : ""} onClick={() => setScheduleMode("gym")}>Lịch Gym</button>
              <button type="button" className={scheduleMode === "yoga" ? "is-active" : ""} onClick={() => setScheduleMode("yoga")}>Lịch Yoga</button>
            </div>
            <div className="schedule-table">
              {(scheduleMode === "gym" ? gymSchedules[goal] : yogaSchedule).map(([day, activity, duration], index) => (
                <div className="schedule-row" key={day}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{day}</strong>
                  <p>{activity}</p>
                  <time>{duration}</time>
                </div>
              ))}
            </div>
            <div className="schedule-guidance">
              {scheduleMode === "gym" ? (
                <p>Lịch Gym phân bổ 2–3 buổi sức mạnh, cardio và ngày phục hồi; mục tiêu tổng vận động ở mức vừa là 150–300 phút mỗi tuần.</p>
              ) : (
                <p>Lịch Yoga bắt đầu bằng lớp nền tảng, xen kẽ phục hồi và tăng dần độ khó; người mới nên tập với hướng dẫn viên đủ chuyên môn.</p>
              )}
              <div>
                <a href="https://www.cdc.gov/physical-activity-basics/guidelines/adults.html" target="_blank" rel="noreferrer">CDC Guidelines ↗</a>
                <a href="https://www.acsm.org/docs/default-source/files-for-resource-library/resistance-training-for-health.pdf" target="_blank" rel="noreferrer">ACSM Resistance Training ↗</a>
                <a href="https://www.nccih.nih.gov/health/yoga-effectiveness-and-safety" target="_blank" rel="noreferrer">NCCIH Yoga Safety ↗</a>
              </div>
            </div>
          </section>

          <section className="plan-section" aria-labelledby="standardTitle">
            <div className="plan-section-heading">
              <span>05</span>
              <div>
                <h2 id="standardTitle">Bảng chiều cao & cân nặng tham khảo</h2>
                <p>Hai bảng tham khảo Nam/Nữ dành cho người trưởng thành; thể trạng thực tế còn phụ thuộc cấu tạo cơ thể.</p>
              </div>
            </div>
            <div className="schedule-switch weight-switch" aria-label="Chọn bảng cân nặng">
              <button type="button" className={weightTableMode === "male" ? "is-active" : ""} onClick={() => setWeightTableMode("male")}>Nam</button>
              <button type="button" className={weightTableMode === "female" ? "is-active" : ""} onClick={() => setWeightTableMode("female")}>Nữ</button>
            </div>
            <div className="weight-table-wrap">
              <table className="weight-table">
                <thead><tr><th>Chiều cao {weightTableMode === "male" ? "Nam" : "Nữ"}</th><th>Khoảng cân nặng</th><th>Chiều cao</th><th>Khoảng cân nặng</th></tr></thead>
                <tbody>
                  {healthyWeightTables[weightTableMode].slice(0, 4).map((item, index) => (
                    <tr key={item[0]}>
                      <td>{item[0]} cm</td><td>{item[1]} kg</td>
                      <td>{healthyWeightTables[weightTableMode][index + 4][0]} cm</td><td>{healthyWeightTables[weightTableMode][index + 4][1]} kg</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <aside className="order-summary">
          <p className="order-kicker">Your selection</p>
          <h2>Tóm tắt đăng ký</h2>
          <div className="order-plan"><div><strong>{plan.name}</strong><span>{plan.period} · {plan.note}</span></div><b>{formatCurrency(plan.price)}</b></div>
          <div className="order-line"><span>Gói PT ({ptSessions} buổi)</span><strong>{formatCurrency(ptTotal)}</strong></div>
          {plan.originalPrice ? <div className="order-saving"><span>Ưu đãi gói dài hạn</span><strong>−{Math.round((1 - plan.price / plan.originalPrice) * 100)}%</strong></div> : null}
          <div className="order-total"><span>Tổng thanh toán</span><strong>{formatCurrency(total)}</strong></div>
          <button className="order-submit" type="submit" disabled={submitting}>
            <span>
              {!user
                ? "Đăng nhập để tiếp tục"
                : submitting
                  ? "Đang tạo mã QR…"
                  : "Thanh toán bằng mã QR"}
            </span>
            <b>→</b>
          </button>
          <p className="order-note">Quét VietQR bằng app ngân hàng. Gói được kích hoạt tự động ngay khi ngân hàng xác nhận đã nhận tiền.</p>
          <div className="order-security"><span>✓</span><p><strong>Thanh toán an toàn</strong>Dữ liệu giao dịch được bảo vệ và ghi nhận minh bạch.</p></div>
        </aside>
      </form>

      <CurtainFooter />

      {checkout ? (
        <PaymentCheckout
          key={checkout.paymentId}
          paymentId={checkout.paymentId}
          title={checkout.title}
          step={checkout.step}
          onPaid={handlePaid}
          onClose={handleCloseCheckout}
        />
      ) : null}

      <div className={`plan-toast ${toast ? "is-visible" : ""}`} aria-live="polite">{toast}</div>
    </main>
  );
}


