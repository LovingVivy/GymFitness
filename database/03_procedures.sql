-- GymFitness stored procedures — authentication, profile, plans và subscription
-- Toàn bộ truy vấn nằm ở đây.
-- Backend Python chỉ gọi CALL <procedure>(...), không viết SELECT/INSERT/UPDATE trực tiếp.
--
-- Chạy file này sau 01_tables.sql và 02_triggers.sql:
--   mysql -u root -p < database/03_procedures.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS sp_auth_register;
DROP PROCEDURE IF EXISTS sp_auth_find_user_by_email;
DROP PROCEDURE IF EXISTS sp_auth_find_user_by_id;
DROP PROCEDURE IF EXISTS sp_auth_mark_login_success;
DROP PROCEDURE IF EXISTS sp_auth_mark_login_failed;
DROP PROCEDURE IF EXISTS sp_profile_get;
DROP PROCEDURE IF EXISTS sp_profile_update;
DROP PROCEDURE IF EXISTS sp_plan_list_active;
DROP PROCEDURE IF EXISTS sp_plan_find_by_id;
DROP PROCEDURE IF EXISTS sp_subscription_create;
DROP PROCEDURE IF EXISTS sp_subscription_mark_paid;
DROP PROCEDURE IF EXISTS sp_file_save_avatar;
DROP PROCEDURE IF EXISTS sp_file_get;

DELIMITER $$

-- ============================================================
-- sp_auth_register
-- Kiểm tra trùng email/phone và tạo users + user_profiles + members
-- trong một transaction. Trả về result set duy nhất:
--   error_code = NULL                -> đăng ký thành công
--   error_code = 'EMAIL_EXISTS'      -> email đã tồn tại
--   error_code = 'PHONE_EXISTS'      -> số điện thoại đã tồn tại
--   error_code = 'INTERNAL_ERROR'    -> lỗi hệ thống
-- ============================================================
CREATE PROCEDURE sp_auth_register(
  IN p_user_id CHAR(36),
  IN p_member_id CHAR(36),
  IN p_email VARCHAR(254),
  IN p_phone VARCHAR(30),
  IN p_password_hash TEXT,
  IN p_full_name VARCHAR(150)
)
BEGIN
  DECLARE v_email_exists INT DEFAULT 0;
  DECLARE v_phone_exists INT DEFAULT 0;
  DECLARE v_duplicate INT DEFAULT 0;
  DECLARE v_member_seq INT DEFAULT 0;
  DECLARE v_member_code VARCHAR(30) DEFAULT NULL;
  DECLARE v_branch_id CHAR(36) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  -- Lớp bảo vệ cuối cùng: UNIQUE index chặn ghi trùng khi có request đồng thời.
  DECLARE CONTINUE HANDLER FOR 1062 SET v_duplicate = 1;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể tạo tài khoản do lỗi hệ thống.' AS error_message,
           NULL AS user_id;
  END;

  START TRANSACTION;

  SELECT COUNT(*) INTO v_email_exists
  FROM users
  WHERE email = p_email AND deleted_at IS NULL;

  IF v_email_exists > 0 THEN
    SET v_error_code = 'EMAIL_EXISTS';
    SET v_error_message = 'Email này đã được sử dụng.';
  END IF;

  IF v_error_code IS NULL AND p_phone IS NOT NULL THEN
    SELECT COUNT(*) INTO v_phone_exists
    FROM users
    WHERE phone = p_phone AND deleted_at IS NULL;

    IF v_phone_exists > 0 THEN
      SET v_error_code = 'PHONE_EXISTS';
      SET v_error_message = 'Số điện thoại này đã được sử dụng.';
    END IF;
  END IF;

  IF v_error_code IS NOT NULL THEN
    ROLLBACK;
  ELSE
    INSERT INTO users (id, email, phone, password_hash, role, status)
    VALUES (p_user_id, p_email, p_phone, p_password_hash, 'USER', 'ACTIVE');

    IF v_duplicate = 1 THEN
      -- UNIQUE index báo trùng: xác định lại chính xác trường nào bị trùng.
      ROLLBACK;

      SELECT COUNT(*) INTO v_email_exists
      FROM users
      WHERE email = p_email AND deleted_at IS NULL;

      IF v_email_exists > 0 THEN
        SET v_error_code = 'EMAIL_EXISTS';
        SET v_error_message = 'Email này đã được sử dụng.';
      ELSE
        SET v_error_code = 'PHONE_EXISTS';
        SET v_error_message = 'Số điện thoại này đã được sử dụng.';
      END IF;
    ELSE
      INSERT INTO user_profiles (user_id, full_name)
      VALUES (p_user_id, p_full_name);

      -- Mỗi tài khoản USER có một hồ sơ hội viên để gắn gói tập và check-in.
      SELECT COALESCE(MAX(CAST(SUBSTRING(member_code, 4) AS UNSIGNED)), 0) + 1
      INTO v_member_seq
      FROM members
      WHERE member_code LIKE 'MEM%';

      SET v_member_code = CONCAT('MEM', LPAD(v_member_seq, 6, '0'));

      SELECT id INTO v_branch_id
      FROM branches
      WHERE is_active = TRUE AND deleted_at IS NULL
      ORDER BY code
      LIMIT 1;

      INSERT INTO members
        (id, member_code, user_id, home_branch_id, full_name, email, phone, status)
      VALUES
        (p_member_id, v_member_code, p_user_id, v_branch_id, p_full_name, p_email, p_phone, 'ACTIVE');

      IF v_duplicate = 1 THEN
        -- member_code trùng (rất hiếm): huỷ toàn bộ để không tạo tài khoản thiếu hồ sơ.
        ROLLBACK;
        SET v_error_code = 'INTERNAL_ERROR';
        SET v_error_message = 'Không thể tạo hồ sơ hội viên, vui lòng thử lại.';
      ELSE
        COMMIT;
      END IF;
    END IF;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_user_id ELSE NULL END AS user_id;
END$$

-- ============================================================
-- sp_auth_find_user_by_email
-- Lấy tài khoản kèm hồ sơ theo email hoặc tên đăng nhập để kiểm tra mật khẩu.
-- Trả về 0 dòng nếu không tìm thấy.
-- ============================================================
CREATE PROCEDURE sp_auth_find_user_by_email(IN p_email VARCHAR(254))
BEGIN
  SELECT
    u.id,
    u.email,
    u.phone,
    u.password_hash,
    u.role,
    u.status,
    u.failed_login_count,
    u.locked_until,
    p.full_name,
    p.height_cm,
    p.weight_kg,
    p.experience_level,
    p.fitness_goal,
    p.weekly_training_sessions
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  -- Đăng nhập bằng email hoặc tên đăng nhập (cột username thêm ở 08_admin.sql).
  WHERE (u.email = p_email OR u.username = p_email) AND u.deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_auth_find_user_by_id
-- Lấy tài khoản kèm hồ sơ theo id (dùng cho /auth/me và response sau đăng ký).
-- ============================================================
CREATE PROCEDURE sp_auth_find_user_by_id(IN p_user_id CHAR(36))
BEGIN
  SELECT
    u.id,
    u.email,
    u.phone,
    u.password_hash,
    u.role,
    u.status,
    u.failed_login_count,
    u.locked_until,
    p.full_name,
    p.height_cm,
    p.weight_kg,
    p.experience_level,
    p.fitness_goal,
    p.weekly_training_sessions
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  WHERE u.id = p_user_id AND u.deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_auth_mark_login_success
-- Ghi nhận thời điểm đăng nhập và xoá bộ đếm đăng nhập sai.
-- ============================================================
CREATE PROCEDURE sp_auth_mark_login_success(IN p_user_id CHAR(36))
BEGIN
  UPDATE users
  SET last_login_at = UTC_TIMESTAMP(6),
      failed_login_count = 0,
      locked_until = NULL
  WHERE id = p_user_id AND deleted_at IS NULL;

  COMMIT;
END$$

-- ============================================================
-- sp_auth_mark_login_failed
-- Tăng bộ đếm đăng nhập sai và tạm khoá tài khoản khi vượt ngưỡng.
-- ============================================================
CREATE PROCEDURE sp_auth_mark_login_failed(
  IN p_user_id CHAR(36),
  IN p_max_attempts INT,
  IN p_lock_minutes INT
)
BEGIN
  UPDATE users
  SET failed_login_count = failed_login_count + 1,
      locked_until = CASE
        WHEN failed_login_count + 1 >= p_max_attempts
          THEN DATE_ADD(UTC_TIMESTAMP(6), INTERVAL p_lock_minutes MINUTE)
        ELSE locked_until
      END
  WHERE id = p_user_id AND deleted_at IS NULL;

  COMMIT;
END$$

-- ============================================================
-- sp_profile_get
-- Hồ sơ đầy đủ của hội viên: tài khoản, thông tin cá nhân, ảnh đại diện,
-- hồ sơ hội viên và gói đang đăng ký kèm số ngày còn lại.
-- Trả về 0 dòng nếu không tìm thấy.
-- ============================================================
CREATE PROCEDURE sp_profile_get(IN p_user_id CHAR(36))
BEGIN
  SELECT
    u.id,
    u.email,
    u.phone,
    u.role,
    u.status,
    u.created_at AS user_created_at,
    u.last_login_at,
    p.full_name,
    p.date_of_birth,
    p.gender,
    p.height_cm,
    p.weight_kg,
    p.experience_level,
    p.fitness_goal,
    p.weekly_training_sessions,
    p.emergency_contact_name,
    p.emergency_contact_phone,
    f.id AS avatar_file_id,
    f.content_type AS avatar_content_type,
    m.id AS member_id,
    m.member_code,
    m.joined_at AS member_joined_at,
    m.status AS member_status,
    b.name AS home_branch_name,
    s.id AS subscription_id,
    -- Gói quá hạn mà tác vụ định kỳ chưa kịp chuyển trạng thái vẫn hiện là EXPIRED.
    CASE WHEN s.status = 'ACTIVE' AND s.end_at <= UTC_TIMESTAMP(6) THEN 'EXPIRED'
         ELSE s.status END AS subscription_status,
    s.start_at AS subscription_start_at,
    s.end_at AS subscription_end_at,
    s.remaining_visits,
    pl.id AS plan_id,
    pl.code AS plan_code,
    pl.name AS plan_name,
    pl.activity_type AS plan_activity_type,
    pl.duration_months AS plan_duration_months,
    pl.duration_days AS plan_duration_days,
    pl.price AS plan_price,
    pl.currency AS plan_currency,
    DATEDIFF(s.end_at, UTC_TIMESTAMP()) AS days_remaining,
    DATEDIFF(s.end_at, s.start_at) AS total_days,
    -- Đầu chuỗi gói nối tiếp cùng loại hình (gia hạn sớm), để tính tổng thời hạn.
    (SELECT MIN(s3.start_at)
     FROM membership_subscriptions s3
     JOIN membership_plans pl3 ON pl3.id = s3.plan_id
     WHERE s3.member_id = m.id AND pl3.activity_type = pl.activity_type
       AND s3.status IN ('ACTIVE', 'FROZEN') AND s3.deleted_at IS NULL
       AND s3.end_at > UTC_TIMESTAMP(6)) AS coverage_start_at,
    COALESCE(pca.purchased_sessions, 0) AS pt_purchased,
    COALESCE(pca.reserved_sessions, 0) AS pt_reserved,
    COALESCE(pca.used_sessions, 0) AS pt_used,
    COALESCE(pca.purchased_sessions, 0)
      - COALESCE(pca.reserved_sessions, 0)
      - COALESCE(pca.used_sessions, 0) AS pt_remaining
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  LEFT JOIN file_assets f ON f.id = p.avatar_file_id AND f.deleted_at IS NULL
  LEFT JOIN members m ON m.user_id = u.id AND m.deleted_at IS NULL
  LEFT JOIN branches b ON b.id = m.home_branch_id
  LEFT JOIN pt_credit_accounts pca ON pca.member_id = m.id
  LEFT JOIN membership_subscriptions s ON s.id = (
    -- Ưu tiên gói còn hiệu lực; không còn gói nào thì lấy gói hết hạn gần nhất
    -- để giao diện hiện "Hết hạn" kèm nút gia hạn.
    SELECT s2.id
    FROM membership_subscriptions s2
    WHERE s2.member_id = m.id
      AND s2.status IN ('ACTIVE', 'FROZEN', 'EXPIRED')
      AND s2.deleted_at IS NULL
    ORDER BY (s2.status IN ('ACTIVE', 'FROZEN') AND s2.end_at > UTC_TIMESTAMP(6)) DESC,
             s2.end_at DESC
    LIMIT 1
  )
  LEFT JOIN membership_plans pl ON pl.id = s.plan_id
  WHERE u.id = p_user_id AND u.deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_profile_update
-- Cập nhật thông tin cá nhân, thể chất và mục tiêu tập luyện.
-- Chỉ ghi đè trường được truyền vào (NULL = giữ nguyên).
-- ============================================================
CREATE PROCEDURE sp_profile_update(
  IN p_user_id CHAR(36),
  IN p_full_name VARCHAR(150),
  IN p_phone VARCHAR(30),
  IN p_date_of_birth DATE,
  IN p_gender VARCHAR(16),
  IN p_height_cm NUMERIC(5,2),
  IN p_weight_kg NUMERIC(5,2),
  IN p_experience_level VARCHAR(20),
  IN p_fitness_goal VARCHAR(24),
  IN p_weekly_training_sessions SMALLINT,
  IN p_emergency_contact_name VARCHAR(150),
  IN p_emergency_contact_phone VARCHAR(30)
)
BEGIN
  DECLARE v_user_exists INT DEFAULT 0;
  DECLARE v_phone_taken INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;
  DECLARE v_next_phone VARCHAR(30) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể cập nhật hồ sơ do lỗi hệ thống.' AS error_message;
  END;

  START TRANSACTION;

  SELECT COUNT(*) INTO v_user_exists
  FROM users
  WHERE id = p_user_id AND deleted_at IS NULL;

  IF v_user_exists = 0 THEN
    SET v_error_code = 'USER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy tài khoản.';
  END IF;

  IF v_error_code IS NULL AND p_phone IS NOT NULL THEN
    SELECT COUNT(*) INTO v_phone_taken
    FROM users
    WHERE phone = p_phone AND id <> p_user_id AND deleted_at IS NULL;

    IF v_phone_taken > 0 THEN
      SET v_error_code = 'PHONE_EXISTS';
      SET v_error_message = 'Số điện thoại này đã được sử dụng.';
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    UPDATE user_profiles
    SET full_name = COALESCE(p_full_name, full_name),
        date_of_birth = COALESCE(p_date_of_birth, date_of_birth),
        gender = COALESCE(p_gender, gender),
        height_cm = COALESCE(p_height_cm, height_cm),
        weight_kg = COALESCE(p_weight_kg, weight_kg),
        experience_level = COALESCE(p_experience_level, experience_level),
        fitness_goal = COALESCE(p_fitness_goal, fitness_goal),
        weekly_training_sessions = COALESCE(p_weekly_training_sessions, weekly_training_sessions),
        emergency_contact_name = COALESCE(p_emergency_contact_name, emergency_contact_name),
        emergency_contact_phone = COALESCE(p_emergency_contact_phone, emergency_contact_phone),
        row_version = row_version + 1
    WHERE user_id = p_user_id;

    IF p_phone IS NOT NULL THEN
      UPDATE users SET phone = p_phone WHERE id = p_user_id;
    END IF;

    UPDATE members
    SET full_name = COALESCE(p_full_name, full_name),
        phone = COALESCE(p_phone, phone)
    WHERE user_id = p_user_id;

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code, v_error_message AS error_message;
END$$

-- ============================================================
-- sp_plan_list_active
-- Danh sách gói tập đang mở bán.
-- ============================================================
CREATE PROCEDURE sp_plan_list_active()
BEGIN
  SELECT
    id,
    code,
    name,
    activity_type,
    description,
    duration_months,
    duration_days,
    price,
    currency,
    max_visits,
    freeze_days_allowed
  FROM membership_plans
  WHERE is_active = TRUE AND deleted_at IS NULL
  ORDER BY activity_type, duration_months;
END$$

-- ============================================================
-- sp_plan_find_by_id
-- ============================================================
CREATE PROCEDURE sp_plan_find_by_id(IN p_plan_id CHAR(36))
BEGIN
  SELECT
    id,
    code,
    name,
    activity_type,
    description,
    duration_months,
    duration_days,
    price,
    currency,
    max_visits,
    freeze_days_allowed
  FROM membership_plans
  WHERE id = p_plan_id AND is_active = TRUE AND deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_subscription_create
-- Tạo đơn thanh toán PENDING và subscription PENDING cho một gói tập.
-- Nếu p_pt_quantity > 0, cùng payment đó kèm một giao dịch mua lượt PT
-- (ADR-014): hội viên chỉ quét QR một lần cho cả gói lẫn PT.
-- Chưa kích hoạt quyền lợi: phải gọi sp_subscription_mark_paid sau khi
-- backend xác minh thanh toán (ADR-004).
-- ============================================================
CREATE PROCEDURE sp_subscription_create(
  IN p_subscription_id CHAR(36),
  IN p_payment_id CHAR(36),
  IN p_payment_number VARCHAR(40),
  IN p_idempotency_key VARCHAR(100),
  IN p_member_id CHAR(36),
  IN p_plan_id CHAR(36),
  IN p_created_by CHAR(36),
  IN p_pt_purchase_id CHAR(36),
  IN p_pt_quantity INT,
  IN p_pt_unit_price NUMERIC(14,2)
)
BEGIN
  DECLARE v_member_exists INT DEFAULT 0;
  DECLARE v_plan_count INT DEFAULT 0;
  DECLARE v_price NUMERIC(14,2) DEFAULT NULL;
  DECLARE v_currency CHAR(3) DEFAULT 'VND';
  DECLARE v_pt_quantity INT DEFAULT 0;
  DECLARE v_pt_total NUMERIC(14,2) DEFAULT 0;
  DECLARE v_account_id CHAR(36) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể tạo đăng ký gói do lỗi hệ thống.' AS error_message,
           NULL AS subscription_id,
           NULL AS payment_id,
           NULL AS amount;
  END;

  SET v_pt_quantity = COALESCE(p_pt_quantity, 0);

  START TRANSACTION;

  SELECT COUNT(*) INTO v_member_exists
  FROM members
  WHERE id = p_member_id AND deleted_at IS NULL;

  IF v_member_exists = 0 THEN
    SET v_error_code = 'MEMBER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy hồ sơ hội viên.';
  ELSEIF v_pt_quantity < 0 OR v_pt_quantity > 100 THEN
    SET v_error_code = 'INVALID_QUANTITY';
    SET v_error_message = 'Số buổi PT phải từ 0 đến 100.';
  END IF;

  IF v_error_code IS NULL THEN
    SELECT COUNT(*), MAX(price), MAX(currency)
    INTO v_plan_count, v_price, v_currency
    FROM membership_plans
    WHERE id = p_plan_id AND is_active = TRUE AND deleted_at IS NULL;

    IF v_plan_count = 0 THEN
      SET v_error_code = 'PLAN_NOT_FOUND';
      SET v_error_message = 'Gói tập không tồn tại hoặc đã ngừng bán.';
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    SET v_pt_total = v_pt_quantity * COALESCE(p_pt_unit_price, 0);

    INSERT INTO payments
      (id, payment_number, member_id, purpose, amount, currency, method, status,
       idempotency_key, qr_payload, qr_expires_at, created_by)
    VALUES
      (p_payment_id, p_payment_number, p_member_id, 'MEMBERSHIP', v_price + v_pt_total,
       v_currency, 'QR', 'PENDING', p_idempotency_key, CONCAT('IRONIX|', p_payment_number),
       DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 30 MINUTE), p_created_by);

    INSERT INTO membership_subscriptions
      (id, member_id, plan_id, payment_id, status, created_by)
    VALUES
      (p_subscription_id, p_member_id, p_plan_id, p_payment_id, 'PENDING', p_created_by);

    IF v_pt_quantity > 0 THEN
      INSERT INTO pt_credit_accounts (id, member_id)
      SELECT UUID(), p_member_id
      WHERE NOT EXISTS (SELECT 1 FROM pt_credit_accounts WHERE member_id = p_member_id);

      SELECT id INTO v_account_id
      FROM pt_credit_accounts
      WHERE member_id = p_member_id
      LIMIT 1;

      INSERT INTO pt_credit_purchases
        (id, credit_account_id, payment_id, quantity, unit_price, status)
      VALUES
        (p_pt_purchase_id, v_account_id, p_payment_id, v_pt_quantity, p_pt_unit_price, 'PENDING');
    END IF;

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_subscription_id ELSE NULL END AS subscription_id,
         CASE WHEN v_error_code IS NULL THEN p_payment_id ELSE NULL END AS payment_id,
         CASE WHEN v_error_code IS NULL THEN v_price + v_pt_total ELSE NULL END AS amount;
END$$

-- ============================================================
-- sp_subscription_mark_paid
-- Backend xác nhận thanh toán: payment -> PAID, subscription -> ACTIVE,
-- tính start_at/end_at theo thời hạn thật của gói (ADR-003) và ghi
-- (gia hạn khi gói cùng loại hình còn hạn: gói mới bắt đầu từ ngày hết hạn đó, ADR-026)
-- lịch sử trạng thái. Nếu payment kèm mua lượt PT (ADR-014) thì cộng
-- lượt và ghi sổ cái trong cùng transaction.
-- ============================================================
CREATE PROCEDURE sp_subscription_mark_paid(
  IN p_payment_id CHAR(36),
  IN p_changed_by CHAR(36)
)
BEGIN
  DECLARE v_payment_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_subscription_id CHAR(36) DEFAULT NULL;
  DECLARE v_duration_months SMALLINT DEFAULT NULL;
  DECLARE v_duration_days SMALLINT DEFAULT NULL;
  DECLARE v_now DATETIME(6) DEFAULT NULL;
  DECLARE v_start_at DATETIME(6) DEFAULT NULL;
  DECLARE v_member_id CHAR(36) DEFAULT NULL;
  DECLARE v_activity_type VARCHAR(12) DEFAULT NULL;
  DECLARE v_end_at DATETIME(6) DEFAULT NULL;
  DECLARE v_purchase_id CHAR(36) DEFAULT NULL;
  DECLARE v_account_id CHAR(36) DEFAULT NULL;
  DECLARE v_quantity INT DEFAULT 0;
  DECLARE v_purchased INT DEFAULT 0;
  DECLARE v_reserved INT DEFAULT 0;
  DECLARE v_used INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể xác nhận thanh toán do lỗi hệ thống.' AS error_message,
           NULL AS subscription_id,
           NULL AS end_at,
           0 AS pt_credited;
  END;

  START TRANSACTION;

  SELECT pym.status, s.id, pl.duration_months, pl.duration_days, s.member_id, pl.activity_type
  INTO v_payment_status, v_subscription_id, v_duration_months, v_duration_days,
       v_member_id, v_activity_type
  FROM payments pym
  JOIN membership_subscriptions s ON s.payment_id = pym.id
  JOIN membership_plans pl ON pl.id = s.plan_id
  WHERE pym.id = p_payment_id AND s.deleted_at IS NULL
  LIMIT 1
  FOR UPDATE;

  IF v_payment_status IS NULL THEN
    SET v_error_code = 'PAYMENT_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy giao dịch thanh toán.';
  ELSEIF v_payment_status <> 'PENDING' THEN
    SET v_error_code = 'PAYMENT_NOT_PENDING';
    SET v_error_message = 'Giao dịch đã được xử lý trước đó.';
  ELSE
    SET v_now = UTC_TIMESTAMP(6);

    -- Gia hạn sớm: nối tiếp sau gói cùng loại hình còn hạn để không mất ngày còn lại.
    SELECT GREATEST(v_now, COALESCE(MAX(s.end_at), v_now)) INTO v_start_at
    FROM membership_subscriptions s
    JOIN membership_plans pl ON pl.id = s.plan_id
    WHERE s.member_id = v_member_id
      AND pl.activity_type = v_activity_type
      AND s.id <> v_subscription_id
      AND s.status IN ('ACTIVE', 'FROZEN')
      AND s.deleted_at IS NULL
      AND s.end_at > v_now;

    -- ADR-003: gói tháng/năm tính theo lịch tháng, không quy đổi ra số ngày.
    IF v_duration_months IS NOT NULL THEN
      SET v_end_at = DATE_ADD(v_start_at, INTERVAL v_duration_months MONTH);
    ELSE
      SET v_end_at = DATE_ADD(v_start_at, INTERVAL v_duration_days DAY);
    END IF;

    UPDATE payments
    SET status = 'PAID',
        paid_at = v_now,
        row_version = row_version + 1
    WHERE id = p_payment_id;

    UPDATE membership_subscriptions
    SET status = 'ACTIVE',
        start_at = v_start_at,
        end_at = v_end_at,
        remaining_visits = NULL,
        row_version = row_version + 1
    WHERE id = v_subscription_id;

    INSERT INTO subscription_status_history
      (id, subscription_id, from_status, to_status, reason, changed_by)
    VALUES
      (UUID(), v_subscription_id, 'PENDING', 'ACTIVE',
       'Thanh toán được xác nhận ở backend', p_changed_by);

    -- Lượt PT mua kèm trong cùng payment (ADR-014).
    SELECT MAX(pc.id), MAX(pc.credit_account_id), COALESCE(MAX(pc.quantity), 0)
    INTO v_purchase_id, v_account_id, v_quantity
    FROM pt_credit_purchases pc
    WHERE pc.payment_id = p_payment_id AND pc.status = 'PENDING';

    IF v_purchase_id IS NOT NULL THEN
      SELECT purchased_sessions, reserved_sessions, used_sessions
      INTO v_purchased, v_reserved, v_used
      FROM pt_credit_accounts
      WHERE id = v_account_id
      FOR UPDATE;

      UPDATE pt_credit_accounts
      SET purchased_sessions = purchased_sessions + v_quantity,
          row_version = row_version + 1
      WHERE id = v_account_id;

      UPDATE pt_credit_purchases
      SET status = 'CREDITED', credited_at = v_now
      WHERE id = v_purchase_id;

      INSERT INTO pt_credit_ledger
        (id, credit_account_id, purchase_id, transaction_type,
         purchased_delta, reserved_delta, used_delta,
         purchased_balance, reserved_balance, used_balance,
         idempotency_key, reason, created_by)
      VALUES
        (UUID(), v_account_id, v_purchase_id, 'PURCHASE',
         v_quantity, 0, 0,
         v_purchased + v_quantity, v_reserved, v_used,
         CONCAT('purchase-', v_purchase_id),
         CONCAT('Mua ', v_quantity, ' buổi PT kèm gói hội viên'), p_changed_by);
    END IF;

    COMMIT;
  END IF;

  IF v_error_code IS NOT NULL THEN
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN v_subscription_id ELSE NULL END AS subscription_id,
         v_end_at AS end_at,
         CASE WHEN v_error_code IS NULL THEN v_quantity ELSE 0 END AS pt_credited;
END$$

-- ============================================================
-- sp_file_save_avatar
-- Lưu metadata ảnh đại diện vào file_assets và gắn vào user_profiles.
-- Nội dung file do backend ghi ra đĩa, database chỉ giữ metadata.
-- Ảnh cũ (nếu có) được soft-delete trong cùng transaction và trả về
-- old_storage_key để backend xoá file trên đĩa, tránh file mồ côi.
-- ============================================================
CREATE PROCEDURE sp_file_save_avatar(
  IN p_file_id CHAR(36),
  IN p_user_id CHAR(36),
  IN p_storage_key VARCHAR(512),
  IN p_original_name TEXT,
  IN p_content_type VARCHAR(120),
  IN p_size_bytes BIGINT,
  IN p_checksum_sha256 CHAR(64)
)
BEGIN
  DECLARE v_user_exists INT DEFAULT 0;
  DECLARE v_old_file_id CHAR(36) DEFAULT NULL;
  DECLARE v_old_storage_key VARCHAR(512) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể lưu ảnh đại diện do lỗi hệ thống.' AS error_message,
           NULL AS file_id,
           NULL AS old_storage_key;
  END;

  START TRANSACTION;

  -- Khoá dòng hồ sơ để hai lần tải ảnh đồng thời không cùng giữ một ảnh cũ.
  SELECT COUNT(*), MAX(p.avatar_file_id)
  INTO v_user_exists, v_old_file_id
  FROM users u
  JOIN user_profiles p ON p.user_id = u.id
  WHERE u.id = p_user_id AND u.deleted_at IS NULL
  FOR UPDATE;

  IF v_user_exists = 0 THEN
    SET v_error_code = 'USER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy hồ sơ người dùng.';
  ELSE
    INSERT INTO file_assets
      (id, owner_user_id, storage_key, original_name, content_type, size_bytes,
       visibility, checksum_sha256)
    VALUES
      (p_file_id, p_user_id, p_storage_key, p_original_name, p_content_type,
       p_size_bytes, 'PRIVATE', p_checksum_sha256);

    UPDATE user_profiles
    SET avatar_file_id = p_file_id,
        row_version = row_version + 1
    WHERE user_id = p_user_id;

    IF v_old_file_id IS NOT NULL THEN
      SELECT MAX(storage_key) INTO v_old_storage_key
      FROM file_assets
      WHERE id = v_old_file_id AND deleted_at IS NULL;

      UPDATE file_assets
      SET deleted_at = UTC_TIMESTAMP(6)
      WHERE id = v_old_file_id AND deleted_at IS NULL;
    END IF;

    COMMIT;
  END IF;

  IF v_error_code IS NOT NULL THEN
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_file_id ELSE NULL END AS file_id,
         CASE WHEN v_error_code IS NULL THEN v_old_storage_key ELSE NULL END AS old_storage_key;
END$$

-- ============================================================
-- sp_file_get
-- Metadata file để backend đọc nội dung từ đĩa và trả cho client.
-- ============================================================
CREATE PROCEDURE sp_file_get(IN p_file_id CHAR(36))
BEGIN
  SELECT id, owner_user_id, storage_key, original_name, content_type, size_bytes, visibility
  FROM file_assets
  WHERE id = p_file_id AND deleted_at IS NULL
  LIMIT 1;
END$$

DELIMITER ;
