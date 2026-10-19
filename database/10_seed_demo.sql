-- GymFitness — dữ liệu mẫu số lượng lớn cho demo và báo cáo (hơn 2.000 bản ghi)
--
-- Tạo một phòng tập "đã hoạt động 12 tháng": 300 hội viên, 6 huấn luyện viên,
-- gói tập kèm lịch sử gia hạn, thanh toán, lượt ra vào, ví lượt PT và buổi PT đã dạy.
-- Nhờ vậy trang quản trị (tài khoản, giao dịch, ra vào, doanh thu, tăng trưởng)
-- có sẵn dữ liệu để tìm kiếm, lọc và phân trang.
--
--   * Mọi mốc thời gian tính lùi từ thời điểm chạy file, nên dữ liệu luôn "mới".
--   * Chạy lại an toàn: nếu dữ liệu mẫu đã có thì file không làm gì cả.
--   * Tài khoản mẫu KHÔNG đăng nhập được (password_hash không hợp lệ). Muốn dùng
--     thử một tài khoản, đặt lại mật khẩu cho nó ở trang quản trị.
--   * Nhận diện dữ liệu mẫu: email @demo.ironix.vn, mã hội viên DEMOxxxxxx,
--     mã PT DEMOPTxx, id bắt đầu bằng chữ "d".
--   * Không chạy file này trên môi trường production.
--
-- Chạy sau 09_admin_shop.sql:
--   python scripts/apply_sql.py database/10_seed_demo.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS _gf_seed_demo;

DELIMITER $$

CREATE PROCEDURE _gf_seed_demo()
seed: BEGIN
  DECLARE v_now DATETIME(6) DEFAULT UTC_TIMESTAMP(6);
  DECLARE v_branch_id CHAR(36) DEFAULT NULL;
  DECLARE v_members INT DEFAULT 300;
  -- Giờ phòng tập là UTC+7; database lưu UTC.
  DECLARE v_offset INT DEFAULT 420;
  DECLARE v_pt_price DECIMAL(14,2) DEFAULT 200000.00;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  IF EXISTS (SELECT 1 FROM users WHERE id = 'd1000000-0000-0000-0000-000000000001') THEN
    LEAVE seed;
  END IF;

  SELECT id INTO v_branch_id FROM branches WHERE code = 'IRONIX-Q1' LIMIT 1;

  DROP TEMPORARY TABLE IF EXISTS _seed_trainer;
  DROP TEMPORARY TABLE IF EXISTS _seed_member;
  DROP TEMPORARY TABLE IF EXISTS _seed_sub;
  DROP TEMPORARY TABLE IF EXISTS _seed_pt;
  DROP TEMPORARY TABLE IF EXISTS _seed_booking;

  START TRANSACTION;

  -- ==========================================================
  -- Huấn luyện viên mẫu: 4 PT Gym, 2 PT Yoga, làm việc T2–T7 08:00–20:00
  -- ==========================================================
  CREATE TEMPORARY TABLE _seed_trainer (
    t INT PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    trainer_id CHAR(36) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    gender VARCHAR(16) NOT NULL,
    activity_type VARCHAR(12) NOT NULL,
    extra_specialty VARCHAR(24) NOT NULL,
    bio TEXT NOT NULL,
    certifications TEXT NOT NULL,
    hourly_rate DECIMAL(14,2) NOT NULL
  );

  INSERT INTO _seed_trainer VALUES
    (1, 'd0000000-0000-0000-0000-000000000001', 'd0100000-0000-0000-0000-000000000001',
     'Phạm Quốc Bảo', 'MALE', 'GYM', 'MUSCLE_GAIN',
     'Chuyên tăng cơ và sức mạnh cho người mới bắt đầu.', 'ACE-CPT', 200000.00),
    (2, 'd0000000-0000-0000-0000-000000000002', 'd0100000-0000-0000-0000-000000000002',
     'Nguyễn Minh Khang', 'MALE', 'GYM', 'WEIGHT_LOSS',
     'Giảm mỡ, cải thiện thể lực và thói quen vận động.', 'NASM-CPT', 220000.00),
    (3, 'd0000000-0000-0000-0000-000000000003', 'd0100000-0000-0000-0000-000000000003',
     'Võ Thanh Tùng', 'MALE', 'GYM', 'REHABILITATION',
     'Phục hồi sau chấn thương, chỉnh tư thế và kỹ thuật.', 'NSCA-CSCS', 250000.00),
    (4, 'd0000000-0000-0000-0000-000000000004', 'd0100000-0000-0000-0000-000000000004',
     'Đặng Ngọc Ánh', 'FEMALE', 'GYM', 'WEIGHT_LOSS',
     'Huấn luyện nữ: siết dáng, tăng sức bền.', 'ISSA-CPT', 200000.00),
    (5, 'd0000000-0000-0000-0000-000000000005', 'd0100000-0000-0000-0000-000000000005',
     'Trần Khánh Linh', 'FEMALE', 'YOGA', 'FLEXIBILITY',
     'Hatha và Vinyasa, tập trung độ linh hoạt và hơi thở.', 'RYT-200', 180000.00),
    (6, 'd0000000-0000-0000-0000-000000000006', 'd0100000-0000-0000-0000-000000000006',
     'Lê Phương Thảo', 'FEMALE', 'YOGA', 'REHABILITATION',
     'Yoga trị liệu cho cổ, vai, gáy và lưng dưới.', 'RYT-500', 190000.00);

  INSERT INTO users (id, email, phone, password_hash, role, status, email_verified_at, created_at)
  SELECT user_id,
         CONCAT('pt.demo', LPAD(t, 2, '0'), '@demo.ironix.vn'),
         CONCAT('0966', LPAD(t, 6, '0')),
         '!demo-no-login', 'PT', 'ACTIVE',
         v_now - INTERVAL 400 DAY, v_now - INTERVAL 400 DAY
  FROM _seed_trainer;

  INSERT INTO user_profiles (user_id, full_name, gender, experience_level, created_at)
  SELECT user_id, full_name, gender, 'ADVANCED', v_now - INTERVAL 400 DAY
  FROM _seed_trainer;

  INSERT INTO trainer_profiles
    (id, user_id, employee_code, branch_id, bio, certifications, hourly_rate, status, created_at)
  SELECT trainer_id, user_id, CONCAT('DEMOPT', LPAD(t, 2, '0')), v_branch_id,
         bio, certifications, hourly_rate, 'ACTIVE', v_now - INTERVAL 400 DAY
  FROM _seed_trainer;

  INSERT INTO trainer_specialties (trainer_id, specialty)
  SELECT trainer_id, activity_type FROM _seed_trainer;

  INSERT INTO trainer_specialties (trainer_id, specialty)
  SELECT trainer_id, extra_specialty FROM _seed_trainer;

  INSERT INTO trainer_weekly_schedule (id, trainer_id, weekday, start_time, end_time)
  WITH RECURSIVE days (d) AS (
    SELECT 1 UNION ALL SELECT d + 1 FROM days WHERE d < 6
  )
  SELECT CONCAT('d0200000-0000-0000-0000-', LPAD(t * 10 + d, 12, '0')),
         trainer_id, d, '08:00:00', '20:00:00'
  FROM _seed_trainer
  JOIN days;

  -- ==========================================================
  -- Hội viên mẫu: đăng ký rải đều trong khoảng 12 tháng gần đây
  -- ==========================================================
  CREATE TEMPORARY TABLE _seed_member (
    n INT PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    member_id CHAR(36) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    gender VARCHAR(16) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    joined_at DATETIME(6) NOT NULL,
    plan_code VARCHAR(40) NOT NULL,
    -- Số lần hội viên gói tháng chịu gia hạn trước khi nghỉ.
    loyalty INT NOT NULL,
    account_status VARCHAR(16) NOT NULL
  );

  INSERT INTO _seed_member
  WITH RECURSIVE seq (n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < v_members
  )
  SELECT
    n,
    CONCAT('d1000000-0000-0000-0000-', LPAD(n, 12, '0')),
    CONCAT('d2000000-0000-0000-0000-', LPAD(n, 12, '0')),
    CONCAT_WS(' ',
      ELT(1 + CRC32(CONCAT('family', n)) % 14,
          'Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan',
          'Vũ', 'Võ', 'Đặng', 'Bùi', 'Đỗ', 'Hồ', 'Ngô'),
      IF(CRC32(CONCAT('gender', n)) % 2 = 0,
         ELT(1 + CRC32(CONCAT('middle', n)) % 6,
             'Văn', 'Minh', 'Quốc', 'Đức', 'Hoàng', 'Thanh'),
         ELT(1 + CRC32(CONCAT('middle', n)) % 6,
             'Thị', 'Ngọc', 'Thu', 'Mai', 'Khánh', 'Phương')),
      IF(CRC32(CONCAT('gender', n)) % 2 = 0,
         ELT(1 + CRC32(CONCAT('given', n)) % 12,
             'An', 'Bình', 'Cường', 'Dũng', 'Hải', 'Huy',
             'Khoa', 'Long', 'Nam', 'Phúc', 'Quân', 'Tuấn'),
         ELT(1 + CRC32(CONCAT('given', n)) % 12,
             'Anh', 'Chi', 'Dung', 'Hà', 'Hương', 'Lan',
             'Linh', 'My', 'Nga', 'Nhi', 'Trang', 'Vy'))),
    IF(CRC32(CONCAT('gender', n)) % 2 = 0, 'MALE', 'FEMALE'),
    CONCAT('hoivien', LPAD(n, 4, '0'), '@demo.ironix.vn'),
    CONCAT('0977', LPAD(n, 6, '0')),
    v_now - INTERVAL (2 + CRC32(CONCAT('joined', n)) % 360) DAY
          - INTERVAL (CRC32(CONCAT('minute', n)) % 840) MINUTE,
    ELT(1 + n % 10, 'GYM_MONTHLY', 'GYM_MONTHLY', 'GYM_MONTHLY', 'GYM_MONTHLY', 'GYM_YEARLY',
                    'GYM_YEARLY', 'YOGA_MONTHLY', 'YOGA_MONTHLY', 'YOGA_YEARLY', 'GYM_MONTHLY'),
    (n * 31) % 12,
    CASE WHEN n % 41 = 0 THEN 'SUSPENDED' WHEN n % 53 = 0 THEN 'INACTIVE' ELSE 'ACTIVE' END
  FROM seq;

  INSERT INTO users
    (id, email, phone, password_hash, role, status, email_verified_at, created_at)
  SELECT user_id, email, phone, '!demo-no-login', 'USER', account_status, joined_at, joined_at
  FROM _seed_member;

  INSERT INTO user_profiles
    (user_id, full_name, date_of_birth, gender, height_cm, weight_kg,
     experience_level, fitness_goal, weekly_training_sessions, created_at)
  SELECT user_id,
         full_name,
         DATE_SUB(DATE(v_now), INTERVAL (18 * 365 + (n * 2741) % (27 * 365)) DAY),
         gender,
         IF(gender = 'MALE', 162 + n % 20, 150 + n % 18),
         IF(gender = 'MALE', 58 + (n * 3) % 30, 45 + (n * 3) % 22),
         ELT(1 + n % 4, 'BEGINNER', 'BASIC', 'INTERMEDIATE', 'ADVANCED'),
         IF(plan_code LIKE 'YOGA%',
            ELT(1 + n % 2, 'FLEXIBILITY', 'GENERAL_HEALTH'),
            ELT(1 + n % 3, 'WEIGHT_LOSS', 'MUSCLE_GAIN', 'GENERAL_HEALTH')),
         2 + n % 4,
         joined_at
  FROM _seed_member;

  INSERT INTO members
    (id, member_code, user_id, home_branch_id, full_name, email, phone,
     joined_at, status, created_at)
  SELECT member_id, CONCAT('DEMO', LPAD(n, 6, '0')), user_id, v_branch_id,
         full_name, email, phone, joined_at, account_status, joined_at
  FROM _seed_member;

  -- ==========================================================
  -- Gói tập: kỳ đầu (k = 0) cho mọi hội viên, hội viên gói tháng gia hạn nối
  -- tiếp tối đa `loyalty` lần. Kỳ đã qua là EXPIRED, kỳ còn hạn là ACTIVE.
  -- ==========================================================
  CREATE TEMPORARY TABLE _seed_sub (
    n INT NOT NULL,
    k INT NOT NULL,
    seq INT NOT NULL,
    sub_id CHAR(36) NOT NULL,
    payment_id CHAR(36) NOT NULL,
    previous_sub_id CHAR(36),
    member_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    plan_id CHAR(36) NOT NULL,
    activity_type VARCHAR(12) NOT NULL,
    is_yearly BOOLEAN NOT NULL,
    price DECIMAL(14,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    start_at DATETIME(6) NOT NULL,
    end_at DATETIME(6) NOT NULL,
    status VARCHAR(16) NOT NULL,
    PRIMARY KEY (n, k)
  );

  INSERT INTO _seed_sub
  WITH RECURSIVE terms (k) AS (
    SELECT 0 UNION ALL SELECT k + 1 FROM terms WHERE k < 11
  ),
  plans AS (
    SELECT id, code, activity_type, price, currency,
           CAST(COALESCE(duration_months, GREATEST(1, ROUND(duration_days / 30))) AS SIGNED) AS months
    FROM membership_plans
  )
  SELECT
    m.n,
    terms.k,
    m.n * 12 + terms.k,
    CONCAT('d4000000-0000-0000-0000-', LPAD(m.n * 12 + terms.k, 12, '0')),
    CONCAT('d3000000-0000-0000-0000-', LPAD(m.n * 12 + terms.k, 12, '0')),
    IF(terms.k = 0, NULL,
       CONCAT('d4000000-0000-0000-0000-', LPAD(m.n * 12 + terms.k - 1, 12, '0'))),
    m.member_id,
    m.user_id,
    plans.id,
    plans.activity_type,
    plans.months >= 6,
    plans.price,
    plans.currency,
    DATE_ADD(m.joined_at + INTERVAL 10 MINUTE, INTERVAL terms.k * plans.months MONTH),
    DATE_ADD(m.joined_at + INTERVAL 10 MINUTE, INTERVAL (terms.k + 1) * plans.months MONTH),
    IF(DATE_ADD(m.joined_at + INTERVAL 10 MINUTE, INTERVAL (terms.k + 1) * plans.months MONTH)
         > v_now, 'ACTIVE', 'EXPIRED')
  FROM _seed_member m
  JOIN plans ON plans.code = m.plan_code
  JOIN terms ON terms.k = 0 OR (plans.months = 1 AND terms.k <= m.loyalty)
  WHERE DATE_ADD(m.joined_at + INTERVAL 10 MINUTE, INTERVAL terms.k * plans.months MONTH) < v_now;

  -- Mã chuyển khoản cùng dạng với backend (IRX + YYMMDD + 8 ký tự hex).
  INSERT INTO payments
    (id, payment_number, member_id, purpose, amount, currency, method, status,
     idempotency_key, paid_at, created_by, created_at)
  SELECT payment_id,
         CONCAT('IRX', DATE_FORMAT(start_at, '%y%m%d'), 'D', LPAD(HEX(seq), 7, '0')),
         member_id, 'MEMBERSHIP', price, currency,
         ELT(1 + seq % 5, 'QR', 'QR', 'QR', 'BANK_TRANSFER', 'CASH'),
         'PAID',
         CONCAT('seed-membership-', seq),
         start_at, user_id, start_at - INTERVAL 5 MINUTE
  FROM _seed_sub;

  -- Kỳ trước phải có trước kỳ sau vì renewed_from_id trỏ ngược lại.
  INSERT INTO membership_subscriptions
    (id, member_id, plan_id, payment_id, renewed_from_id, start_at, end_at, status,
     created_by, created_at)
  SELECT sub_id, member_id, plan_id, payment_id, previous_sub_id, start_at, end_at, status,
         user_id, start_at - INTERVAL 5 MINUTE
  FROM _seed_sub
  ORDER BY k, n;

  INSERT INTO subscription_status_history
    (id, subscription_id, from_status, to_status, reason, created_at)
  SELECT CONCAT('d5000000-0000-0000-0000-', LPAD(seq, 12, '0')),
         sub_id, 'PENDING', 'ACTIVE', 'Thanh toán được xác nhận ở backend', start_at
  FROM _seed_sub;

  INSERT INTO subscription_status_history
    (id, subscription_id, from_status, to_status, reason, created_at)
  SELECT CONCAT('d5100000-0000-0000-0000-', LPAD(seq, 12, '0')),
         sub_id, 'ACTIVE', 'EXPIRED', 'Gói tập hết hạn', end_at
  FROM _seed_sub
  WHERE status = 'EXPIRED';

  -- ==========================================================
  -- Lượt ra vào: 2–5 lượt mỗi kỳ gói tháng, 8–19 lượt mỗi gói năm, vào trong
  -- khung 06:00–20:00 giờ phòng tập. Mọi lượt đều đã check-out.
  -- ==========================================================
  INSERT INTO check_ins
    (id, member_id, subscription_id, branch_id, check_in_at, check_out_at,
     method, location, created_at)
  WITH RECURSIVE visits (v) AS (
    SELECT 0 UNION ALL SELECT v + 1 FROM visits WHERE v < 19
  )
  SELECT id, member_id, sub_id, v_branch_id, check_in_at,
         check_in_at + INTERVAL stay_minutes MINUTE,
         'MANUAL', 'Quầy lễ tân', check_in_at
  FROM (
    SELECT
      CONCAT('d6000000-0000-0000-0000-', LPAD(s.seq * 20 + visits.v, 12, '0')) AS id,
      s.member_id,
      s.sub_id,
      TIMESTAMP(DATE(s.start_at + INTERVAL
          IF(s.is_yearly, 2 + (visits.v * 17 + s.n) % 300, 2 + (visits.v * 7 + s.n) % 25) DAY))
        + INTERVAL (360 + (s.n * 53 + visits.v * 211 + s.k * 97) % 840 - v_offset) MINUTE
        AS check_in_at,
      45 + (s.n * 7 + visits.v * 13) % 76 AS stay_minutes
    FROM _seed_sub s
    JOIN visits ON visits.v < IF(s.is_yearly, 8 + s.n % 12, 2 + (s.n + s.k * 5) % 4)
  ) AS planned
  WHERE check_in_at + INTERVAL stay_minutes MINUTE < v_now - INTERVAL 1 HOUR;

  -- ==========================================================
  -- Ví lượt PT: hội viên gói năm mua một gói buổi PT sau khi đăng ký ít ngày
  -- và tập với PT có chuyên môn trùng loại hình của gói (ADR-018).
  -- ==========================================================
  CREATE TEMPORARY TABLE _seed_pt (
    n INT PRIMARY KEY,
    member_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    sub_id CHAR(36) NOT NULL,
    account_id CHAR(36) NOT NULL,
    purchase_id CHAR(36) NOT NULL,
    payment_id CHAR(36) NOT NULL,
    trainer_id CHAR(36) NOT NULL,
    trainer_user_id CHAR(36) NOT NULL,
    activity_type VARCHAR(12) NOT NULL,
    quantity INT NOT NULL,
    paid_at DATETIME(6) NOT NULL
  );

  INSERT INTO _seed_pt
  SELECT s.n, s.member_id, s.user_id, s.sub_id,
         CONCAT('d7000000-0000-0000-0000-', LPAD(s.n, 12, '0')),
         CONCAT('d8000000-0000-0000-0000-', LPAD(s.n, 12, '0')),
         CONCAT('d9000000-0000-0000-0000-', LPAD(s.n, 12, '0')),
         t.trainer_id,
         t.user_id,
         s.activity_type,
         ELT(1 + s.n % 4, 4, 8, 12, 6),
         s.start_at + INTERVAL (3 + s.n % 20) DAY
  FROM _seed_sub s
  JOIN _seed_trainer t
    ON t.t = IF(s.activity_type = 'GYM', 1 + s.n % 4, 5 + s.n % 2)
  WHERE s.k = 0
    AND s.is_yearly
    AND s.start_at + INTERVAL (3 + s.n % 20) DAY < v_now - INTERVAL 1 DAY;

  INSERT INTO payments
    (id, payment_number, member_id, purpose, amount, currency, method, status,
     idempotency_key, paid_at, created_by, created_at)
  SELECT payment_id,
         CONCAT('IRX', DATE_FORMAT(paid_at, '%y%m%d'), 'E', LPAD(HEX(n), 7, '0')),
         member_id, 'PT_CREDIT', quantity * v_pt_price, 'VND', 'QR', 'PAID',
         CONCAT('seed-ptcredit-', n),
         paid_at, user_id, paid_at - INTERVAL 5 MINUTE
  FROM _seed_pt;

  INSERT INTO pt_credit_accounts
    (id, member_id, purchased_sessions, reserved_sessions, used_sessions, created_at)
  SELECT account_id, member_id, quantity, 0, 0, paid_at - INTERVAL 5 MINUTE
  FROM _seed_pt;

  INSERT INTO pt_credit_purchases
    (id, credit_account_id, payment_id, quantity, unit_price, status, credited_at, created_at)
  SELECT purchase_id, account_id, payment_id, quantity, v_pt_price, 'CREDITED',
         paid_at, paid_at - INTERVAL 5 MINUTE
  FROM _seed_pt;

  INSERT INTO pt_credit_ledger
    (id, credit_account_id, purchase_id, transaction_type,
     purchased_delta, reserved_delta, used_delta,
     purchased_balance, reserved_balance, used_balance,
     idempotency_key, reason, created_by, created_at)
  SELECT CONCAT('da000000-0000-0000-0000-', LPAD(n, 12, '0')),
         account_id, purchase_id, 'PURCHASE',
         quantity, 0, 0,
         quantity, 0, 0,
         CONCAT('purchase-', purchase_id),
         CONCAT('Mua ', quantity, ' buổi PT'), user_id, paid_at
  FROM _seed_pt;

  -- ==========================================================
  -- Buổi PT đã diễn ra: cách nhau 4 ngày, không rơi vào Chủ nhật. Mỗi PT có 12 ô
  -- 60 phút từ 08:00 mỗi ngày; `slot` là thứ tự đặt trong ngày và được trải ra
  -- các giờ khác nhau (nhân 5 theo modulo 12 là một hoán vị nên không trùng ô).
  -- `r` là thứ tự buổi của hội viên, dùng để ghi số dư sổ cái: giữ lượt khi đặt
  -- (trước buổi tập 1 ngày), trừ lượt khi PT chốt buổi.
  -- ==========================================================
  CREATE TEMPORARY TABLE _seed_booking (
    n INT NOT NULL,
    j INT NOT NULL,
    r INT NOT NULL,
    booking_id CHAR(36) NOT NULL,
    start_at DATETIME(6) NOT NULL,
    end_at DATETIME(6) NOT NULL,
    status VARCHAR(16) NOT NULL,
    PRIMARY KEY (n, j)
  );

  INSERT INTO _seed_booking
  WITH RECURSIVE sessions (j) AS (
    SELECT 1 UNION ALL SELECT j + 1 FROM sessions WHERE j < 12
  ),
  wanted AS (
    SELECT p.n, sessions.j, p.trainer_id,
           DATE(p.paid_at + INTERVAL v_offset MINUTE + INTERVAL (sessions.j * 4 - 2) DAY) AS raw_day
    FROM _seed_pt p
    JOIN sessions ON sessions.j <= p.quantity - p.n % 3
  ),
  dated AS (
    SELECT n, j, trainer_id,
           raw_day + INTERVAL IF(DAYOFWEEK(raw_day) = 1, 1, 0) DAY AS local_day
    FROM wanted
  ),
  slotted AS (
    SELECT n, j, local_day,
           ROW_NUMBER() OVER (PARTITION BY trainer_id, local_day ORDER BY n) AS slot
    FROM dated
  ),
  timed AS (
    SELECT n, j,
           TIMESTAMP(local_day)
             + INTERVAL ((8 + (slot * 5 + DAYOFYEAR(local_day)) % 12) * 60 - v_offset) MINUTE
             AS start_at
    FROM slotted
    WHERE slot <= 12
  )
  SELECT n, j,
         ROW_NUMBER() OVER (PARTITION BY n ORDER BY j),
         CONCAT('db000000-0000-0000-0000-', LPAD(n * 16 + j, 12, '0')),
         start_at,
         start_at + INTERVAL 60 MINUTE,
         IF((n + j) % 9 = 0, 'NO_SHOW', 'COMPLETED')
  FROM timed
  WHERE start_at + INTERVAL 60 MINUTE < v_now - INTERVAL 1 HOUR;

  INSERT INTO pt_bookings
    (id, booking_number, member_id, trainer_id, subscription_id, credit_account_id,
     availability_id, activity_type, start_at, end_at, status,
     requested_at, responded_at, completed_at, created_at)
  SELECT b.booking_id,
         CONCAT('PTB-', DATE_FORMAT(b.start_at, '%Y%m%d'), '-D', LPAD(HEX(b.n * 16 + b.j), 5, '0')),
         p.member_id, p.trainer_id, p.sub_id, p.account_id,
         NULL, p.activity_type, b.start_at, b.end_at, b.status,
         b.start_at - INTERVAL 1 DAY,
         b.start_at - INTERVAL 1 DAY,
         IF(b.status = 'COMPLETED', b.end_at + INTERVAL 5 MINUTE, NULL),
         b.start_at - INTERVAL 1 DAY
  FROM _seed_booking b
  JOIN _seed_pt p ON p.n = b.n;

  INSERT INTO pt_credit_ledger
    (id, credit_account_id, booking_id, transaction_type,
     purchased_delta, reserved_delta, used_delta,
     purchased_balance, reserved_balance, used_balance,
     idempotency_key, reason, created_by, created_at)
  SELECT CONCAT('dc000000-0000-0000-0000-', LPAD(b.n * 16 + b.j, 12, '0')),
         p.account_id, b.booking_id, 'RESERVE',
         0, 1, 0,
         p.quantity, 1, b.r - 1,
         CONCAT('reserve-', b.booking_id),
         'Giữ 1 lượt cho buổi PT đã đặt', p.user_id, b.start_at - INTERVAL 1 DAY
  FROM _seed_booking b
  JOIN _seed_pt p ON p.n = b.n;

  INSERT INTO pt_credit_ledger
    (id, credit_account_id, booking_id, transaction_type,
     purchased_delta, reserved_delta, used_delta,
     purchased_balance, reserved_balance, used_balance,
     idempotency_key, reason, created_by, created_at)
  SELECT CONCAT('dd000000-0000-0000-0000-', LPAD(b.n * 16 + b.j, 12, '0')),
         p.account_id, b.booking_id, 'CONSUME',
         0, -1, 1,
         p.quantity, 0, b.r,
         CONCAT('consume-', b.booking_id),
         IF(b.status = 'COMPLETED', 'Hoàn thành buổi PT', 'Vắng mặt buổi PT'),
         p.trainer_user_id, b.end_at + INTERVAL 5 MINUTE
  FROM _seed_booking b
  JOIN _seed_pt p ON p.n = b.n;

  UPDATE pt_credit_accounts a
  JOIN _seed_pt p ON p.account_id = a.id
  JOIN (SELECT n, COUNT(*) AS sessions_used FROM _seed_booking GROUP BY n) AS used
    ON used.n = p.n
  SET a.used_sessions = used.sessions_used;

  COMMIT;

  DROP TEMPORARY TABLE IF EXISTS _seed_trainer;
  DROP TEMPORARY TABLE IF EXISTS _seed_member;
  DROP TEMPORARY TABLE IF EXISTS _seed_sub;
  DROP TEMPORARY TABLE IF EXISTS _seed_pt;
  DROP TEMPORARY TABLE IF EXISTS _seed_booking;
END$$

DELIMITER ;

CALL _gf_seed_demo();

DROP PROCEDURE IF EXISTS _gf_seed_demo;
