-- GymFitness — lịch làm việc cố định của PT và đặt buổi xác nhận ngay (ADR-015)
--
-- Thay mô hình cũ "PT mở từng khung giờ rảnh/bận + duyệt từng yêu cầu" bằng:
--   * trainer_weekly_schedule : giờ làm việc lặp lại mỗi tuần (giờ địa phương)
--   * trainer_time_off        : nghỉ đột xuất (UTC)
--   * Hội viên chọn ô 60 phút còn trống → booking ACCEPTED ngay, giữ 1 lượt.
--   * Kết thúc: PT đánh dấu COMPLETED / NO_SHOW (tiêu lượt), hoặc một bên huỷ
--     (PT huỷ hoặc hội viên huỷ sớm → hoàn lượt; hội viên huỷ sát giờ → mất lượt).
--
-- File này vừa tạo mới vừa nâng cấp database đang chạy, chạy lại nhiều lần an toàn.
-- Chạy sau 06_procedures_payment.sql:
--   python scripts/apply_sql.py database/07_pt_schedule.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ============================================================
-- Bảng mới
-- ============================================================

CREATE TABLE IF NOT EXISTS trainer_weekly_schedule (
  id CHAR(36) PRIMARY KEY,
  trainer_id CHAR(36) NOT NULL,
  -- ISO 8601: 1 = Thứ 2 ... 7 = Chủ nhật. Giờ là giờ địa phương của phòng tập.
  weekday TINYINT NOT NULL CHECK (weekday BETWEEN 1 AND 7),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CHECK (end_time > start_time),
  INDEX idx_trainer_weekly_schedule_day (trainer_id, weekday, start_time),
  CONSTRAINT fk_trainer_weekly_schedule_trainer_id FOREIGN KEY (trainer_id)
    REFERENCES trainer_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS trainer_time_off (
  id CHAR(36) PRIMARY KEY,
  trainer_id CHAR(36) NOT NULL,
  start_at DATETIME(6) NOT NULL,
  end_at DATETIME(6) NOT NULL,
  reason VARCHAR(255),
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  deleted_at DATETIME(6),
  CHECK (end_at > start_at),
  INDEX idx_trainer_time_off_range (trainer_id, start_at, end_at),
  CONSTRAINT fk_trainer_time_off_trainer_id FOREIGN KEY (trainer_id)
    REFERENCES trainer_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- Nâng cấp pt_bookings
-- ============================================================

DROP PROCEDURE IF EXISTS _gf_add_column;

DELIMITER $$

CREATE PROCEDURE _gf_add_column(
  IN p_table VARCHAR(64),
  IN p_column VARCHAR(64),
  IN p_definition TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table AND COLUMN_NAME = p_column
  ) THEN
    SET @gf_ddl = CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN `', p_column, '` ', p_definition);
    PREPARE gf_stmt FROM @gf_ddl;
    EXECUTE gf_stmt;
    DEALLOCATE PREPARE gf_stmt;
  END IF;
END$$

DELIMITER ;

CALL _gf_add_column('pt_bookings', 'cancelled_at', 'DATETIME(6) NULL AFTER cancellation_reason');
CALL _gf_add_column('pt_bookings', 'cancelled_by', 'CHAR(36) NULL AFTER cancelled_at');
CALL _gf_add_column('pt_bookings', 'cancelled_by_role', 'VARCHAR(12) NULL AFTER cancelled_by');

DROP PROCEDURE IF EXISTS _gf_add_column;

-- Booking mới không gắn với trainer_availability nữa.
ALTER TABLE pt_bookings MODIFY availability_id CHAR(36) NULL;

-- ============================================================
-- Trigger: chỉ kiểm tra trainer_availability với booking kiểu cũ
-- ============================================================

DROP TRIGGER IF EXISTS trg_pt_bookings_validate_insert;
DROP TRIGGER IF EXISTS trg_pt_bookings_validate_update;

DELIMITER $$

CREATE TRIGGER trg_pt_bookings_validate_insert
BEFORE INSERT ON pt_bookings
FOR EACH ROW
BEGIN
  IF NEW.status IN ('REQUESTED', 'ACCEPTED') THEN
    IF NEW.availability_id IS NOT NULL AND NOT EXISTS (
      SELECT 1
      FROM trainer_availability AS a
      WHERE a.id = NEW.availability_id
        AND a.trainer_id = NEW.trainer_id
        AND a.status = 'AVAILABLE'
        AND a.deleted_at IS NULL
        AND a.start_at <= NEW.start_at
        AND a.end_at >= NEW.end_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'PT booking is outside trainer availability';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.trainer_id = NEW.trainer_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainer already has an overlapping PT booking';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.member_id = NEW.member_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Member already has an overlapping PT booking';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_pt_bookings_validate_update
BEFORE UPDATE ON pt_bookings
FOR EACH ROW
BEGIN
  IF NEW.status IN ('REQUESTED', 'ACCEPTED') AND NEW.deleted_at IS NULL THEN
    IF NEW.availability_id IS NOT NULL AND NOT EXISTS (
      SELECT 1
      FROM trainer_availability AS a
      WHERE a.id = NEW.availability_id
        AND a.trainer_id = NEW.trainer_id
        AND a.status = 'AVAILABLE'
        AND a.deleted_at IS NULL
        AND a.start_at <= NEW.start_at
        AND a.end_at >= NEW.end_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'PT booking is outside trainer availability';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.id <> NEW.id
        AND b.trainer_id = NEW.trainer_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainer already has an overlapping PT booking';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.id <> NEW.id
        AND b.member_id = NEW.member_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Member already has an overlapping PT booking';
    END IF;
  END IF;
END$$

DELIMITER ;

-- ============================================================
-- Procedure
-- ============================================================

-- Mô hình khung giờ rảnh/bận + duyệt yêu cầu đã bị thay thế.
DROP PROCEDURE IF EXISTS sp_trainer_availability_list;
DROP PROCEDURE IF EXISTS sp_trainer_availability_create;
DROP PROCEDURE IF EXISTS sp_trainer_availability_set_status;
DROP PROCEDURE IF EXISTS sp_trainer_availability_delete;
DROP PROCEDURE IF EXISTS sp_pt_booking_create;
DROP PROCEDURE IF EXISTS sp_pt_booking_accept;
DROP PROCEDURE IF EXISTS sp_pt_booking_reject;

DROP PROCEDURE IF EXISTS sp_trainer_list;
DROP PROCEDURE IF EXISTS sp_trainer_schedule_get;
DROP PROCEDURE IF EXISTS sp_trainer_schedule_replace;
DROP PROCEDURE IF EXISTS sp_trainer_time_off_list;
DROP PROCEDURE IF EXISTS sp_trainer_time_off_create;
DROP PROCEDURE IF EXISTS sp_trainer_time_off_delete;
DROP PROCEDURE IF EXISTS sp_trainer_busy_list;
DROP PROCEDURE IF EXISTS sp_pt_session_book;
DROP PROCEDURE IF EXISTS sp_pt_session_cancel;
DROP PROCEDURE IF EXISTS sp_pt_session_finish;
DROP PROCEDURE IF EXISTS sp_pt_booking_list_for_trainer;
DROP PROCEDURE IF EXISTS sp_pt_booking_list_for_member;

DELIMITER $$

-- ============================================================
-- sp_trainer_list
-- PT đang hoạt động và ĐÃ khai lịch làm việc: PT chưa có lịch không hiện
-- cho hội viên, tránh chọn phải người không có giờ nào để đặt.
-- ============================================================
CREATE PROCEDURE sp_trainer_list(IN p_activity_type VARCHAR(24))
BEGIN
  SELECT
    t.id,
    t.user_id,
    t.employee_code,
    t.hourly_rate,
    t.bio,
    t.certifications,
    t.status,
    p.full_name,
    b.name AS branch_name,
    (SELECT GROUP_CONCAT(ts.specialty ORDER BY ts.specialty)
     FROM trainer_specialties ts WHERE ts.trainer_id = t.id) AS specialties,
    (SELECT GROUP_CONCAT(DISTINCT ws.weekday ORDER BY ws.weekday)
     FROM trainer_weekly_schedule ws WHERE ws.trainer_id = t.id) AS schedule_weekdays
  FROM trainer_profiles t
  JOIN users u ON u.id = t.user_id AND u.deleted_at IS NULL AND u.status = 'ACTIVE'
  LEFT JOIN user_profiles p ON p.user_id = t.user_id
  LEFT JOIN branches b ON b.id = t.branch_id
  WHERE t.deleted_at IS NULL
    AND t.status = 'ACTIVE'
    AND EXISTS (SELECT 1 FROM trainer_weekly_schedule ws2 WHERE ws2.trainer_id = t.id)
    AND (p_activity_type IS NULL
         OR EXISTS (SELECT 1 FROM trainer_specialties ts2
                    WHERE ts2.trainer_id = t.id AND ts2.specialty = p_activity_type))
  ORDER BY p.full_name;
END$$

-- ============================================================
-- sp_trainer_schedule_get
-- Giờ làm việc hằng tuần của một PT (giờ địa phương, dạng HH:MM).
-- ============================================================
CREATE PROCEDURE sp_trainer_schedule_get(IN p_trainer_id CHAR(36))
BEGIN
  SELECT id,
         weekday,
         TIME_FORMAT(start_time, '%H:%i') AS start_time,
         TIME_FORMAT(end_time, '%H:%i') AS end_time
  FROM trainer_weekly_schedule
  WHERE trainer_id = p_trainer_id
  ORDER BY weekday, start_time;
END$$

-- ============================================================
-- sp_trainer_schedule_replace
-- PT lưu lại toàn bộ lịch tuần trong một transaction.
-- p_schedule: [{"weekday":1,"start_time":"17:00","end_time":"21:00"}, ...]
-- Buổi đã đặt KHÔNG bị ảnh hưởng; backend báo cho PT các buổi nằm ngoài lịch mới.
-- ============================================================
CREATE PROCEDURE sp_trainer_schedule_replace(
  IN p_user_id CHAR(36),
  IN p_schedule JSON
)
BEGIN
  DECLARE v_trainer_id CHAR(36) DEFAULT NULL;
  DECLARE v_overlaps INT DEFAULT 0;
  DECLARE v_rows INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INVALID_SCHEDULE' AS error_code,
           'Lịch làm việc không hợp lệ.' AS error_message,
           NULL AS trainer_id,
           0 AS slot_count;
  END;

  START TRANSACTION;

  SELECT t.id INTO v_trainer_id
  FROM trainer_profiles t
  WHERE t.user_id = p_user_id AND t.deleted_at IS NULL
  LIMIT 1
  FOR UPDATE;

  IF v_trainer_id IS NULL THEN
    SET v_error_code = 'TRAINER_NOT_FOUND';
    SET v_error_message = 'Tài khoản này không có hồ sơ huấn luyện viên.';
  ELSE
    DELETE FROM trainer_weekly_schedule WHERE trainer_id = v_trainer_id;

    INSERT INTO trainer_weekly_schedule (id, trainer_id, weekday, start_time, end_time)
    SELECT UUID(), v_trainer_id, j.weekday, j.start_time, j.end_time
    FROM JSON_TABLE(
      p_schedule, '$[*]'
      COLUMNS (
        weekday TINYINT PATH '$.weekday',
        start_time TIME PATH '$.start_time',
        end_time TIME PATH '$.end_time'
      )
    ) AS j;

    SET v_rows = ROW_COUNT();

    SELECT COUNT(*) INTO v_overlaps
    FROM trainer_weekly_schedule a
    JOIN trainer_weekly_schedule b
      ON b.trainer_id = a.trainer_id
     AND b.weekday = a.weekday
     AND a.id < b.id
     AND a.start_time < b.end_time
     AND b.start_time < a.end_time
    WHERE a.trainer_id = v_trainer_id;

    IF v_overlaps > 0 THEN
      SET v_error_code = 'SCHEDULE_OVERLAP';
      SET v_error_message = 'Các khung giờ trong cùng một ngày đang chồng lấn nhau.';
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         v_trainer_id AS trainer_id,
         CASE WHEN v_error_code IS NULL THEN v_rows ELSE 0 END AS slot_count;
END$$

-- ============================================================
-- sp_trainer_time_off_list
-- Các khoảng nghỉ đột xuất còn hiệu lực (kết thúc sau p_from).
-- ============================================================
CREATE PROCEDURE sp_trainer_time_off_list(
  IN p_trainer_id CHAR(36),
  IN p_from DATETIME(6),
  IN p_to DATETIME(6)
)
BEGIN
  SELECT id, trainer_id, start_at, end_at, reason, created_at
  FROM trainer_time_off
  WHERE trainer_id = p_trainer_id
    AND deleted_at IS NULL
    AND end_at > p_from
    AND (p_to IS NULL OR start_at < p_to)
  ORDER BY start_at;
END$$

-- ============================================================
-- sp_trainer_time_off_create
-- PT chặn một khoảng thời gian. Buổi đã đặt trong khoảng đó giữ nguyên;
-- backend liệt kê để PT tự huỷ kèm lý do (hội viên được hoàn lượt).
-- ============================================================
CREATE PROCEDURE sp_trainer_time_off_create(
  IN p_time_off_id CHAR(36),
  IN p_user_id CHAR(36),
  IN p_start_at DATETIME(6),
  IN p_end_at DATETIME(6),
  IN p_reason VARCHAR(255)
)
BEGIN
  DECLARE v_trainer_id CHAR(36) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  SELECT t.id INTO v_trainer_id
  FROM trainer_profiles t
  WHERE t.user_id = p_user_id AND t.deleted_at IS NULL
  LIMIT 1;

  IF v_trainer_id IS NULL THEN
    SET v_error_code = 'TRAINER_NOT_FOUND';
    SET v_error_message = 'Tài khoản này không có hồ sơ huấn luyện viên.';
  ELSEIF p_end_at <= p_start_at THEN
    SET v_error_code = 'INVALID_WINDOW';
    SET v_error_message = 'Thời điểm kết thúc phải sau thời điểm bắt đầu.';
  ELSEIF p_end_at <= UTC_TIMESTAMP(6) THEN
    SET v_error_code = 'PAST_WINDOW';
    SET v_error_message = 'Không thể đặt lịch nghỉ trong quá khứ.';
  ELSE
    INSERT INTO trainer_time_off (id, trainer_id, start_at, end_at, reason)
    VALUES (p_time_off_id, v_trainer_id, p_start_at, p_end_at, NULLIF(TRIM(p_reason), ''));
  END IF;

  COMMIT;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_time_off_id ELSE NULL END AS time_off_id,
         v_trainer_id AS trainer_id;
END$$

-- ============================================================
-- sp_trainer_time_off_delete
-- ============================================================
CREATE PROCEDURE sp_trainer_time_off_delete(
  IN p_time_off_id CHAR(36),
  IN p_user_id CHAR(36)
)
BEGIN
  DECLARE v_updated INT DEFAULT 0;

  UPDATE trainer_time_off o
  JOIN trainer_profiles t ON t.id = o.trainer_id
  SET o.deleted_at = UTC_TIMESTAMP(6)
  WHERE o.id = p_time_off_id
    AND t.user_id = p_user_id
    AND o.deleted_at IS NULL;

  SET v_updated = ROW_COUNT();
  COMMIT;

  SELECT CASE WHEN v_updated = 0 THEN 'TIME_OFF_NOT_FOUND' ELSE NULL END AS error_code,
         CASE WHEN v_updated = 0 THEN 'Không tìm thấy lịch nghỉ.' ELSE NULL END AS error_message;
END$$

-- ============================================================
-- sp_trainer_busy_list
-- Các buổi đang giữ chỗ của PT, dùng để loại khỏi danh sách ô trống.
-- Không trả thông tin hội viên.
-- ============================================================
CREATE PROCEDURE sp_trainer_busy_list(
  IN p_trainer_id CHAR(36),
  IN p_from DATETIME(6),
  IN p_to DATETIME(6)
)
BEGIN
  SELECT start_at, end_at
  FROM pt_bookings
  WHERE trainer_id = p_trainer_id
    AND status IN ('REQUESTED', 'ACCEPTED')
    AND deleted_at IS NULL
    AND end_at > p_from
    AND start_at < p_to
  ORDER BY start_at;
END$$

-- ============================================================
-- sp_pt_session_book
-- Hội viên đặt một ô trong lịch làm việc của PT → xác nhận ngay (ACCEPTED).
-- Khoá dòng PT để hai người đặt cùng lúc không cùng lấy được một ô.
-- p_local_*: ngày/giờ địa phương do backend tính, dùng để đối chiếu lịch tuần.
-- p_local_label: giờ địa phương đã định dạng (HH:MM dd/mm/yyyy) cho thông báo.
-- ============================================================
CREATE PROCEDURE sp_pt_session_book(
  IN p_booking_id CHAR(36),
  IN p_booking_number VARCHAR(40),
  IN p_user_id CHAR(36),
  IN p_trainer_id CHAR(36),
  IN p_start_at DATETIME(6),
  IN p_end_at DATETIME(6),
  IN p_local_weekday TINYINT,
  IN p_local_start TIME,
  IN p_local_end TIME,
  IN p_local_label VARCHAR(60),
  IN p_notes TEXT
)
BEGIN
  DECLARE v_member_id CHAR(36) DEFAULT NULL;
  DECLARE v_member_name VARCHAR(150) DEFAULT NULL;
  DECLARE v_subscription_id CHAR(36) DEFAULT NULL;
  DECLARE v_activity_type VARCHAR(12) DEFAULT NULL;
  DECLARE v_trainer_user_id CHAR(36) DEFAULT NULL;
  DECLARE v_trainer_name VARCHAR(150) DEFAULT NULL;
  DECLARE v_account_id CHAR(36) DEFAULT NULL;
  DECLARE v_purchased INT DEFAULT 0;
  DECLARE v_reserved INT DEFAULT 0;
  DECLARE v_used INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  -- Trigger chống trùng lịch là lớp bảo vệ cuối cùng.
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    ROLLBACK;
    SELECT 'SLOT_UNAVAILABLE' AS error_code,
           'Khung giờ này vừa có người đặt, vui lòng chọn giờ khác.' AS error_message,
           NULL AS booking_id;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể đặt buổi PT do lỗi hệ thống.' AS error_message,
           NULL AS booking_id;
  END;

  START TRANSACTION;

  SELECT m.id, m.full_name INTO v_member_id, v_member_name
  FROM members m
  WHERE m.user_id = p_user_id AND m.deleted_at IS NULL
  LIMIT 1;

  SELECT t.user_id INTO v_trainer_user_id
  FROM trainer_profiles t
  WHERE t.id = p_trainer_id AND t.deleted_at IS NULL AND t.status = 'ACTIVE'
  LIMIT 1
  FOR UPDATE;

  IF v_member_id IS NULL THEN
    SET v_error_code = 'MEMBER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy hồ sơ hội viên.';
  ELSEIF v_trainer_user_id IS NULL THEN
    SET v_error_code = 'TRAINER_NOT_FOUND';
    SET v_error_message = 'Huấn luyện viên không tồn tại hoặc đã ngừng hoạt động.';
  END IF;

  IF v_error_code IS NULL THEN
    SELECT s.id, pl.activity_type
    INTO v_subscription_id, v_activity_type
    FROM membership_subscriptions s
    JOIN membership_plans pl ON pl.id = s.plan_id
    WHERE s.member_id = v_member_id
      AND s.status = 'ACTIVE'
      AND s.deleted_at IS NULL
      AND s.start_at <= p_start_at
      AND s.end_at >= p_end_at
    ORDER BY s.end_at DESC
    LIMIT 1;

    IF v_subscription_id IS NULL THEN
      SET v_error_code = 'NO_ACTIVE_SUBSCRIPTION';
      SET v_error_message = 'Cần có gói hội viên còn hiệu lực trong ngày tập để đặt PT.';
    END IF;
  END IF;

  IF v_error_code IS NULL AND NOT EXISTS (
    SELECT 1 FROM trainer_weekly_schedule ws
    WHERE ws.trainer_id = p_trainer_id
      AND ws.weekday = p_local_weekday
      AND ws.start_time <= p_local_start
      AND ws.end_time >= p_local_end
  ) THEN
    SET v_error_code = 'OUTSIDE_SCHEDULE';
    SET v_error_message = 'Giờ này nằm ngoài lịch làm việc của huấn luyện viên.';
  END IF;

  IF v_error_code IS NULL AND EXISTS (
    SELECT 1 FROM trainer_time_off o
    WHERE o.trainer_id = p_trainer_id
      AND o.deleted_at IS NULL
      AND p_start_at < o.end_at
      AND p_end_at > o.start_at
  ) THEN
    SET v_error_code = 'TRAINER_OFF';
    SET v_error_message = 'Huấn luyện viên nghỉ vào thời gian này.';
  END IF;

  IF v_error_code IS NULL AND EXISTS (
    SELECT 1 FROM pt_bookings b
    WHERE b.trainer_id = p_trainer_id
      AND b.status IN ('REQUESTED', 'ACCEPTED')
      AND b.deleted_at IS NULL
      AND p_start_at < b.end_at
      AND p_end_at > b.start_at
  ) THEN
    SET v_error_code = 'SLOT_UNAVAILABLE';
    SET v_error_message = 'Khung giờ này vừa có người đặt, vui lòng chọn giờ khác.';
  END IF;

  IF v_error_code IS NULL AND EXISTS (
    SELECT 1 FROM pt_bookings b
    WHERE b.member_id = v_member_id
      AND b.status IN ('REQUESTED', 'ACCEPTED')
      AND b.deleted_at IS NULL
      AND p_start_at < b.end_at
      AND p_end_at > b.start_at
  ) THEN
    SET v_error_code = 'MEMBER_BUSY';
    SET v_error_message = 'Bạn đã có một buổi PT khác trùng giờ này.';
  END IF;

  IF v_error_code IS NULL THEN
    SELECT id, purchased_sessions, reserved_sessions, used_sessions
    INTO v_account_id, v_purchased, v_reserved, v_used
    FROM pt_credit_accounts
    WHERE member_id = v_member_id
    LIMIT 1
    FOR UPDATE;

    IF v_account_id IS NULL OR v_purchased - v_reserved - v_used < 1 THEN
      SET v_error_code = 'NO_PT_CREDIT';
      SET v_error_message = 'Bạn chưa có lượt PT khả dụng. Hãy mua thêm buổi.';
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    UPDATE pt_credit_accounts
    SET reserved_sessions = reserved_sessions + 1,
        row_version = row_version + 1
    WHERE id = v_account_id;

    INSERT INTO pt_bookings
      (id, booking_number, member_id, trainer_id, subscription_id, credit_account_id,
       availability_id, activity_type, start_at, end_at, status,
       requested_at, responded_at, notes)
    VALUES
      (p_booking_id, p_booking_number, v_member_id, p_trainer_id, v_subscription_id,
       v_account_id, NULL, v_activity_type, p_start_at, p_end_at, 'ACCEPTED',
       UTC_TIMESTAMP(6), UTC_TIMESTAMP(6), NULLIF(TRIM(p_notes), ''));

    INSERT INTO pt_credit_ledger
      (id, credit_account_id, booking_id, transaction_type,
       purchased_delta, reserved_delta, used_delta,
       purchased_balance, reserved_balance, used_balance,
       idempotency_key, reason, created_by)
    VALUES
      (UUID(), v_account_id, p_booking_id, 'RESERVE',
       0, 1, 0,
       v_purchased, v_reserved + 1, v_used,
       CONCAT('reserve-', p_booking_id),
       'Giữ 1 lượt cho buổi PT đã đặt', p_user_id);

    INSERT INTO notifications
      (id, user_id, notification_type, title, body, data, action_url)
    VALUES
      (UUID(), v_trainer_user_id, 'PT_SESSION_BOOKED',
       'Có buổi PT mới',
       CONCAT(COALESCE(v_member_name, 'Một hội viên'), ' đã đặt buổi tập lúc ', p_local_label, '.'),
       JSON_OBJECT(
         'booking_id', p_booking_id,
         'start_at', DATE_FORMAT(p_start_at, '%Y-%m-%dT%H:%i:%sZ'),
         'activity_type', v_activity_type
       ),
       '/pt');

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_booking_id ELSE NULL END AS booking_id;
END$$

-- ============================================================
-- sp_pt_session_cancel
-- Hội viên hoặc PT phụ trách huỷ một buổi chưa bắt đầu.
--   * PT huỷ: bắt buộc lý do, luôn hoàn lượt.
--   * Hội viên huỷ trước giờ tập >= p_refund_minutes: hoàn lượt;
--     huỷ sát giờ hơn: lượt bị tính là đã dùng.
-- ============================================================
CREATE PROCEDURE sp_pt_session_cancel(
  IN p_booking_id CHAR(36),
  IN p_user_id CHAR(36),
  IN p_reason TEXT,
  IN p_refund_minutes INT,
  IN p_utc_offset_minutes INT
)
BEGIN
  DECLARE v_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_label VARCHAR(40) DEFAULT NULL;
  DECLARE v_start_at DATETIME(6) DEFAULT NULL;
  DECLARE v_account_id CHAR(36) DEFAULT NULL;
  DECLARE v_member_user_id CHAR(36) DEFAULT NULL;
  DECLARE v_trainer_user_id CHAR(36) DEFAULT NULL;
  DECLARE v_member_name VARCHAR(150) DEFAULT NULL;
  DECLARE v_trainer_name VARCHAR(150) DEFAULT NULL;
  DECLARE v_actor VARCHAR(12) DEFAULT NULL;
  DECLARE v_refund BOOLEAN DEFAULT FALSE;
  DECLARE v_purchased INT DEFAULT 0;
  DECLARE v_reserved INT DEFAULT 0;
  DECLARE v_used INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể huỷ buổi PT do lỗi hệ thống.' AS error_message,
           NULL AS booking_id,
           NULL AS refunded,
           NULL AS cancelled_by_role;
  END;

  START TRANSACTION;

  SELECT b.status, b.start_at, b.credit_account_id, mu.id, tu.id, mp.full_name, tp.full_name
  INTO v_status, v_start_at, v_account_id, v_member_user_id, v_trainer_user_id,
       v_member_name, v_trainer_name
  FROM pt_bookings b
  JOIN members m ON m.id = b.member_id
  JOIN users mu ON mu.id = m.user_id
  LEFT JOIN user_profiles mp ON mp.user_id = mu.id
  JOIN trainer_profiles t ON t.id = b.trainer_id
  JOIN users tu ON tu.id = t.user_id
  LEFT JOIN user_profiles tp ON tp.user_id = tu.id
  WHERE b.id = p_booking_id AND b.deleted_at IS NULL
  LIMIT 1
  FOR UPDATE;

  -- Giờ địa phương cho nội dung thông báo (DB lưu UTC).
  SET v_label = DATE_FORMAT(DATE_ADD(v_start_at, INTERVAL p_utc_offset_minutes MINUTE), '%H:%i %d/%m/%Y');

  IF v_member_user_id = p_user_id THEN
    SET v_actor = 'MEMBER';
  ELSEIF v_trainer_user_id = p_user_id THEN
    SET v_actor = 'TRAINER';
  END IF;

  -- Người không liên quan nhận "không tìm thấy", không lộ buổi của người khác.
  IF v_status IS NULL OR v_actor IS NULL THEN
    SET v_error_code = 'BOOKING_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy buổi PT.';
  ELSEIF v_status NOT IN ('REQUESTED', 'ACCEPTED') THEN
    SET v_error_code = 'BOOKING_NOT_ACTIVE';
    SET v_error_message = 'Buổi này đã kết thúc hoặc đã bị huỷ.';
  ELSEIF v_start_at <= UTC_TIMESTAMP(6) THEN
    SET v_error_code = 'SESSION_STARTED';
    SET v_error_message = 'Buổi tập đã bắt đầu, không thể huỷ.';
  ELSEIF v_actor = 'TRAINER' AND NULLIF(TRIM(p_reason), '') IS NULL THEN
    SET v_error_code = 'REASON_REQUIRED';
    SET v_error_message = 'Vui lòng nhập lý do huỷ để thông báo cho hội viên.';
  END IF;

  IF v_error_code IS NULL THEN
    SET v_refund = (v_actor = 'TRAINER'
      OR TIMESTAMPDIFF(MINUTE, UTC_TIMESTAMP(6), v_start_at) >= p_refund_minutes);

    UPDATE pt_bookings
    SET status = 'CANCELLED',
        cancellation_reason = NULLIF(TRIM(p_reason), ''),
        cancelled_at = UTC_TIMESTAMP(6),
        cancelled_by = p_user_id,
        cancelled_by_role = v_actor,
        row_version = row_version + 1
    WHERE id = p_booking_id;

    SELECT purchased_sessions, reserved_sessions, used_sessions
    INTO v_purchased, v_reserved, v_used
    FROM pt_credit_accounts
    WHERE id = v_account_id
    FOR UPDATE;

    IF v_refund THEN
      UPDATE pt_credit_accounts
      SET reserved_sessions = reserved_sessions - 1, row_version = row_version + 1
      WHERE id = v_account_id;

      INSERT INTO pt_credit_ledger
        (id, credit_account_id, booking_id, transaction_type,
         purchased_delta, reserved_delta, used_delta,
         purchased_balance, reserved_balance, used_balance,
         idempotency_key, reason, created_by)
      VALUES
        (UUID(), v_account_id, p_booking_id, 'RELEASE',
         0, -1, 0,
         v_purchased, v_reserved - 1, v_used,
         CONCAT('release-', p_booking_id),
         CASE v_actor WHEN 'TRAINER' THEN 'Hoàn lượt do PT huỷ buổi'
                      ELSE 'Hoàn lượt do hội viên huỷ sớm' END,
         p_user_id);
    ELSE
      UPDATE pt_credit_accounts
      SET reserved_sessions = reserved_sessions - 1,
          used_sessions = used_sessions + 1,
          row_version = row_version + 1
      WHERE id = v_account_id;

      INSERT INTO pt_credit_ledger
        (id, credit_account_id, booking_id, transaction_type,
         purchased_delta, reserved_delta, used_delta,
         purchased_balance, reserved_balance, used_balance,
         idempotency_key, reason, created_by)
      VALUES
        (UUID(), v_account_id, p_booking_id, 'CONSUME',
         0, -1, 1,
         v_purchased, v_reserved - 1, v_used + 1,
         CONCAT('consume-', p_booking_id),
         'Hội viên huỷ sát giờ, lượt được tính là đã dùng', p_user_id);
    END IF;

    INSERT INTO notifications
      (id, user_id, notification_type, title, body, data, action_url)
    VALUES
      (UUID(),
       CASE v_actor WHEN 'TRAINER' THEN v_member_user_id ELSE v_trainer_user_id END,
       'PT_SESSION_CANCELLED',
       CASE v_actor WHEN 'TRAINER' THEN 'PT đã huỷ buổi tập' ELSE 'Hội viên đã huỷ buổi tập' END,
       CASE v_actor
         WHEN 'TRAINER' THEN CONCAT(
           COALESCE(v_trainer_name, 'PT'), ' đã huỷ buổi lúc ', v_label,
           '. Lý do: ', TRIM(p_reason), '. Lượt PT đã được hoàn lại.')
         ELSE CONCAT(
           COALESCE(v_member_name, 'Hội viên'), ' đã huỷ buổi lúc ', v_label,
           COALESCE(CONCAT('. Lý do: ', NULLIF(TRIM(p_reason), '')), ''), '.')
       END,
       JSON_OBJECT('booking_id', p_booking_id, 'refunded', v_refund),
       CASE v_actor WHEN 'TRAINER' THEN '/pt-booking' ELSE '/pt' END);

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_booking_id ELSE NULL END AS booking_id,
         v_refund AS refunded,
         v_actor AS cancelled_by_role;
END$$

-- ============================================================
-- sp_pt_session_finish
-- PT chốt buổi đã diễn ra: COMPLETED (hoàn thành) hoặc NO_SHOW (vắng mặt).
-- Cả hai đều chuyển lượt từ reserved sang used.
-- ============================================================
CREATE PROCEDURE sp_pt_session_finish(
  IN p_booking_id CHAR(36),
  IN p_user_id CHAR(36),
  IN p_outcome VARCHAR(16),
  IN p_utc_offset_minutes INT
)
BEGIN
  DECLARE v_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_label VARCHAR(40) DEFAULT NULL;
  DECLARE v_start_at DATETIME(6) DEFAULT NULL;
  DECLARE v_account_id CHAR(36) DEFAULT NULL;
  DECLARE v_trainer_user_id CHAR(36) DEFAULT NULL;
  DECLARE v_member_user_id CHAR(36) DEFAULT NULL;
  DECLARE v_trainer_name VARCHAR(150) DEFAULT NULL;
  DECLARE v_purchased INT DEFAULT 0;
  DECLARE v_reserved INT DEFAULT 0;
  DECLARE v_used INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể cập nhật buổi PT do lỗi hệ thống.' AS error_message,
           NULL AS booking_id;
  END;

  START TRANSACTION;

  SELECT b.status, b.start_at, b.credit_account_id, t.user_id, m.user_id, tp.full_name
  INTO v_status, v_start_at, v_account_id, v_trainer_user_id, v_member_user_id, v_trainer_name
  FROM pt_bookings b
  JOIN trainer_profiles t ON t.id = b.trainer_id
  JOIN members m ON m.id = b.member_id
  LEFT JOIN user_profiles tp ON tp.user_id = t.user_id
  WHERE b.id = p_booking_id AND b.deleted_at IS NULL
  LIMIT 1
  FOR UPDATE;

  -- Giờ địa phương cho nội dung thông báo (DB lưu UTC).
  SET v_label = DATE_FORMAT(DATE_ADD(v_start_at, INTERVAL p_utc_offset_minutes MINUTE), '%H:%i %d/%m/%Y');

  IF v_status IS NULL OR v_trainer_user_id <> p_user_id THEN
    SET v_error_code = 'BOOKING_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy buổi PT.';
  ELSEIF p_outcome NOT IN ('COMPLETED', 'NO_SHOW') THEN
    SET v_error_code = 'INVALID_STATUS';
    SET v_error_message = 'Trạng thái không hợp lệ.';
  ELSEIF v_status NOT IN ('REQUESTED', 'ACCEPTED') THEN
    SET v_error_code = 'BOOKING_NOT_ACTIVE';
    SET v_error_message = 'Buổi này đã được chốt hoặc đã bị huỷ.';
  ELSEIF v_start_at > UTC_TIMESTAMP(6) THEN
    SET v_error_code = 'SESSION_NOT_STARTED';
    SET v_error_message = 'Chỉ chốt được buổi tập khi đã tới giờ bắt đầu.';
  END IF;

  IF v_error_code IS NULL THEN
    UPDATE pt_bookings
    SET status = p_outcome,
        completed_at = CASE WHEN p_outcome = 'COMPLETED' THEN UTC_TIMESTAMP(6) ELSE NULL END,
        row_version = row_version + 1
    WHERE id = p_booking_id;

    SELECT purchased_sessions, reserved_sessions, used_sessions
    INTO v_purchased, v_reserved, v_used
    FROM pt_credit_accounts
    WHERE id = v_account_id
    FOR UPDATE;

    UPDATE pt_credit_accounts
    SET reserved_sessions = reserved_sessions - 1,
        used_sessions = used_sessions + 1,
        row_version = row_version + 1
    WHERE id = v_account_id;

    INSERT INTO pt_credit_ledger
      (id, credit_account_id, booking_id, transaction_type,
       purchased_delta, reserved_delta, used_delta,
       purchased_balance, reserved_balance, used_balance,
       idempotency_key, reason, created_by)
    VALUES
      (UUID(), v_account_id, p_booking_id, 'CONSUME',
       0, -1, 1,
       v_purchased, v_reserved - 1, v_used + 1,
       CONCAT('consume-', p_booking_id),
       CASE p_outcome WHEN 'COMPLETED' THEN 'Hoàn thành buổi PT' ELSE 'Vắng mặt buổi PT' END,
       p_user_id);

    INSERT INTO notifications
      (id, user_id, notification_type, title, body, data, action_url)
    VALUES
      (UUID(), v_member_user_id,
       CASE p_outcome WHEN 'COMPLETED' THEN 'PT_SESSION_COMPLETED' ELSE 'PT_SESSION_NO_SHOW' END,
       CASE p_outcome WHEN 'COMPLETED' THEN 'Buổi PT đã hoàn thành' ELSE 'Bạn đã vắng buổi PT' END,
       CASE p_outcome
         WHEN 'COMPLETED' THEN CONCAT('Buổi tập cùng ', COALESCE(v_trainer_name, 'PT'),
                                      ' lúc ', v_label, ' đã hoàn thành.')
         ELSE CONCAT(COALESCE(v_trainer_name, 'PT'), ' ghi nhận bạn vắng buổi lúc ',
                     v_label, '. Lượt PT của buổi này đã được tính.')
       END,
       JSON_OBJECT('booking_id', p_booking_id),
       '/pt-booking');

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_booking_id ELSE NULL END AS booking_id;
END$$

-- ============================================================
-- sp_pt_booking_list_for_trainer
-- Buổi dạy của PT: buổi sắp tới trước (tăng dần), sau đó lịch sử (giảm dần).
-- ============================================================
CREATE PROCEDURE sp_pt_booking_list_for_trainer(
  IN p_user_id CHAR(36),
  IN p_status VARCHAR(16)
)
BEGIN
  SELECT
    b.id,
    b.booking_number,
    b.status,
    b.activity_type,
    b.start_at,
    b.end_at,
    b.rejection_reason,
    b.cancellation_reason,
    b.cancelled_at,
    b.cancelled_by_role,
    b.completed_at,
    b.notes,
    b.requested_at,
    b.responded_at,
    b.trainer_id,
    t.employee_code,
    mp.full_name AS member_name,
    u.phone AS member_phone,
    u.email AS member_email,
    mb.member_code
  FROM pt_bookings b
  JOIN trainer_profiles t ON t.id = b.trainer_id
  JOIN members mb ON mb.id = b.member_id
  JOIN users u ON u.id = mb.user_id
  LEFT JOIN user_profiles mp ON mp.user_id = u.id
  WHERE t.user_id = p_user_id
    AND b.deleted_at IS NULL
    AND (p_status IS NULL OR b.status = p_status)
  ORDER BY
    CASE WHEN b.status IN ('REQUESTED', 'ACCEPTED') THEN 0 ELSE 1 END,
    CASE WHEN b.status IN ('REQUESTED', 'ACCEPTED') THEN b.start_at END ASC,
    b.start_at DESC;
END$$

-- ============================================================
-- sp_pt_booking_list_for_member
-- ============================================================
CREATE PROCEDURE sp_pt_booking_list_for_member(IN p_user_id CHAR(36))
BEGIN
  SELECT
    b.id,
    b.booking_number,
    b.status,
    b.activity_type,
    b.start_at,
    b.end_at,
    b.rejection_reason,
    b.cancellation_reason,
    b.cancelled_at,
    b.cancelled_by_role,
    b.completed_at,
    b.notes,
    b.requested_at,
    b.responded_at,
    b.trainer_id,
    tp.full_name AS trainer_name,
    t.employee_code,
    t.hourly_rate
  FROM pt_bookings b
  JOIN members m ON m.id = b.member_id
  JOIN trainer_profiles t ON t.id = b.trainer_id
  LEFT JOIN user_profiles tp ON tp.user_id = t.user_id
  WHERE m.user_id = p_user_id
    AND b.deleted_at IS NULL
  ORDER BY
    CASE WHEN b.status IN ('REQUESTED', 'ACCEPTED') THEN 0 ELSE 1 END,
    CASE WHEN b.status IN ('REQUESTED', 'ACCEPTED') THEN b.start_at END ASC,
    b.start_at DESC;
END$$

DELIMITER ;
