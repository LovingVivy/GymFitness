-- GymFitness stored procedures — hồ sơ huấn luyện viên, lượt PT và thông báo.
-- Lịch làm việc của PT và đặt/huỷ/chốt buổi PT nằm ở 07_pt_schedule.sql.
--
-- Toàn bộ truy vấn nằm ở đây; backend chỉ gọi CALL <procedure>(...).
-- Chạy sau 01_tables.sql, 02_triggers.sql, 03_procedures.sql, 04_seed.sql:
--   mysql -u root -p < database/05_procedures_pt.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS sp_trainer_find_by_user;
DROP PROCEDURE IF EXISTS sp_pt_credit_get;
DROP PROCEDURE IF EXISTS sp_pt_credit_purchase_create;
DROP PROCEDURE IF EXISTS sp_pt_credit_purchase_mark_paid;
DROP PROCEDURE IF EXISTS sp_payment_get;
DROP PROCEDURE IF EXISTS sp_notification_list;
DROP PROCEDURE IF EXISTS sp_notification_unread_count;
DROP PROCEDURE IF EXISTS sp_notification_mark_read;
DROP PROCEDURE IF EXISTS sp_notification_mark_all_read;

DELIMITER $$

-- ============================================================
-- sp_trainer_find_by_user
-- Hồ sơ huấn luyện viên của một tài khoản role PT.
-- ============================================================
CREATE PROCEDURE sp_trainer_find_by_user(IN p_user_id CHAR(36))
BEGIN
  SELECT
    t.id,
    t.user_id,
    t.employee_code,
    t.branch_id,
    b.name AS branch_name,
    t.bio,
    t.certifications,
    t.hourly_rate,
    t.status,
    u.email,
    p.full_name,
    (SELECT GROUP_CONCAT(ts.specialty ORDER BY ts.specialty)
     FROM trainer_specialties ts WHERE ts.trainer_id = t.id) AS specialties
  FROM trainer_profiles t
  JOIN users u ON u.id = t.user_id AND u.deleted_at IS NULL
  LEFT JOIN user_profiles p ON p.user_id = t.user_id
  LEFT JOIN branches b ON b.id = t.branch_id
  WHERE t.user_id = p_user_id AND t.deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_pt_credit_get
-- Ví lượt PT của hội viên. Tự tạo ví rỗng nếu chưa có.
-- ============================================================
CREATE PROCEDURE sp_pt_credit_get(IN p_user_id CHAR(36))
BEGIN
  DECLARE v_member_id CHAR(36) DEFAULT NULL;

  SELECT m.id INTO v_member_id
  FROM members m
  WHERE m.user_id = p_user_id AND m.deleted_at IS NULL
  LIMIT 1;

  IF v_member_id IS NULL THEN
    SELECT NULL AS credit_account_id, 0 AS purchased, 0 AS reserved, 0 AS used, 0 AS available;
  ELSE
    INSERT INTO pt_credit_accounts (id, member_id)
    SELECT UUID(), v_member_id
    WHERE NOT EXISTS (SELECT 1 FROM pt_credit_accounts WHERE member_id = v_member_id);

    SELECT
      a.id AS credit_account_id,
      a.purchased_sessions AS purchased,
      a.reserved_sessions AS reserved,
      a.used_sessions AS used,
      a.purchased_sessions - a.reserved_sessions - a.used_sessions AS available
    FROM pt_credit_accounts a
    WHERE a.member_id = v_member_id
    LIMIT 1;
  END IF;
END$$

-- ============================================================
-- sp_pt_credit_purchase_create
-- Tạo payment PENDING và giao dịch mua lượt PT PENDING.
-- Lượt chỉ được cộng sau khi backend xác nhận thanh toán.
-- ============================================================
CREATE PROCEDURE sp_pt_credit_purchase_create(
  IN p_purchase_id CHAR(36),
  IN p_payment_id CHAR(36),
  IN p_payment_number VARCHAR(40),
  IN p_idempotency_key VARCHAR(100),
  IN p_user_id CHAR(36),
  IN p_quantity INT,
  IN p_unit_price NUMERIC(14,2)
)
BEGIN
  DECLARE v_member_id CHAR(36) DEFAULT NULL;
  DECLARE v_account_id CHAR(36) DEFAULT NULL;
  DECLARE v_total NUMERIC(14,2) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể tạo giao dịch mua lượt PT.' AS error_message,
           NULL AS payment_id;
  END;

  START TRANSACTION;

  SELECT m.id INTO v_member_id
  FROM members m
  WHERE m.user_id = p_user_id AND m.deleted_at IS NULL
  LIMIT 1;

  IF v_member_id IS NULL THEN
    SET v_error_code = 'MEMBER_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy hồ sơ hội viên.';
  ELSEIF p_quantity IS NULL OR p_quantity < 1 OR p_quantity > 100 THEN
    SET v_error_code = 'INVALID_QUANTITY';
    SET v_error_message = 'Số buổi PT phải từ 1 đến 100.';
  END IF;

  IF v_error_code IS NULL THEN
    INSERT INTO pt_credit_accounts (id, member_id)
    SELECT UUID(), v_member_id
    WHERE NOT EXISTS (SELECT 1 FROM pt_credit_accounts WHERE member_id = v_member_id);

    SELECT id INTO v_account_id
    FROM pt_credit_accounts
    WHERE member_id = v_member_id
    LIMIT 1;

    SET v_total = p_quantity * p_unit_price;

    INSERT INTO payments
      (id, payment_number, member_id, purpose, amount, currency, method, status,
       idempotency_key, qr_payload, qr_expires_at, created_by)
    VALUES
      (p_payment_id, p_payment_number, v_member_id, 'PT_CREDIT', v_total, 'VND',
       'QR', 'PENDING', p_idempotency_key, CONCAT('IRONIX|', p_payment_number),
       DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 30 MINUTE), p_user_id);

    INSERT INTO pt_credit_purchases
      (id, credit_account_id, payment_id, quantity, unit_price, status)
    VALUES
      (p_purchase_id, v_account_id, p_payment_id, p_quantity, p_unit_price, 'PENDING');

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_payment_id ELSE NULL END AS payment_id,
         CASE WHEN v_error_code IS NULL THEN p_purchase_id ELSE NULL END AS purchase_id,
         v_total AS amount;
END$$

-- ============================================================
-- sp_pt_credit_purchase_mark_paid
-- Backend xác nhận thanh toán lượt PT: payment -> PAID, cộng lượt vào ví
-- và ghi sổ cái bất biến.
-- ============================================================
CREATE PROCEDURE sp_pt_credit_purchase_mark_paid(
  IN p_payment_id CHAR(36),
  IN p_changed_by CHAR(36)
)
BEGIN
  DECLARE v_payment_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_purchase_id CHAR(36) DEFAULT NULL;
  DECLARE v_purchase_status VARCHAR(16) DEFAULT NULL;
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
           'Không thể xác nhận thanh toán lượt PT.' AS error_message,
           NULL AS credit_account_id;
  END;

  START TRANSACTION;

  SELECT pym.status, pc.id, pc.status, pc.credit_account_id, pc.quantity
  INTO v_payment_status, v_purchase_id, v_purchase_status, v_account_id, v_quantity
  FROM payments pym
  JOIN pt_credit_purchases pc ON pc.payment_id = pym.id
  WHERE pym.id = p_payment_id
  LIMIT 1
  FOR UPDATE;

  IF v_payment_status IS NULL THEN
    SET v_error_code = 'PURCHASE_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy giao dịch mua lượt PT.';
  ELSEIF v_payment_status <> 'PENDING' OR v_purchase_status <> 'PENDING' THEN
    SET v_error_code = 'PAYMENT_NOT_PENDING';
    SET v_error_message = 'Giao dịch đã được xử lý trước đó.';
  ELSE
    SELECT purchased_sessions, reserved_sessions, used_sessions
    INTO v_purchased, v_reserved, v_used
    FROM pt_credit_accounts
    WHERE id = v_account_id
    FOR UPDATE;

    UPDATE payments
    SET status = 'PAID', paid_at = UTC_TIMESTAMP(6), row_version = row_version + 1
    WHERE id = p_payment_id;

    UPDATE pt_credit_accounts
    SET purchased_sessions = purchased_sessions + v_quantity,
        row_version = row_version + 1
    WHERE id = v_account_id;

    UPDATE pt_credit_purchases
    SET status = 'CREDITED', credited_at = UTC_TIMESTAMP(6)
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
       CONCAT('Mua ', v_quantity, ' buổi PT'), p_changed_by);

    COMMIT;
  END IF;

  IF v_error_code IS NOT NULL THEN
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         v_account_id AS credit_account_id;
END$$

-- ============================================================
-- sp_payment_get
-- Thông tin payment để backend quyết định kích hoạt loại quyền lợi nào.
-- ============================================================
CREATE PROCEDURE sp_payment_get(IN p_payment_id CHAR(36))
BEGIN
  SELECT id, payment_number, member_id, purpose, amount, currency, method, status, paid_at
  FROM payments
  WHERE id = p_payment_id
  LIMIT 1;
END$$

-- ============================================================
-- sp_notification_list
-- Thông báo trong ứng dụng của một tài khoản.
-- ============================================================
CREATE PROCEDURE sp_notification_list(
  IN p_user_id CHAR(36),
  IN p_limit INT
)
BEGIN
  DECLARE v_limit INT DEFAULT 30;

  IF p_limit IS NOT NULL AND p_limit > 0 AND p_limit <= 100 THEN
    SET v_limit = p_limit;
  END IF;

  SELECT
    n.id,
    n.notification_type,
    n.title,
    n.body,
    n.data,
    n.action_url,
    n.read_at,
    n.created_at
  FROM notifications n
  WHERE n.user_id = p_user_id
  ORDER BY n.created_at DESC
  LIMIT v_limit;
END$$

-- ============================================================
-- sp_notification_unread_count
-- ============================================================
CREATE PROCEDURE sp_notification_unread_count(IN p_user_id CHAR(36))
BEGIN
  SELECT COUNT(*) AS unread
  FROM notifications
  WHERE user_id = p_user_id AND read_at IS NULL;
END$$

-- ============================================================
-- sp_notification_mark_read
-- ============================================================
CREATE PROCEDURE sp_notification_mark_read(
  IN p_user_id CHAR(36),
  IN p_notification_id CHAR(36)
)
BEGIN
  UPDATE notifications
  SET read_at = UTC_TIMESTAMP(6)
  WHERE id = p_notification_id AND user_id = p_user_id AND read_at IS NULL;

  COMMIT;

  SELECT ROW_COUNT() AS updated;
END$$

-- ============================================================
-- sp_notification_mark_all_read
-- ============================================================
CREATE PROCEDURE sp_notification_mark_all_read(IN p_user_id CHAR(36))
BEGIN
  UPDATE notifications
  SET read_at = UTC_TIMESTAMP(6)
  WHERE user_id = p_user_id AND read_at IS NULL;

  COMMIT;

  SELECT ROW_COUNT() AS updated;
END$$

DELIMITER ;
