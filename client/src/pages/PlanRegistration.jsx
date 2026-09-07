import { useMemo, useState } from "react";
import SiteHeader from "../components/SiteHeader";
import CurtainFooter from "../components/CurtainFooter";
import "./PlanRegistration.css";

const plans = {
  gymMonthly: {
    name: "Gym theo tháng",
    category: "Gym",
    price: 500000,
    period: "30 ngày",
    note: "Linh hoạt gia hạn mỗi tháng"
  },
  gymYearly: {
    name: "Gym theo năm",
    category: "Gym",
    price: 4200000,
    originalPrice: 6000000,
    period: "12 tháng",
    note: "Tiết kiệm 1.800.000đ"
  },
  yogaMonthly: {
    name: "Yoga theo tháng",
    category: "Yoga",
    price: 350000,
    period: "30 ngày",
    note: "Linh hoạt gia hạn mỗi tháng"
  },
  yogaYearly: {
    name: "Yoga theo năm",
    category: "Yoga",
    price: 2940000,
    originalPrice: 4200000,
    period: "12 tháng",
    note: "Tiết kiệm 1.260.000đ"
  }
};

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

export default function PlanRegistration() {
  const [selectedPlan, setSelectedPlan] = useState("gymYearly");
  const [ptSessions, setPtSessions] = useState(0);
  const [goal, setGoal] = useState("fitness");
  const [scheduleMode, setScheduleMode] = useState("gym");
  const [weightTableMode, setWeightTableMode] = useState("male");
  const [height, setHeight] = useState(170);
  const [weight, setWeight] = useState(65);
  const [toast, setToast] = useState("");

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

  const plan = plans[selectedPlan];
  const ptTotal = ptSessions * 200000;
  const total = plan.price + ptTotal;

  const submitRegistration = (event) => {
    event.preventDefault();
    setToast("Đã ghi nhận đăng ký demo. Kết nối API để hoàn tất thanh toán.");
    window.setTimeout(() => setToast(""), 3000);
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
              {Object.entries(plans).map(([key, option]) => {
                const isYearly = Boolean(option.originalPrice);
                const shortPrice = option.price >= 1000000
                  ? `${(option.price / 1000000).toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}M`
                  : `${option.price / 1000}K`;

                return (
                  <label className={`membership-card ${isYearly ? "membership-card--featured" : ""} ${selectedPlan === key ? "is-selected" : ""}`} key={key}>
                    <input type="radio" name="plan" value={key} checked={selectedPlan === key} onChange={() => setSelectedPlan(key)} />
                    <span className="membership-radio" />
                    <span className="membership-tag">{option.category} · {isYearly ? "Giảm 30%" : "Linh hoạt"}</span>
                    <h3>{option.name}</h3>
                    <div className="membership-price"><strong>{shortPrice}</strong><span>/ {isYearly ? "năm" : "tháng"}</span></div>
                    {isYearly && <div className="membership-original">Giá gốc {formatCurrency(option.originalPrice)}</div>}
                    <p>{isYearly ? option.note : `Gia hạn mỗi 30 ngày cho chương trình ${option.category}.`}</p>
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
              <label className="plan-field"><span>Họ và tên</span><input type="text" placeholder="Nguyễn Văn A" required /></label>
              <label className="plan-field"><span>Tuổi</span><input type="number" min="16" max="90" placeholder="25" required /></label>
              <label className="plan-field"><span>Chiều cao (cm)</span><input type="number" min="120" max="230" value={height} onChange={(event) => setHeight(event.target.value)} required /></label>
              <label className="plan-field"><span>Cân nặng (kg)</span><input type="number" min="30" max="250" step="0.1" value={weight} onChange={(event) => setWeight(event.target.value)} required /></label>
              <label className="plan-field"><span>Kinh nghiệm</span><select defaultValue="beginner"><option value="beginner">Mới bắt đầu</option><option value="intermediate">Đã tập 6–18 tháng</option><option value="advanced">Trên 18 tháng</option></select></label>
              <label className="plan-field"><span>Số ngày có thể tập</span><select defaultValue="3"><option value="2">2 ngày / tuần</option><option value="3">3 ngày / tuần</option><option value="4">4 ngày / tuần</option><option value="5">5+ ngày / tuần</option></select></label>
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
          {plan.originalPrice && <div className="order-saving"><span>Ưu đãi gói năm</span><strong>−30%</strong></div>}
          <div className="order-total"><span>Tổng thanh toán</span><strong>{formatCurrency(total)}</strong></div>
          <button className="order-submit" type="submit"><span>Tiếp tục thanh toán</span><b>→</b></button>
          <p className="order-note">Bạn có thể kiểm tra lại thông tin trước khi thanh toán. Chưa có khoản phí nào được thu ở bước này.</p>
          <div className="order-security"><span>✓</span><p><strong>Thanh toán an toàn</strong>Dữ liệu giao dịch được bảo vệ và ghi nhận minh bạch.</p></div>
        </aside>
      </form>

      <CurtainFooter />

      <div className={`plan-toast ${toast ? "is-visible" : ""}`} aria-live="polite">{toast}</div>
    </main>
  );
}


