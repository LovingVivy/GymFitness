-- GymFitness stored procedures — thanh toán chuyển khoản QR tự động
--
-- Luồng (ADR-004, ADR-012):
--   1. Backend tạo payment PENDING với payment_number là mã chuyển khoản.
--   2. Hội viên quét VietQR, nội dung chuyển khoản chứa payment_number.
--   3. Cổng đối soát (SePay) gọi webhook; backend ghi payment_events, khớp mã,
--      kiểm tra số tiền rồi mới gọi sp_subscription_mark_paid /
--      sp_pt_credit_purchase_mark_paid.
--   4. Frontend hỏi trạng thái qua sp_payment_get_for_user cho tới khi PAID.
--
-- Chạy file này sau 05_procedures_pt.sql:
--   python scripts/apply_sql.py database/06_procedures_payment.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS sp_payment_get_for_user;
DROP PROCEDURE IF EXISTS sp_payment_find_by_number;
DROP PROCEDURE IF EXISTS sp_payment_event_record;
DROP PROCEDURE IF EXISTS sp_payment_event_finish;
DROP PROCEDURE IF EXISTS sp_payment_notify_paid;

DELIMITER $$

-- ============================================================
-- sp_payment_get_for_user
-- Trạng thái một payment, chỉ khi payment thuộc về chính tài khoản đó.
-- Không có dòng nào nghĩa là không tồn tại hoặc không phải của người gọi.
-- ============================================================
CREATE PROCEDURE sp_payment_get_for_user(
  IN p_payment_id CHAR(36),
  IN p_user_id CHAR(36)
)
BEGIN
  SELECT pym.id, pym.payment_number, pym.member_id, pym.purpose, pym.amount,
         pym.currency, pym.method, pym.status, pym.provider, pym.paid_at,
         pym.qr_expires_at, pym.created_at
  FROM payments pym
  JOIN members m ON m.id = pym.member_id
  WHERE pym.id = p_payment_id
    AND m.user_id = p_user_id
    AND m.deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_payment_find_by_number
-- Khớp mã chuyển khoản trong webhook với payment tương ứng.
-- ============================================================
CREATE PROCEDURE sp_payment_find_by_number(IN p_payment_number VARCHAR(40))
BEGIN
  SELECT pym.id, pym.payment_number, pym.member_id, m.user_id, pym.purpose,
         pym.amount, pym.currency, pym.status, pym.qr_expires_at
  FROM payments pym
  LEFT JOIN members m ON m.id = pym.member_id
  WHERE pym.payment_number = p_payment_number
  LIMIT 1;
END$$

-- ============================================================
-- sp_payment_event_record
-- Ghi nhận thô mọi webhook nhận được (kể cả không khớp) để đối soát.
-- UNIQUE (provider, provider_event_id) đảm bảo idempotency: webhook gửi
-- lại trả về dòng cũ với duplicate = TRUE.
-- ============================================================
CREATE PROCEDURE sp_payment_event_record(
  IN p_event_id CHAR(36),
  IN p_provider VARCHAR(50),
  IN p_provider_event_id VARCHAR(150),
  IN p_event_type VARCHAR(80),
  IN p_signature_valid BOOLEAN,
  IN p_payload JSON
)
BEGIN
  DECLARE v_duplicate BOOLEAN DEFAULT FALSE;
  DECLARE CONTINUE HANDLER FOR 1062 SET v_duplicate = TRUE;

  INSERT INTO payment_events
    (id, provider, provider_event_id, event_type, signature_valid, payload)
  VALUES
    (p_event_id, p_provider, p_provider_event_id, p_event_type, p_signature_valid, p_payload);

  COMMIT;

  IF v_duplicate THEN
    SELECT TRUE AS duplicate, e.id AS event_id, e.payment_id, e.processed_at, e.error_message
    FROM payment_events e
    WHERE e.provider = p_provider AND e.provider_event_id = p_provider_event_id
    LIMIT 1;
  ELSE
    SELECT FALSE AS duplicate, p_event_id AS event_id, NULL AS payment_id,
           NULL AS processed_at, NULL AS error_message;
  END IF;
END$$

-- ============================================================
-- sp_payment_event_finish
-- Đánh dấu webhook đã xử lý. Khi thành công, gắn mã tham chiếu ngân hàng
-- vào payment để tra soát (UNIQUE provider + external_reference).
-- ============================================================
CREATE PROCEDURE sp_payment_event_finish(
  IN p_event_id CHAR(36),
  IN p_payment_id CHAR(36),
  IN p_error_message TEXT,
  IN p_provider VARCHAR(50),
  IN p_external_reference VARCHAR(150)
)
BEGIN
  -- Mã tham chiếu đã gắn cho payment khác thì bỏ qua, không làm hỏng việc ghi nhận.
  DECLARE CONTINUE HANDLER FOR 1062 BEGIN END;

  UPDATE payment_events
  SET payment_id = p_payment_id,
      processed_at = UTC_TIMESTAMP(6),
      error_message = p_error_message
  WHERE id = p_event_id;

  IF p_payment_id IS NOT NULL AND p_error_message IS NULL AND p_external_reference IS NOT NULL THEN
    UPDATE payments
    SET provider = p_provider,
        external_reference = p_external_reference
    WHERE id = p_payment_id AND external_reference IS NULL;
  END IF;

  COMMIT;

  SELECT p_event_id AS event_id;
END$$

-- ============================================================
-- sp_payment_notify_paid
-- Thông báo trong ứng dụng khi payment đã PAID. Idempotent theo payment.
-- ============================================================
CREATE PROCEDURE sp_payment_notify_paid(IN p_payment_id CHAR(36))
BEGIN
  DECLARE v_inserted INT DEFAULT 0;

  INSERT INTO notifications
    (id, user_id, notification_type, title, body, data, action_url, idempotency_key)
  SELECT UUID(), m.user_id, 'PAYMENT_PAID', 'Thanh toán thành công',
         CONCAT('Đã nhận ', FORMAT(pym.amount, 0, 'vi_VN'), 'đ cho giao dịch ',
                pym.payment_number,
                CASE
                  WHEN pym.purpose = 'PT_CREDIT' THEN '. Lượt PT đã được cộng vào ví.'
                  WHEN pc.quantity IS NOT NULL THEN
                    CONCAT('. Gói hội viên đã được kích hoạt và cộng ', pc.quantity, ' buổi PT.')
                  ELSE '. Gói hội viên đã được kích hoạt.'
                END),
         JSON_OBJECT('payment_id', pym.id, 'purpose', pym.purpose,
                     'payment_number', pym.payment_number),
         CASE pym.purpose WHEN 'PT_CREDIT' THEN '/pt-booking' ELSE '/profile' END,
         CONCAT('payment-paid-', pym.id)
  FROM payments pym
  JOIN members m ON m.id = pym.member_id
  LEFT JOIN pt_credit_purchases pc ON pc.payment_id = pym.id
  WHERE pym.id = p_payment_id AND pym.status = 'PAID'
  ON DUPLICATE KEY UPDATE id = notifications.id;

  -- ROW_COUNT: 1 = vừa tạo, 0 = đã có từ trước (idempotent).
  SET v_inserted = ROW_COUNT();
  COMMIT;

  SELECT v_inserted AS inserted;
END$$

DELIMITER ;
