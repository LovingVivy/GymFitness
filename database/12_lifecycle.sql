-- GymFitness — vòng đời gói tập và buổi PT (ADR-026)
--
--   * Gói hết hạn chuyển ACTIVE → EXPIRED, kèm lịch sử và thông báo.
--   * Nhắc gia hạn trước 7, 3 và 1 ngày (mỗi mốc một lần, bỏ qua gói đã gia hạn).
--   * Buổi PT đã kết thúc quá lâu mà PT chưa chốt được tự ghi nhận hoàn thành.
--   * Khoá tài khoản PT/hội viên tự huỷ các buổi PT sắp tới và hoàn lượt.
--
-- Các procedure định kỳ do backend gọi (app/tasks/maintenance.py), chạy lại nhiều lần an toàn.
-- Chạy sau 11_platform.sql:
--   python scripts/apply_sql.py database/12_lifecycle.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS sp_subscription_expire_due;
DROP PROCEDURE IF EXISTS sp_subscription_reminders_due;
DROP PROCEDURE IF EXISTS sp_pt_session_autoclose;
DROP PROCEDURE IF EXISTS sp_pt_cancel_upcoming_for_user;
DROP PROCEDURE IF EXISTS sp_profile_memberships;

DELIMITER $$

-- ============================================================
-- sp_subscription_expire_due
-- Chuyển các gói đã quá end_at sang EXPIRED. Trả các gói vừa hết hạn mà hội viên
-- chưa gia hạn (không còn gói cùng loại hình kéo dài hơn) để backend gửi email.
-- ============================================================
CREATE PROCEDURE sp_subscription_expire_due()
BEGIN
  DECLARE v_now DATETIME(6) DEFAULT UTC_TIMESTAMP(6);

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    DROP TEMPORARY TABLE IF EXISTS _gf_expired;
    RESIGNAL;
  END;

  DROP TEMPORARY TABLE IF EXISTS _gf_expired;
  CREATE TEMPORARY TABLE _gf_expired (
    subscription_id CHAR(36) PRIMARY KEY,
    member_id CHAR(36) NOT NULL,
    activity_type VARCHAR(12) NOT NULL,
    end_at DATETIME(6) NOT NULL,
    renewed BOOLEAN NOT NULL DEFAULT FALSE
  );

  START TRANSACTION;

  INSERT INTO _gf_expired (subscription_id, member_id, activity_type, end_at)
  SELECT s.id, s.member_id, pl.activity_type, s.end_at
  FROM membership_subscriptions s
  JOIN membership_plans pl ON pl.id = s.plan_id
  WHERE s.status = 'ACTIVE'
    AND s.deleted_at IS NULL
    AND s.end_at <= v_now;

  UPDATE _gf_expired e
  SET e.renewed = EXISTS (
    SELECT 1
    FROM membership_subscriptions s
    JOIN membership_plans pl ON pl.id = s.plan_id
    WHERE s.member_id = e.member_id
      AND pl.activity_type = e.activity_type
      AND s.status = 'ACTIVE'
      AND s.deleted_at IS NULL
      AND s.end_at > v_now
  );

  UPDATE membership_subscriptions s
  JOIN _gf_expired e ON e.subscription_id = s.id
  SET s.status = 'EXPIRED', s.row_version = s.row_version + 1;

  INSERT INTO subscription_status_history (id, subscription_id, from_status, to_status, reason)
  SELECT UUID(), subscription_id, 'ACTIVE', 'EXPIRED', 'Gói tập hết hạn'
  FROM _gf_expired;

  INSERT INTO notifications
    (id, user_id, notification_type, title, body, data, action_url, idempotency_key)
  SELECT UUID(), m.user_id, 'MEMBERSHIP_EXPIRED', 'Gói tập đã hết hạn',
         CONCAT('Gói ', pl.name, ' đã hết hạn. Gia hạn để tiếp tục tập luyện và đặt PT.'),
         JSON_OBJECT('subscription_id', e.subscription_id), '/plans',
         CONCAT('expired-', e.subscription_id)
  FROM _gf_expired e
  JOIN membership_subscriptions s ON s.id = e.subscription_id
  JOIN membership_plans pl ON pl.id = s.plan_id
  JOIN members m ON m.id = e.member_id AND m.user_id IS NOT NULL
  WHERE e.renewed = FALSE
    AND NOT EXISTS (
      SELECT 1 FROM notifications n WHERE n.idempotency_key = CONCAT('expired-', e.subscription_id)
    );

  COMMIT;

  SELECT e.subscription_id, e.end_at, pl.name AS plan_name, u.email, p.full_name
  FROM _gf_expired e
  JOIN membership_subscriptions s ON s.id = e.subscription_id
  JOIN membership_plans pl ON pl.id = s.plan_id
  JOIN members m ON m.id = e.member_id
  JOIN users u ON u.id = m.user_id AND u.deleted_at IS NULL AND u.status = 'ACTIVE'
  LEFT JOIN user_profiles p ON p.user_id = u.id
  WHERE e.renewed = FALSE;

  DROP TEMPORARY TABLE IF EXISTS _gf_expired;
END$$

-- ============================================================
-- sp_subscription_reminders_due
-- Nhắc gia hạn ở các mốc còn ≤ 7 ngày, ≤ 3 ngày, ≤ 1 ngày. Mỗi gói mỗi mốc một
-- thông báo (khoá idempotency_key); gói đã có gói nối tiếp cùng loại hình thì bỏ qua.
-- Trả các nhắc vừa tạo để backend gửi email.
-- ============================================================
CREATE PROCEDURE sp_subscription_reminders_due()
BEGIN
  DECLARE v_now DATETIME(6) DEFAULT UTC_TIMESTAMP(6);

  -- Hai tiến trình cùng chạy: khoá idempotency_key chặn bản trùng, lần sau chạy lại.
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    DROP TEMPORARY TABLE IF EXISTS _gf_reminders;
    SELECT NULL AS subscription_id LIMIT 0;
  END;

  DROP TEMPORARY TABLE IF EXISTS _gf_reminders;
  CREATE TEMPORARY TABLE _gf_reminders (
    subscription_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    plan_name VARCHAR(150) NOT NULL,
    end_at DATETIME(6) NOT NULL,
    days_left INT NOT NULL,
    reminder_key VARCHAR(120) PRIMARY KEY
  );

  INSERT INTO _gf_reminders
  SELECT c.id, c.user_id, c.plan_name, c.end_at, c.bucket,
         CONCAT('expiring-', c.id, '-', c.bucket)
  FROM (
    SELECT s.id, m.user_id, pl.name AS plan_name, s.end_at,
           CASE
             WHEN TIMESTAMPDIFF(HOUR, v_now, s.end_at) < 24 THEN 1
             WHEN TIMESTAMPDIFF(HOUR, v_now, s.end_at) < 72 THEN 3
             ELSE 7
           END AS bucket
    FROM membership_subscriptions s
    JOIN membership_plans pl ON pl.id = s.plan_id
    JOIN members m ON m.id = s.member_id AND m.deleted_at IS NULL AND m.user_id IS NOT NULL
    JOIN users u ON u.id = m.user_id AND u.deleted_at IS NULL AND u.status = 'ACTIVE'
    WHERE s.status = 'ACTIVE'
      AND s.deleted_at IS NULL
      AND s.end_at > v_now
      AND s.end_at <= v_now + INTERVAL 7 DAY
      AND NOT EXISTS (
        SELECT 1
        FROM membership_subscriptions later
        JOIN membership_plans lpl ON lpl.id = later.plan_id
        WHERE later.member_id = s.member_id
          AND lpl.activity_type = pl.activity_type
          AND later.status = 'ACTIVE'
          AND later.deleted_at IS NULL
          AND later.end_at > s.end_at
      )
  ) AS c
  WHERE NOT EXISTS (
    SELECT 1 FROM notifications n WHERE n.idempotency_key = CONCAT('expiring-', c.id, '-', c.bucket)
  );

  START TRANSACTION;

  INSERT INTO notifications
    (id, user_id, notification_type, title, body, data, action_url, idempotency_key)
  SELECT UUID(), r.user_id, 'MEMBERSHIP_EXPIRING',
         CASE r.days_left WHEN 1 THEN 'Gói tập hết hạn trong 24 giờ'
                          ELSE CONCAT('Gói tập còn dưới ', r.days_left, ' ngày') END,
         CONCAT('Gói ', r.plan_name, ' sắp hết hạn. Gia hạn ngay để không bị gián đoạn — ',
                'ngày của gói mới được cộng nối tiếp, không mất ngày còn lại.'),
         JSON_OBJECT('subscription_id', r.subscription_id, 'days_left', r.days_left),
         '/plans', r.reminder_key
  FROM _gf_reminders r;

  COMMIT;

  SELECT r.subscription_id, r.end_at, r.days_left, r.plan_name, u.email, p.full_name
  FROM _gf_reminders r
  JOIN users u ON u.id = r.user_id
  LEFT JOIN user_profiles p ON p.user_id = u.id;

  DROP TEMPORARY TABLE IF EXISTS _gf_reminders;
END$$

-- ============================================================
-- sp_pt_session_autoclose
-- Buổi PT đã kết thúc quá p_grace_minutes mà PT chưa chốt: tự ghi nhận COMPLETED,
-- chuyển lượt reserved → used và báo cho hội viên. Trả số buổi đã đóng.
-- ============================================================
CREATE PROCEDURE sp_pt_session_autoclose(
  IN p_grace_minutes INT,
  IN p_utc_offset_minutes INT
)
BEGIN
  DECLARE v_done BOOLEAN DEFAULT FALSE;
  DECLARE v_closed INT DEFAULT 0;
  DECLARE v_booking_id CHAR(36);
  DECLARE v_account_id CHAR(36);
  DECLARE v_start_at DATETIME(6);
  DECLARE v_member_user_id CHAR(36);
  DECLARE v_purchased INT;
  DECLARE v_reserved INT;
  DECLARE v_used INT;

  DECLARE due CURSOR FOR
    SELECT b.id, b.credit_account_id, b.start_at, m.user_id
    FROM pt_bookings b
    JOIN members m ON m.id = b.member_id
    WHERE b.status IN ('REQUESTED', 'ACCEPTED')
      AND b.deleted_at IS NULL
      AND b.end_at < UTC_TIMESTAMP(6) - INTERVAL p_grace_minutes MINUTE
    ORDER BY b.end_at;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  OPEN due;
  close_loop: LOOP
    FETCH due INTO v_booking_id, v_account_id, v_start_at, v_member_user_id;
    IF v_done THEN
      LEAVE close_loop;
    END IF;

    START TRANSACTION;

    SELECT purchased_sessions, reserved_sessions, used_sessions
    INTO v_purchased, v_reserved, v_used
    FROM pt_credit_accounts
    WHERE id = v_account_id
    FOR UPDATE;

    UPDATE pt_bookings
    SET status = 'COMPLETED',
        completed_at = UTC_TIMESTAMP(6),
        row_version = row_version + 1
    WHERE id = v_booking_id AND status IN ('REQUESTED', 'ACCEPTED');

    IF ROW_COUNT() > 0 THEN
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
        (UUID(), v_account_id, v_booking_id, 'CONSUME',
         0, -1, 1,
         v_purchased, v_reserved - 1, v_used + 1,
         CONCAT('consume-', v_booking_id),
         'Hệ thống tự ghi nhận hoàn thành vì PT chưa chốt buổi', NULL);

      INSERT INTO notifications
        (id, user_id, notification_type, title, body, data, action_url)
      VALUES
        (UUID(), v_member_user_id, 'PT_SESSION_COMPLETED', 'Buổi PT đã hoàn thành',
         CONCAT('Buổi tập lúc ',
                DATE_FORMAT(DATE_ADD(v_start_at, INTERVAL p_utc_offset_minutes MINUTE), '%H:%i %d/%m/%Y'),
                ' được hệ thống ghi nhận hoàn thành. Nếu bạn đã vắng mặt, hãy liên hệ quầy lễ tân.'),
         JSON_OBJECT('booking_id', v_booking_id, 'auto_closed', TRUE), '/pt-booking');

      SET v_closed = v_closed + 1;
    END IF;

    COMMIT;
  END LOOP;
  CLOSE due;

  SELECT v_closed AS closed;
END$$

-- ============================================================
-- sp_pt_cancel_upcoming_for_user
-- Huỷ mọi buổi PT chưa bắt đầu của một tài khoản (PT hoặc hội viên) bị khoá/ngưng:
-- hoàn lượt cho hội viên, ghi sổ cái, báo cho bên còn lại.
-- Không tự COMMIT: chạy trong transaction của procedure gọi nó (sp_admin_user_update).
-- ============================================================
CREATE PROCEDURE sp_pt_cancel_upcoming_for_user(
  IN p_user_id CHAR(36),
  IN p_actor_id CHAR(36),
  IN p_reason VARCHAR(255),
  IN p_utc_offset_minutes INT,
  OUT p_cancelled INT
)
BEGIN
  DECLARE v_done BOOLEAN DEFAULT FALSE;
  DECLARE v_booking_id CHAR(36);
  DECLARE v_account_id CHAR(36);
  DECLARE v_start_at DATETIME(6);
  DECLARE v_member_user_id CHAR(36);
  DECLARE v_trainer_user_id CHAR(36);
  DECLARE v_purchased INT;
  DECLARE v_reserved INT;
  DECLARE v_used INT;

  DECLARE upcoming CURSOR FOR
    SELECT b.id, b.credit_account_id, b.start_at, m.user_id, t.user_id
    FROM pt_bookings b
    JOIN members m ON m.id = b.member_id
    JOIN trainer_profiles t ON t.id = b.trainer_id
    WHERE (m.user_id = p_user_id OR t.user_id = p_user_id)
      AND b.status IN ('REQUESTED', 'ACCEPTED')
      AND b.deleted_at IS NULL
      AND b.start_at > UTC_TIMESTAMP(6)
    ORDER BY b.start_at
    FOR UPDATE;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

  SET p_cancelled = 0;
  OPEN upcoming;
  cancel_loop: LOOP
    FETCH upcoming INTO v_booking_id, v_account_id, v_start_at, v_member_user_id, v_trainer_user_id;
    IF v_done THEN
      LEAVE cancel_loop;
    END IF;

    SELECT purchased_sessions, reserved_sessions, used_sessions
    INTO v_purchased, v_reserved, v_used
    FROM pt_credit_accounts
    WHERE id = v_account_id
    FOR UPDATE;

    UPDATE pt_bookings
    SET status = 'CANCELLED',
        cancellation_reason = p_reason,
        cancelled_at = UTC_TIMESTAMP(6),
        cancelled_by = p_actor_id,
        cancelled_by_role = 'ADMIN',
        row_version = row_version + 1
    WHERE id = v_booking_id;

    UPDATE pt_credit_accounts
    SET reserved_sessions = reserved_sessions - 1, row_version = row_version + 1
    WHERE id = v_account_id;

    INSERT INTO pt_credit_ledger
      (id, credit_account_id, booking_id, transaction_type,
       purchased_delta, reserved_delta, used_delta,
       purchased_balance, reserved_balance, used_balance,
       idempotency_key, reason, created_by)
    VALUES
      (UUID(), v_account_id, v_booking_id, 'RELEASE',
       0, -1, 0,
       v_purchased, v_reserved - 1, v_used,
       CONCAT('release-', v_booking_id), CONCAT('Hoàn lượt: ', p_reason), p_actor_id);

    -- Báo cho bên không bị khoá.
    INSERT INTO notifications
      (id, user_id, notification_type, title, body, data, action_url)
    VALUES
      (UUID(),
       IF(v_trainer_user_id = p_user_id, v_member_user_id, v_trainer_user_id),
       'PT_SESSION_CANCELLED', 'Buổi PT đã bị huỷ',
       CONCAT('Buổi lúc ',
              DATE_FORMAT(DATE_ADD(v_start_at, INTERVAL p_utc_offset_minutes MINUTE), '%H:%i %d/%m/%Y'),
              ' đã được huỷ. Lý do: ', p_reason,
              IF(v_trainer_user_id = p_user_id, '. Lượt PT đã được hoàn lại.', '.')),
       JSON_OBJECT('booking_id', v_booking_id, 'refunded', TRUE),
       IF(v_trainer_user_id = p_user_id, '/pt-booking', '/pt'));

    SET p_cancelled = p_cancelled + 1;
  END LOOP;
  CLOSE upcoming;
END$$

-- ============================================================
-- sp_profile_memberships
-- Mọi gói còn hiệu lực của một tài khoản, gộp theo loại hình (Gym, Yoga):
-- coverage_start_at/end_at là cả chuỗi gói nối tiếp nhau (gia hạn sớm).
-- ============================================================
CREATE PROCEDURE sp_profile_memberships(IN p_user_id CHAR(36))
BEGIN
  SELECT
    s.id AS subscription_id,
    s.status,
    s.start_at,
    s.end_at,
    pl.id AS plan_id,
    pl.code AS plan_code,
    pl.name AS plan_name,
    pl.activity_type,
    pl.duration_months,
    pl.duration_days,
    pl.price,
    pl.currency,
    chain.coverage_start_at
  FROM members m
  JOIN (
    SELECT s2.member_id, pl2.activity_type,
           MIN(s2.start_at) AS coverage_start_at,
           MAX(s2.end_at) AS coverage_end_at
    FROM membership_subscriptions s2
    JOIN membership_plans pl2 ON pl2.id = s2.plan_id
    WHERE s2.status IN ('ACTIVE', 'FROZEN')
      AND s2.deleted_at IS NULL
      AND s2.end_at > UTC_TIMESTAMP(6)
    GROUP BY s2.member_id, pl2.activity_type
  ) AS chain ON chain.member_id = m.id
  JOIN membership_subscriptions s
    ON s.member_id = m.id AND s.end_at = chain.coverage_end_at
   AND s.status IN ('ACTIVE', 'FROZEN') AND s.deleted_at IS NULL
  JOIN membership_plans pl ON pl.id = s.plan_id AND pl.activity_type = chain.activity_type
  WHERE m.user_id = p_user_id AND m.deleted_at IS NULL
  ORDER BY s.end_at DESC;
END$$

DELIMITER ;
