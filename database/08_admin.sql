-- GymFitness — khu quản trị (ADR-016)
--
--   * users.username: đăng nhập bằng tên đăng nhập hoặc email (tài khoản admin mặc định).
--   * Quản lý tài khoản, gói tập, lịch sử ra vào (check-in/out) và báo cáo doanh thu.
--   * Mọi thao tác ghi của admin được lưu vào audit_logs.
--
-- File này vừa tạo mới vừa nâng cấp database đang chạy, chạy lại nhiều lần an toàn.
-- Chạy sau 07_pt_schedule.sql:
--   python scripts/apply_sql.py database/08_admin.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ============================================================
-- Nâng cấp bảng users: tên đăng nhập
-- ============================================================

DROP PROCEDURE IF EXISTS _gf_migrate_username;

DELIMITER $$

CREATE PROCEDURE _gf_migrate_username()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'username'
  ) THEN
    ALTER TABLE users ADD COLUMN username VARCHAR(50) NULL AFTER email;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND INDEX_NAME = 'uq_users_username'
  ) THEN
    CREATE UNIQUE INDEX uq_users_username ON users (username);
  END IF;
END$$

DELIMITER ;

CALL _gf_migrate_username();
DROP PROCEDURE IF EXISTS _gf_migrate_username;

-- ============================================================
-- Procedure
-- ============================================================

DROP PROCEDURE IF EXISTS sp_admin_bootstrap;
DROP PROCEDURE IF EXISTS sp_admin_overview;
DROP PROCEDURE IF EXISTS sp_admin_user_list;
DROP PROCEDURE IF EXISTS sp_admin_user_create;
DROP PROCEDURE IF EXISTS sp_admin_user_update;
DROP PROCEDURE IF EXISTS sp_admin_user_set_password;
DROP PROCEDURE IF EXISTS sp_admin_user_delete;
DROP PROCEDURE IF EXISTS sp_admin_plan_list;
DROP PROCEDURE IF EXISTS sp_admin_plan_save;
DROP PROCEDURE IF EXISTS sp_admin_plan_delete;
DROP PROCEDURE IF EXISTS sp_admin_checkin_list;
DROP PROCEDURE IF EXISTS sp_admin_checkin_create;
DROP PROCEDURE IF EXISTS sp_admin_checkout;
DROP PROCEDURE IF EXISTS sp_admin_revenue;

DELIMITER $$

-- ============================================================
-- sp_admin_bootstrap
-- Tạo tài khoản ADMIN mặc định nếu tên đăng nhập/email chưa tồn tại.
-- Không bao giờ ghi đè mật khẩu của tài khoản đã có.
-- ============================================================
CREATE PROCEDURE sp_admin_bootstrap(
  IN p_user_id CHAR(36),
  IN p_username VARCHAR(50),
  IN p_email VARCHAR(254),
  IN p_password_hash TEXT,
  IN p_full_name VARCHAR(150)
)
BEGIN
  DECLARE v_exists INT DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code, 'Không tạo được admin mặc định.' AS error_message,
           0 AS created;
  END;

  START TRANSACTION;

  SELECT COUNT(*) INTO v_exists
  FROM users
  WHERE username = p_username OR email = p_email;

  IF v_exists = 0 THEN
    INSERT INTO users (id, email, username, password_hash, role, status)
    VALUES (p_user_id, p_email, p_username, p_password_hash, 'ADMIN', 'ACTIVE');

    INSERT INTO user_profiles (user_id, full_name) VALUES (p_user_id, p_full_name);

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, after_data)
    VALUES (UUID(), NULL, 'ADMIN_BOOTSTRAP', 'user', p_user_id,
            JSON_OBJECT('username', p_username, 'email', p_email));
  END IF;

  COMMIT;

  SELECT NULL AS error_code, NULL AS error_message, v_exists = 0 AS created;
END$$

-- ============================================================
-- sp_admin_overview
-- Số liệu nhanh cho đầu trang quản trị. p_day_start/p_month_start/
-- p_prev_month_start là UTC của 00:00 hôm nay / ngày 1 tháng này / ngày 1
-- tháng trước theo giờ phòng tập.
-- ============================================================
CREATE PROCEDURE sp_admin_overview(
  IN p_day_start DATETIME(6),
  IN p_month_start DATETIME(6),
  IN p_prev_month_start DATETIME(6)
)
BEGIN
  SELECT
    (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role = 'USER') AS members,
    (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role = 'USER'
        AND created_at >= p_month_start) AS new_members_this_month,
    (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role = 'USER'
        AND created_at >= p_prev_month_start AND created_at < p_month_start) AS new_members_last_month,
    (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role = 'PT') AS trainers,
    (SELECT COUNT(DISTINCT s.member_id) FROM membership_subscriptions s
      JOIN members m ON m.id = s.member_id
      JOIN users u ON u.id = m.user_id
      WHERE s.status = 'ACTIVE' AND s.deleted_at IS NULL
        AND s.end_at > UTC_TIMESTAMP(6)
        AND u.role = 'USER' AND u.deleted_at IS NULL) AS active_members,
    (SELECT COUNT(*) FROM check_ins
      WHERE deleted_at IS NULL AND check_in_at >= p_day_start) AS checkins_today,
    (SELECT COUNT(*) FROM check_ins
      WHERE deleted_at IS NULL AND check_out_at IS NULL) AS inside_now,
    (SELECT COALESCE(SUM(amount), 0) FROM payments
      WHERE status = 'PAID' AND paid_at >= p_month_start) AS revenue_this_month,
    (SELECT COALESCE(SUM(amount), 0) FROM payments
      WHERE status = 'PAID' AND paid_at >= p_prev_month_start
        AND paid_at < p_month_start) AS revenue_last_month,
    (SELECT COUNT(*) FROM payments WHERE status = 'PENDING') AS pending_payments,
    (SELECT COUNT(*) FROM products WHERE deleted_at IS NULL AND status = 'ACTIVE') AS products;
END$$

-- ============================================================
-- sp_admin_user_list
-- Tìm kiếm tài khoản theo tên/email/sđt/mã hội viên/tên đăng nhập
-- (hoặc lấy đúng một tài khoản theo p_user_id).
-- total_count là tổng số dòng khớp (trước LIMIT) để phân trang.
-- p_sort: full_name, email, created_at, last_login_at; tiền tố '-' = giảm dần.
-- Mặc định (NULL hoặc giá trị lạ): mới tạo trước.
-- ============================================================
CREATE PROCEDURE sp_admin_user_list(
  IN p_user_id CHAR(36),
  IN p_search VARCHAR(150),
  IN p_role VARCHAR(16),
  IN p_status VARCHAR(16),
  IN p_sort VARCHAR(24),
  IN p_limit INT,
  IN p_offset INT
)
BEGIN
  DECLARE v_pattern VARCHAR(160) DEFAULT NULL;

  IF NULLIF(TRIM(p_search), '') IS NOT NULL THEN
    SET v_pattern = CONCAT('%', TRIM(p_search), '%');
  END IF;

  -- Xếp hạng bằng ROW_NUMBER() trong bảng dẫn xuất rồi sắp theo một cột số:
  -- nhiều khoá ORDER BY CASE làm MySQL 8.0 sập khi procedure chạy lại với LIMIT khác.
  SELECT t.*
  FROM (
  SELECT
    u.id,
    u.email,
    u.username,
    u.phone,
    u.role,
    u.status,
    u.created_at,
    u.last_login_at,
    u.locked_until,
    p.full_name,
    m.member_code,
    t.employee_code,
    t.hourly_rate,
    t.bio,
    (SELECT GROUP_CONCAT(ts.specialty ORDER BY ts.specialty)
     FROM trainer_specialties ts WHERE ts.trainer_id = t.id) AS specialties,
    (SELECT COUNT(*) FROM trainer_weekly_schedule ws WHERE ws.trainer_id = t.id) AS schedule_slots,
    (SELECT pl.name
     FROM membership_subscriptions s
     JOIN membership_plans pl ON pl.id = s.plan_id
     WHERE s.member_id = m.id AND s.status = 'ACTIVE' AND s.deleted_at IS NULL
       AND s.end_at > UTC_TIMESTAMP(6)
     ORDER BY s.end_at DESC LIMIT 1) AS active_plan_name,
    (SELECT s.end_at
     FROM membership_subscriptions s
     WHERE s.member_id = m.id AND s.status = 'ACTIVE' AND s.deleted_at IS NULL
       AND s.end_at > UTC_TIMESTAMP(6)
     ORDER BY s.end_at DESC LIMIT 1) AS active_plan_end_at,
    COUNT(*) OVER () AS total_count,
    CASE p_sort
      WHEN 'full_name' THEN ROW_NUMBER() OVER (ORDER BY p.full_name, u.id)
      WHEN '-full_name' THEN ROW_NUMBER() OVER (ORDER BY p.full_name DESC, u.id)
      WHEN 'email' THEN ROW_NUMBER() OVER (ORDER BY u.email, u.id)
      WHEN '-email' THEN ROW_NUMBER() OVER (ORDER BY u.email DESC, u.id)
      WHEN 'created_at' THEN ROW_NUMBER() OVER (ORDER BY u.created_at, u.id)
      WHEN 'last_login_at' THEN ROW_NUMBER() OVER (ORDER BY u.last_login_at, u.id)
      WHEN '-last_login_at' THEN ROW_NUMBER() OVER (ORDER BY u.last_login_at DESC, u.id)
      ELSE ROW_NUMBER() OVER (ORDER BY u.created_at DESC, u.id)
    END AS sort_rank
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  LEFT JOIN members m ON m.user_id = u.id AND m.deleted_at IS NULL
  LEFT JOIN trainer_profiles t ON t.user_id = u.id AND t.deleted_at IS NULL
  WHERE u.deleted_at IS NULL
    AND (p_user_id IS NULL OR u.id = p_user_id)
    AND (p_role IS NULL OR u.role = p_role)
    AND (p_status IS NULL OR u.status = p_status)
    AND (v_pattern IS NULL
         OR u.email LIKE v_pattern
         OR u.username LIKE v_pattern
         OR u.phone LIKE v_pattern
         OR p.full_name LIKE v_pattern
         OR m.member_code LIKE v_pattern
         OR t.employee_code LIKE v_pattern)
  ) AS t
  ORDER BY t.sort_rank
  LIMIT p_limit OFFSET p_offset;
END$$

-- ============================================================
-- sp_admin_user_create
-- Admin tạo tài khoản USER (kèm hồ sơ hội viên), PT (kèm hồ sơ PT) hoặc ADMIN.
-- p_specialties: JSON mảng chuyên môn cho PT, ví dụ ["GYM","MUSCLE_GAIN"].
-- ============================================================
CREATE PROCEDURE sp_admin_user_create(
  IN p_user_id CHAR(36),
  IN p_profile_id CHAR(36),
  IN p_email VARCHAR(254),
  IN p_username VARCHAR(50),
  IN p_phone VARCHAR(30),
  IN p_password_hash TEXT,
  IN p_full_name VARCHAR(150),
  IN p_role VARCHAR(16),
  IN p_hourly_rate NUMERIC(14,2),
  IN p_bio TEXT,
  IN p_specialties JSON,
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_seq INT DEFAULT 0;
  DECLARE v_code VARCHAR(30) DEFAULT NULL;
  DECLARE v_branch_id CHAR(36) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SELECT 'DUPLICATE' AS error_code,
           'Email, số điện thoại hoặc tên đăng nhập đã được dùng.' AS error_message,
           NULL AS user_id;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể tạo tài khoản do lỗi hệ thống.' AS error_message,
           NULL AS user_id;
  END;

  START TRANSACTION;

  IF EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
    SET v_error_code = 'EMAIL_EXISTS';
    SET v_error_message = 'Email này đã được sử dụng.';
  ELSEIF p_phone IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE phone = p_phone) THEN
    SET v_error_code = 'PHONE_EXISTS';
    SET v_error_message = 'Số điện thoại này đã được sử dụng.';
  ELSEIF p_username IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE username = p_username) THEN
    SET v_error_code = 'USERNAME_EXISTS';
    SET v_error_message = 'Tên đăng nhập này đã được sử dụng.';
  ELSEIF p_role NOT IN ('USER', 'PT', 'MANAGER', 'ADMIN') THEN
    SET v_error_code = 'INVALID_ROLE';
    SET v_error_message = 'Vai trò không hợp lệ.';
  END IF;

  IF v_error_code IS NULL THEN
    INSERT INTO users (id, email, username, phone, password_hash, role, status)
    VALUES (p_user_id, p_email, p_username, p_phone, p_password_hash, p_role, 'ACTIVE');

    INSERT INTO user_profiles (user_id, full_name) VALUES (p_user_id, p_full_name);

    SELECT id INTO v_branch_id
    FROM branches
    WHERE is_active = TRUE AND deleted_at IS NULL
    ORDER BY code
    LIMIT 1;

    IF p_role = 'USER' THEN
      SELECT COALESCE(MAX(CAST(SUBSTRING(member_code, 4) AS UNSIGNED)), 0) + 1
      INTO v_seq
      FROM members
      WHERE member_code LIKE 'MEM%';
      SET v_code = CONCAT('MEM', LPAD(v_seq, 6, '0'));

      INSERT INTO members
        (id, member_code, user_id, home_branch_id, full_name, email, phone, status)
      VALUES
        (p_profile_id, v_code, p_user_id, v_branch_id, p_full_name, p_email, p_phone, 'ACTIVE');
    ELSEIF p_role = 'PT' THEN
      SELECT COALESCE(MAX(CAST(SUBSTRING(employee_code, 3) AS UNSIGNED)), 0) + 1
      INTO v_seq
      FROM trainer_profiles
      WHERE employee_code LIKE 'PT%';
      SET v_code = CONCAT('PT', LPAD(v_seq, 6, '0'));

      INSERT INTO trainer_profiles
        (id, user_id, employee_code, branch_id, bio, hourly_rate, status)
      VALUES
        (p_profile_id, p_user_id, v_code, v_branch_id, NULLIF(TRIM(p_bio), ''),
         COALESCE(p_hourly_rate, 200000), 'ACTIVE');

      INSERT INTO trainer_specialties (trainer_id, specialty)
      SELECT DISTINCT p_profile_id, j.specialty
      FROM JSON_TABLE(COALESCE(p_specialties, JSON_ARRAY()), '$[*]'
             COLUMNS (specialty VARCHAR(24) PATH '$')) AS j;
    END IF;

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, after_data)
    VALUES (UUID(), p_actor_id, 'USER_CREATE', 'user', p_user_id,
            JSON_OBJECT('email', p_email, 'username', p_username, 'role', p_role,
                        'full_name', p_full_name, 'code', v_code));
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_user_id ELSE NULL END AS user_id;
END$$

-- ============================================================
-- sp_admin_user_update
-- Tham số NULL = giữ nguyên. p_phone = '' để xoá số điện thoại.
-- Vai trò không đổi được (hồ sơ hội viên/PT gắn với vai trò).
-- Khoá/ngưng tài khoản: huỷ các buổi PT chưa bắt đầu và hoàn lượt (ADR-026),
-- trả cancelled_sessions. Cần 12_lifecycle.sql (sp_pt_cancel_upcoming_for_user).
-- ============================================================
CREATE PROCEDURE sp_admin_user_update(
  IN p_user_id CHAR(36),
  IN p_email VARCHAR(254),
  IN p_username VARCHAR(50),
  IN p_phone VARCHAR(30),
  IN p_full_name VARCHAR(150),
  IN p_status VARCHAR(16),
  IN p_hourly_rate NUMERIC(14,2),
  IN p_bio TEXT,
  IN p_specialties JSON,
  IN p_actor_id CHAR(36),
  IN p_utc_offset_minutes INT
)
BEGIN
  DECLARE v_role VARCHAR(16) DEFAULT NULL;
  DECLARE v_old_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_cancelled INT DEFAULT 0;
  DECLARE v_before JSON DEFAULT NULL;
  DECLARE v_trainer_id CHAR(36) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SELECT 'DUPLICATE' AS error_code,
           'Email, số điện thoại hoặc tên đăng nhập đã được dùng.' AS error_message,
           NULL AS user_id,
           0 AS cancelled_sessions;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể cập nhật tài khoản do lỗi hệ thống.' AS error_message,
           NULL AS user_id,
           0 AS cancelled_sessions;
  END;

  START TRANSACTION;

  SELECT u.role, u.status,
         JSON_OBJECT('email', u.email, 'username', u.username, 'phone', u.phone,
                     'status', u.status, 'full_name', p.full_name)
  INTO v_role, v_old_status, v_before
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  WHERE u.id = p_user_id AND u.deleted_at IS NULL
  FOR UPDATE;

  IF v_role IS NULL THEN
    SET v_error_code = 'USER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy tài khoản.';
  ELSEIF p_email IS NOT NULL AND EXISTS (
    SELECT 1 FROM users WHERE email = p_email AND id <> p_user_id
  ) THEN
    SET v_error_code = 'EMAIL_EXISTS';
    SET v_error_message = 'Email này đã được sử dụng.';
  ELSEIF NULLIF(p_phone, '') IS NOT NULL AND EXISTS (
    SELECT 1 FROM users WHERE phone = p_phone AND id <> p_user_id
  ) THEN
    SET v_error_code = 'PHONE_EXISTS';
    SET v_error_message = 'Số điện thoại này đã được sử dụng.';
  ELSEIF NULLIF(p_username, '') IS NOT NULL AND EXISTS (
    SELECT 1 FROM users WHERE username = p_username AND id <> p_user_id
  ) THEN
    SET v_error_code = 'USERNAME_EXISTS';
    SET v_error_message = 'Tên đăng nhập này đã được sử dụng.';
  END IF;

  IF v_error_code IS NULL THEN
    UPDATE users
    SET email = COALESCE(p_email, email),
        username = CASE WHEN p_username IS NULL THEN username ELSE NULLIF(p_username, '') END,
        phone = CASE WHEN p_phone IS NULL THEN phone ELSE NULLIF(p_phone, '') END,
        status = COALESCE(p_status, status),
        row_version = row_version + 1
    WHERE id = p_user_id;

    IF p_full_name IS NOT NULL THEN
      UPDATE user_profiles SET full_name = p_full_name WHERE user_id = p_user_id;
    END IF;

    -- Khoá hoặc ngưng: buổi PT sắp tới không thể diễn ra, huỷ và hoàn lượt ngay.
    IF p_status IN ('SUSPENDED', 'INACTIVE') AND v_old_status = 'ACTIVE' THEN
      CALL sp_pt_cancel_upcoming_for_user(
        p_user_id, p_actor_id,
        IF(v_role = 'PT', 'Huấn luyện viên tạm ngưng nhận buổi', 'Tài khoản hội viên bị tạm khoá'),
        COALESCE(p_utc_offset_minutes, 420), v_cancelled);
    END IF;

    -- Giữ hồ sơ hội viên đồng bộ với tài khoản.
    UPDATE members m
    JOIN users u ON u.id = m.user_id
    SET m.full_name = COALESCE(p_full_name, m.full_name),
        m.email = u.email,
        m.phone = u.phone
    WHERE m.user_id = p_user_id AND m.deleted_at IS NULL;

    IF v_role = 'PT' THEN
      SELECT id INTO v_trainer_id
      FROM trainer_profiles
      WHERE user_id = p_user_id AND deleted_at IS NULL
      LIMIT 1;

      UPDATE trainer_profiles
      SET hourly_rate = COALESCE(p_hourly_rate, hourly_rate),
          bio = CASE WHEN p_bio IS NULL THEN bio ELSE NULLIF(TRIM(p_bio), '') END,
          row_version = row_version + 1
      WHERE id = v_trainer_id;

      IF p_specialties IS NOT NULL THEN
        DELETE FROM trainer_specialties WHERE trainer_id = v_trainer_id;
        INSERT INTO trainer_specialties (trainer_id, specialty)
        SELECT DISTINCT v_trainer_id, j.specialty
        FROM JSON_TABLE(p_specialties, '$[*]' COLUMNS (specialty VARCHAR(24) PATH '$')) AS j;
      END IF;
    END IF;

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
    SELECT UUID(), p_actor_id, 'USER_UPDATE', 'user', p_user_id, v_before,
           JSON_OBJECT('email', u.email, 'username', u.username, 'phone', u.phone,
                       'status', u.status, 'full_name', p.full_name)
    FROM users u
    LEFT JOIN user_profiles p ON p.user_id = u.id
    WHERE u.id = p_user_id;

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_user_id ELSE NULL END AS user_id,
         v_cancelled AS cancelled_sessions;
END$$

-- ============================================================
-- sp_admin_user_set_password
-- Đặt lại mật khẩu và mở khoá đăng nhập.
-- ============================================================
CREATE PROCEDURE sp_admin_user_set_password(
  IN p_user_id CHAR(36),
  IN p_password_hash TEXT,
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_updated INT DEFAULT 0;

  UPDATE users
  SET password_hash = p_password_hash,
      failed_login_count = 0,
      locked_until = NULL,
      row_version = row_version + 1
  WHERE id = p_user_id AND deleted_at IS NULL;

  SET v_updated = ROW_COUNT();

  IF v_updated > 0 THEN
    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id)
    VALUES (UUID(), p_actor_id, 'USER_RESET_PASSWORD', 'user', p_user_id);
  END IF;

  COMMIT;

  SELECT CASE WHEN v_updated = 0 THEN 'USER_NOT_FOUND' ELSE NULL END AS error_code,
         CASE WHEN v_updated = 0 THEN 'Không tìm thấy tài khoản.' ELSE NULL END AS error_message;
END$$

-- ============================================================
-- sp_admin_user_delete
-- Xoá mềm: ngưng hoạt động, ẩn khỏi hệ thống và giải phóng email/sđt/tên đăng
-- nhập để có thể đăng ký lại. Lịch sử thanh toán, gói tập, buổi PT vẫn giữ.
-- Không xoá được khi còn buổi PT sắp tới hoặc khi là admin cuối cùng.
-- ============================================================
CREATE PROCEDURE sp_admin_user_delete(
  IN p_user_id CHAR(36),
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_role VARCHAR(16) DEFAULT NULL;
  DECLARE v_before JSON DEFAULT NULL;
  DECLARE v_upcoming INT DEFAULT 0;
  DECLARE v_other_admins INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể xoá tài khoản do lỗi hệ thống.' AS error_message,
           NULL AS user_id;
  END;

  START TRANSACTION;

  SELECT u.role,
         JSON_OBJECT('email', u.email, 'username', u.username, 'phone', u.phone,
                     'role', u.role, 'full_name', p.full_name)
  INTO v_role, v_before
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  WHERE u.id = p_user_id AND u.deleted_at IS NULL
  FOR UPDATE;

  SELECT COUNT(*) INTO v_upcoming
  FROM pt_bookings b
  LEFT JOIN members m ON m.id = b.member_id
  LEFT JOIN trainer_profiles t ON t.id = b.trainer_id
  WHERE (m.user_id = p_user_id OR t.user_id = p_user_id)
    AND b.status IN ('REQUESTED', 'ACCEPTED')
    AND b.deleted_at IS NULL
    AND b.end_at > UTC_TIMESTAMP(6);

  SELECT COUNT(*) INTO v_other_admins
  FROM users
  WHERE role = 'ADMIN' AND status = 'ACTIVE' AND deleted_at IS NULL AND id <> p_user_id;

  IF v_role IS NULL THEN
    SET v_error_code = 'USER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy tài khoản.';
  ELSEIF p_user_id = p_actor_id THEN
    SET v_error_code = 'CANNOT_DELETE_SELF';
    SET v_error_message = 'Không thể tự xoá tài khoản đang đăng nhập.';
  ELSEIF v_role = 'ADMIN' AND v_other_admins = 0 THEN
    SET v_error_code = 'LAST_ADMIN';
    SET v_error_message = 'Phải còn ít nhất một tài khoản quản trị.';
  ELSEIF v_upcoming > 0 THEN
    SET v_error_code = 'HAS_UPCOMING_SESSIONS';
    SET v_error_message = CONCAT('Tài khoản còn ', v_upcoming,
                                 ' buổi PT chưa kết thúc. Hãy tạm khoá tài khoản trước: ',
                                 'các buổi chưa bắt đầu sẽ được huỷ và hoàn lượt.');
  END IF;

  IF v_error_code IS NULL THEN
    UPDATE users
    SET email = CONCAT('deleted+', LEFT(id, 8), '+', UNIX_TIMESTAMP(), '@deleted.local'),
        username = NULL,
        phone = NULL,
        status = 'INACTIVE',
        deleted_at = UTC_TIMESTAMP(6),
        row_version = row_version + 1
    WHERE id = p_user_id;

    UPDATE members
    SET status = 'INACTIVE', email = NULL, phone = NULL, deleted_at = UTC_TIMESTAMP(6)
    WHERE user_id = p_user_id AND deleted_at IS NULL;

    UPDATE trainer_profiles
    SET status = 'INACTIVE', deleted_at = UTC_TIMESTAMP(6)
    WHERE user_id = p_user_id AND deleted_at IS NULL;

    DELETE ws FROM trainer_weekly_schedule ws
    JOIN trainer_profiles t ON t.id = ws.trainer_id
    WHERE t.user_id = p_user_id;

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, before_data)
    VALUES (UUID(), p_actor_id, 'USER_DELETE', 'user', p_user_id, v_before);

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_user_id ELSE NULL END AS user_id;
END$$

-- ============================================================
-- sp_admin_plan_list
-- Mọi gói chưa xoá (kể cả đang ẩn) kèm số người đang dùng.
-- ============================================================
CREATE PROCEDURE sp_admin_plan_list()
BEGIN
  SELECT
    pl.id,
    pl.code,
    pl.name,
    pl.activity_type,
    pl.description,
    pl.duration_months,
    pl.duration_days,
    pl.price,
    pl.currency,
    pl.is_active,
    pl.created_at,
    pl.row_version,
    (SELECT COUNT(*) FROM membership_subscriptions s
      WHERE s.plan_id = pl.id AND s.status = 'ACTIVE' AND s.deleted_at IS NULL
        AND s.end_at > UTC_TIMESTAMP(6)) AS active_subscriptions,
    (SELECT COUNT(*) FROM membership_subscriptions s
      JOIN payments pym ON pym.id = s.payment_id
      WHERE s.plan_id = pl.id AND pym.status = 'PAID') AS total_sold
  FROM membership_plans pl
  WHERE pl.deleted_at IS NULL
  ORDER BY pl.activity_type, pl.is_active DESC, pl.price;
END$$

-- ============================================================
-- sp_admin_plan_save
-- Tạo mới (p_is_new = TRUE) hoặc cập nhật gói tập. Đúng một trong
-- duration_months / duration_days được đặt (CHECK của bảng).
-- Đổi giá không ảnh hưởng gói đã bán: subscription giữ payment cũ.
-- p_expected_version: row_version client đang xem; khác bản hiện tại nghĩa là
-- người khác vừa sửa → VERSION_CONFLICT, không ghi đè. NULL = bỏ qua kiểm tra.
-- ============================================================
CREATE PROCEDURE sp_admin_plan_save(
  IN p_plan_id CHAR(36),
  IN p_is_new BOOLEAN,
  IN p_code VARCHAR(40),
  IN p_name VARCHAR(150),
  IN p_activity_type VARCHAR(12),
  IN p_description TEXT,
  IN p_duration_months SMALLINT,
  IN p_duration_days SMALLINT,
  IN p_price NUMERIC(14,2),
  IN p_is_active BOOLEAN,
  IN p_expected_version INT,
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_before JSON DEFAULT NULL;
  DECLARE v_version INT DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SELECT 'PLAN_CODE_EXISTS' AS error_code, 'Mã gói này đã tồn tại.' AS error_message,
           NULL AS plan_id;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INVALID_PLAN' AS error_code, 'Thông tin gói tập không hợp lệ.' AS error_message,
           NULL AS plan_id;
  END;

  START TRANSACTION;

  IF p_is_new THEN
    INSERT INTO membership_plans
      (id, code, name, activity_type, description, duration_months, duration_days,
       price, currency, is_active)
    VALUES
      (p_plan_id, p_code, p_name, p_activity_type, NULLIF(TRIM(p_description), ''),
       p_duration_months, p_duration_days, p_price, 'VND', p_is_active);
  ELSE
    SELECT JSON_OBJECT('code', code, 'name', name, 'price', price, 'is_active', is_active,
                       'duration_months', duration_months, 'duration_days', duration_days,
                       'row_version', row_version),
           row_version
    INTO v_before, v_version
    FROM membership_plans
    WHERE id = p_plan_id AND deleted_at IS NULL
    FOR UPDATE;

    IF v_before IS NULL THEN
      SET v_error_code = 'PLAN_NOT_FOUND';
      SET v_error_message = 'Không tìm thấy gói tập.';
    ELSEIF p_expected_version IS NOT NULL AND p_expected_version <> v_version THEN
      SET v_error_code = 'VERSION_CONFLICT';
      SET v_error_message = 'Gói tập vừa được người khác sửa. Tải lại để xem bản mới nhất.';
    ELSE
      UPDATE membership_plans
      SET code = p_code,
          name = p_name,
          activity_type = p_activity_type,
          description = NULLIF(TRIM(p_description), ''),
          duration_months = p_duration_months,
          duration_days = p_duration_days,
          price = p_price,
          is_active = p_is_active,
          row_version = row_version + 1
      WHERE id = p_plan_id;
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
    VALUES (UUID(), p_actor_id, IF(p_is_new, 'PLAN_CREATE', 'PLAN_UPDATE'), 'membership_plan',
            p_plan_id, v_before,
            JSON_OBJECT('code', p_code, 'name', p_name, 'price', p_price, 'is_active', p_is_active,
                        'duration_months', p_duration_months, 'duration_days', p_duration_days));
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_plan_id ELSE NULL END AS plan_id;
END$$

-- ============================================================
-- sp_admin_plan_delete
-- Xoá mềm: ngừng bán và ẩn khỏi danh sách; gói đã bán vẫn giữ tham chiếu.
-- ============================================================
CREATE PROCEDURE sp_admin_plan_delete(
  IN p_plan_id CHAR(36),
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_updated INT DEFAULT 0;

  UPDATE membership_plans
  SET is_active = FALSE, deleted_at = UTC_TIMESTAMP(6), row_version = row_version + 1
  WHERE id = p_plan_id AND deleted_at IS NULL;

  SET v_updated = ROW_COUNT();

  IF v_updated > 0 THEN
    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id)
    VALUES (UUID(), p_actor_id, 'PLAN_DELETE', 'membership_plan', p_plan_id);
  END IF;

  COMMIT;

  SELECT CASE WHEN v_updated = 0 THEN 'PLAN_NOT_FOUND' ELSE NULL END AS error_code,
         CASE WHEN v_updated = 0 THEN 'Không tìm thấy gói tập.' ELSE NULL END AS error_message;
END$$

-- ============================================================
-- sp_admin_checkin_list
-- Lịch sử ra vào trong khoảng [p_from, p_to), tìm theo tên/mã/email/sđt.
-- p_sort: check_in_at, member_name; tiền tố '-' = giảm dần. Mặc định: mới vào trước.
-- ============================================================
CREATE PROCEDURE sp_admin_checkin_list(
  IN p_from DATETIME(6),
  IN p_to DATETIME(6),
  IN p_search VARCHAR(150),
  IN p_inside_only BOOLEAN,
  IN p_sort VARCHAR(24),
  IN p_limit INT,
  IN p_offset INT
)
BEGIN
  DECLARE v_pattern VARCHAR(160) DEFAULT NULL;

  IF NULLIF(TRIM(p_search), '') IS NOT NULL THEN
    SET v_pattern = CONCAT('%', TRIM(p_search), '%');
  END IF;

  -- Xếp hạng bằng ROW_NUMBER() trong bảng dẫn xuất rồi sắp theo một cột số:
  -- nhiều khoá ORDER BY CASE làm MySQL 8.0 sập khi procedure chạy lại với LIMIT khác.
  SELECT t.*
  FROM (
  SELECT
    c.id,
    c.check_in_at,
    c.check_out_at,
    c.method,
    m.id AS member_id,
    m.member_code,
    m.full_name AS member_name,
    u.email AS member_email,
    u.phone AS member_phone,
    pl.name AS plan_name,
    cp.full_name AS created_by_name,
    COUNT(*) OVER () AS total_count,
    CASE p_sort
      WHEN 'member_name' THEN ROW_NUMBER() OVER (ORDER BY m.full_name, c.check_in_at DESC, c.id)
      WHEN '-member_name' THEN ROW_NUMBER() OVER (ORDER BY m.full_name DESC, c.check_in_at DESC, c.id)
      WHEN 'check_in_at' THEN ROW_NUMBER() OVER (ORDER BY c.check_in_at, c.id)
      ELSE ROW_NUMBER() OVER (ORDER BY c.check_in_at DESC, c.id)
    END AS sort_rank
  FROM check_ins c
  JOIN members m ON m.id = c.member_id
  LEFT JOIN users u ON u.id = m.user_id
  LEFT JOIN membership_subscriptions s ON s.id = c.subscription_id
  LEFT JOIN membership_plans pl ON pl.id = s.plan_id
  LEFT JOIN user_profiles cp ON cp.user_id = c.created_by
  WHERE c.deleted_at IS NULL
    AND (p_inside_only IS NOT TRUE OR c.check_out_at IS NULL)
    AND (p_inside_only IS TRUE OR (c.check_in_at >= p_from AND c.check_in_at < p_to))
    AND (v_pattern IS NULL
         OR m.full_name LIKE v_pattern
         OR m.member_code LIKE v_pattern
         OR u.email LIKE v_pattern
         OR u.phone LIKE v_pattern)
  ) AS t
  ORDER BY t.sort_rank
  LIMIT p_limit OFFSET p_offset;
END$$

-- ============================================================
-- sp_admin_checkin_create
-- Check-in thủ công tại quầy. p_identifier: mã hội viên, email hoặc sđt.
-- Cần gói còn hiệu lực; mỗi hội viên chỉ có một lượt đang ở trong phòng tập.
-- ============================================================
CREATE PROCEDURE sp_admin_checkin_create(
  IN p_checkin_id CHAR(36),
  IN p_identifier VARCHAR(254),
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_member_id CHAR(36) DEFAULT NULL;
  DECLARE v_member_name VARCHAR(150) DEFAULT NULL;
  DECLARE v_branch_id CHAR(36) DEFAULT NULL;
  DECLARE v_subscription_id CHAR(36) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    ROLLBACK;
    SELECT 'ALREADY_INSIDE' AS error_code,
           'Hội viên đang ở trong phòng tập (chưa check-out).' AS error_message,
           NULL AS checkin_id, NULL AS member_name;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code, 'Không thể check-in do lỗi hệ thống.' AS error_message,
           NULL AS checkin_id, NULL AS member_name;
  END;

  START TRANSACTION;

  SELECT m.id, m.full_name, m.home_branch_id
  INTO v_member_id, v_member_name, v_branch_id
  FROM members m
  LEFT JOIN users u ON u.id = m.user_id
  WHERE m.deleted_at IS NULL
    AND (m.member_code = p_identifier OR u.email = p_identifier OR u.phone = p_identifier)
  LIMIT 1;

  IF v_member_id IS NULL THEN
    SET v_error_code = 'MEMBER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy hội viên với mã/email/số điện thoại này.';
  ELSE
    SELECT s.id INTO v_subscription_id
    FROM membership_subscriptions s
    WHERE s.member_id = v_member_id
      AND s.status = 'ACTIVE'
      AND s.deleted_at IS NULL
      AND s.start_at <= UTC_TIMESTAMP(6)
      AND s.end_at > UTC_TIMESTAMP(6)
    ORDER BY s.end_at DESC
    LIMIT 1;

    IF v_subscription_id IS NULL THEN
      SET v_error_code = 'NO_ACTIVE_SUBSCRIPTION';
      SET v_error_message = 'Hội viên không có gói tập còn hiệu lực.';
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    INSERT INTO check_ins
      (id, member_id, subscription_id, branch_id, check_in_at, method, created_by)
    VALUES
      (p_checkin_id, v_member_id, v_subscription_id, v_branch_id, UTC_TIMESTAMP(6),
       'MANUAL', p_actor_id);
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_checkin_id ELSE NULL END AS checkin_id,
         v_member_name AS member_name;
END$$

-- ============================================================
-- sp_admin_checkout
-- ============================================================
CREATE PROCEDURE sp_admin_checkout(
  IN p_checkin_id CHAR(36),
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_updated INT DEFAULT 0;

  UPDATE check_ins
  SET check_out_at = GREATEST(UTC_TIMESTAMP(6), DATE_ADD(check_in_at, INTERVAL 1 SECOND)),
      row_version = row_version + 1
  WHERE id = p_checkin_id AND check_out_at IS NULL AND deleted_at IS NULL;

  SET v_updated = ROW_COUNT();
  COMMIT;

  SELECT CASE WHEN v_updated = 0 THEN 'CHECKIN_NOT_OPEN' ELSE NULL END AS error_code,
         CASE WHEN v_updated = 0 THEN 'Lượt vào này đã check-out hoặc không tồn tại.'
              ELSE NULL END AS error_message;
END$$

-- ============================================================
-- sp_admin_revenue
-- Doanh thu từ payment PAID trong [p_from, p_to), gom theo kỳ của giờ phòng
-- tập (p_offset_minutes so với UTC). period_start là ngày bắt đầu kỳ (YYYY-MM-DD):
--   WEEK: thứ 2 đầu tuần (ISO) · MONTH: ngày 1 · QUARTER: ngày đầu quý · YEAR: 1/1.
-- Payment gói kèm PT (ADR-014) được tách phần PT theo pt_credit_purchases.
-- ============================================================
CREATE PROCEDURE sp_admin_revenue(
  IN p_from DATETIME(6),
  IN p_to DATETIME(6),
  IN p_period VARCHAR(8),
  IN p_offset_minutes INT
)
BEGIN
  SELECT
    CASE p_period
      WHEN 'WEEK' THEN DATE_FORMAT(DATE_SUB(DATE(l.local_paid), INTERVAL WEEKDAY(l.local_paid) DAY), '%Y-%m-%d')
      WHEN 'MONTH' THEN DATE_FORMAT(l.local_paid, '%Y-%m-01')
      WHEN 'QUARTER' THEN CONCAT(YEAR(l.local_paid), '-',
                                 LPAD((QUARTER(l.local_paid) - 1) * 3 + 1, 2, '0'), '-01')
      ELSE CONCAT(YEAR(l.local_paid), '-01-01')
    END AS period_start,
    SUM(l.amount) AS total,
    SUM(l.pt_amount) AS pt_total,
    SUM(CASE WHEN l.purpose = 'MEMBERSHIP' THEN l.amount - l.pt_amount ELSE 0 END) AS membership_total,
    SUM(CASE WHEN l.purpose = 'PRODUCT_ORDER' THEN l.amount ELSE 0 END) AS other_total,
    COUNT(*) AS payment_count
  FROM (
    SELECT
      DATE_ADD(pym.paid_at, INTERVAL p_offset_minutes MINUTE) AS local_paid,
      pym.amount,
      pym.purpose,
      CASE
        WHEN pym.purpose = 'PT_CREDIT' THEN pym.amount
        WHEN pym.purpose = 'MEMBERSHIP' THEN COALESCE(
          (SELECT pc.quantity * pc.unit_price FROM pt_credit_purchases pc
           WHERE pc.payment_id = pym.id LIMIT 1), 0)
        ELSE 0
      END AS pt_amount
    FROM payments pym
    WHERE pym.status = 'PAID'
      AND pym.paid_at >= p_from
      AND pym.paid_at < p_to
  ) AS l
  GROUP BY period_start
  ORDER BY period_start;
END$$

DELIMITER ;
