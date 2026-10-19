-- GymFitness — nền tảng: vai trò Manager, đặt lại mật khẩu, xác thực 2 bước,
-- hàng đợi tác vụ, nhật ký thao tác, hoá đơn và xuất/nhập dữ liệu (ADR-019 … ADR-023).
--
-- File này vừa tạo mới vừa nâng cấp database đang chạy, chạy lại nhiều lần an toàn.
-- Chạy sau 10_seed_demo.sql (hoặc sau 09_admin_shop.sql nếu không nạp dữ liệu mẫu):
--   python scripts/apply_sql.py database/11_platform.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ============================================================
-- Vai trò MANAGER: thay CHECK cũ (ADMIN/USER/PT) bằng chk_users_role
-- ============================================================

DROP PROCEDURE IF EXISTS _gf_migrate_role_check;

DELIMITER $$

CREATE PROCEDURE _gf_migrate_role_check()
BEGIN
  DECLARE v_name VARCHAR(64) DEFAULT NULL;

  SELECT cc.CONSTRAINT_NAME INTO v_name
  FROM information_schema.CHECK_CONSTRAINTS cc
  JOIN information_schema.TABLE_CONSTRAINTS tc
    ON tc.CONSTRAINT_SCHEMA = cc.CONSTRAINT_SCHEMA
   AND tc.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
  WHERE cc.CONSTRAINT_SCHEMA = DATABASE()
    AND tc.TABLE_NAME = 'users'
    AND tc.CONSTRAINT_TYPE = 'CHECK'
    AND cc.CHECK_CLAUSE LIKE '%`role`%'
    AND cc.CHECK_CLAUSE NOT LIKE '%MANAGER%'
  LIMIT 1;

  IF v_name IS NOT NULL THEN
    SET @gf_ddl = CONCAT('ALTER TABLE users DROP CHECK `', v_name, '`');
    PREPARE gf_stmt FROM @gf_ddl;
    EXECUTE gf_stmt;
    DEALLOCATE PREPARE gf_stmt;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'users'
      AND CONSTRAINT_NAME = 'chk_users_role'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT chk_users_role CHECK (role IN ('ADMIN', 'MANAGER', 'USER', 'PT'));
  END IF;
END$$

DELIMITER ;

CALL _gf_migrate_role_check();
DROP PROCEDURE IF EXISTS _gf_migrate_role_check;

-- ============================================================
-- Procedure
-- ============================================================

DROP PROCEDURE IF EXISTS sp_health_ping;
DROP PROCEDURE IF EXISTS sp_password_reset_create;
DROP PROCEDURE IF EXISTS sp_password_reset_consume;
DROP PROCEDURE IF EXISTS sp_auth_two_factor_get;
DROP PROCEDURE IF EXISTS sp_auth_two_factor_set;
DROP PROCEDURE IF EXISTS sp_file_save;
DROP PROCEDURE IF EXISTS sp_job_create;
DROP PROCEDURE IF EXISTS sp_job_claim;
DROP PROCEDURE IF EXISTS sp_job_progress;
DROP PROCEDURE IF EXISTS sp_job_finish;
DROP PROCEDURE IF EXISTS sp_job_get;
DROP PROCEDURE IF EXISTS sp_job_list;
DROP PROCEDURE IF EXISTS sp_job_pending_list;
DROP PROCEDURE IF EXISTS sp_audit_log_list;
DROP PROCEDURE IF EXISTS sp_invoice_issue;
DROP PROCEDURE IF EXISTS sp_pt_booking_contact;
DROP PROCEDURE IF EXISTS sp_admin_product_find_by_sku;

DELIMITER $$

-- ============================================================
-- sp_password_reset_create
-- Tạo liên kết đặt lại mật khẩu cho một tài khoản còn hoạt động. Chỉ lưu SHA-256
-- của token; token gốc chỉ nằm trong email. Liên kết cũ chưa dùng bị vô hiệu.
-- Trả email/họ tên để gửi thư; NULL nếu tài khoản không đủ điều kiện.
-- ============================================================
CREATE PROCEDURE sp_password_reset_create(
  IN p_token_id CHAR(36),
  IN p_user_id CHAR(36),
  IN p_token_digest CHAR(64),
  IN p_ttl_minutes INT
)
BEGIN
  DECLARE v_email VARCHAR(254) DEFAULT NULL;
  DECLARE v_full_name VARCHAR(150) DEFAULT NULL;

  SELECT u.email, p.full_name INTO v_email, v_full_name
  FROM users u
  LEFT JOIN user_profiles p ON p.user_id = u.id
  WHERE u.id = p_user_id AND u.deleted_at IS NULL AND u.status IN ('ACTIVE', 'PENDING')
  LIMIT 1;

  IF v_email IS NOT NULL THEN
    UPDATE password_reset_tokens
    SET used_at = UTC_TIMESTAMP(6)
    WHERE user_id = p_user_id AND used_at IS NULL;

    INSERT INTO password_reset_tokens (id, user_id, token_digest, expires_at)
    VALUES (p_token_id, p_user_id, p_token_digest,
            DATE_ADD(UTC_TIMESTAMP(6), INTERVAL p_ttl_minutes MINUTE));
  END IF;

  COMMIT;

  SELECT v_email AS email, v_full_name AS full_name;
END$$

-- ============================================================
-- sp_password_reset_consume
-- Đổi mật khẩu bằng token còn hạn và chưa dùng. Đồng thời mở khoá đăng nhập
-- (xoá bộ đếm sai mật khẩu) và vô hiệu mọi liên kết khác của tài khoản.
-- ============================================================
CREATE PROCEDURE sp_password_reset_consume(
  IN p_token_digest CHAR(64),
  IN p_password_hash TEXT
)
BEGIN
  DECLARE v_token_id CHAR(36) DEFAULT NULL;
  DECLARE v_user_id CHAR(36) DEFAULT NULL;
  DECLARE v_expires_at DATETIME(6) DEFAULT NULL;
  DECLARE v_used_at DATETIME(6) DEFAULT NULL;
  DECLARE v_user_ok INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể đặt lại mật khẩu do lỗi hệ thống.' AS error_message,
           NULL AS user_id;
  END;

  START TRANSACTION;

  SELECT id, user_id, expires_at, used_at
  INTO v_token_id, v_user_id, v_expires_at, v_used_at
  FROM password_reset_tokens
  WHERE token_digest = p_token_digest
  LIMIT 1
  FOR UPDATE;

  SELECT COUNT(*) INTO v_user_ok
  FROM users
  WHERE id = v_user_id AND deleted_at IS NULL AND status IN ('ACTIVE', 'PENDING');

  IF v_token_id IS NULL OR v_used_at IS NOT NULL OR v_user_ok = 0 THEN
    SET v_error_code = 'TOKEN_INVALID';
    SET v_error_message = 'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã được sử dụng.';
  ELSEIF v_expires_at <= UTC_TIMESTAMP(6) THEN
    SET v_error_code = 'TOKEN_EXPIRED';
    SET v_error_message = 'Liên kết đặt lại mật khẩu đã hết hạn. Hãy yêu cầu liên kết mới.';
  ELSE
    UPDATE users
    SET password_hash = p_password_hash,
        failed_login_count = 0,
        locked_until = NULL,
        row_version = row_version + 1
    WHERE id = v_user_id;

    UPDATE password_reset_tokens
    SET used_at = UTC_TIMESTAMP(6)
    WHERE user_id = v_user_id AND used_at IS NULL;

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id)
    VALUES (UUID(), v_user_id, 'PASSWORD_RESET', 'user', v_user_id);
  END IF;

  IF v_error_code IS NULL THEN
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN v_user_id ELSE NULL END AS user_id;
END$$

-- ============================================================
-- sp_auth_two_factor_get / sp_auth_two_factor_set
-- Khoá TOTP đã mã hoá (Fernet) của tài khoản. NULL = chưa bật xác thực 2 bước.
-- ============================================================
CREATE PROCEDURE sp_auth_two_factor_get(IN p_user_id CHAR(36))
BEGIN
  SELECT two_factor_secret_encrypted
  FROM users
  WHERE id = p_user_id AND deleted_at IS NULL
  LIMIT 1;
END$$

CREATE PROCEDURE sp_auth_two_factor_set(
  IN p_user_id CHAR(36),
  IN p_secret_encrypted TEXT
)
BEGIN
  DECLARE v_updated INT DEFAULT 0;

  UPDATE users
  SET two_factor_secret_encrypted = p_secret_encrypted,
      row_version = row_version + 1
  WHERE id = p_user_id AND deleted_at IS NULL;

  SET v_updated = ROW_COUNT();

  IF v_updated > 0 THEN
    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id)
    VALUES (UUID(), p_user_id,
            IF(p_secret_encrypted IS NULL, 'TWO_FACTOR_DISABLE', 'TWO_FACTOR_ENABLE'),
            'user', p_user_id);
  END IF;

  COMMIT;

  SELECT CASE WHEN v_updated = 0 THEN 'USER_NOT_FOUND' ELSE NULL END AS error_code,
         CASE WHEN v_updated = 0 THEN 'Không tìm thấy tài khoản.' ELSE NULL END AS error_message;
END$$

-- ============================================================
-- sp_file_save
-- Metadata cho tệp backend vừa ghi ra storage (báo cáo xuất, hoá đơn...).
-- ============================================================
CREATE PROCEDURE sp_file_save(
  IN p_file_id CHAR(36),
  IN p_owner_user_id CHAR(36),
  IN p_storage_key VARCHAR(512),
  IN p_original_name TEXT,
  IN p_content_type VARCHAR(120),
  IN p_size_bytes BIGINT,
  IN p_checksum_sha256 CHAR(64)
)
BEGIN
  INSERT INTO file_assets
    (id, owner_user_id, storage_key, original_name, content_type, size_bytes,
     visibility, checksum_sha256)
  VALUES
    (p_file_id, p_owner_user_id, p_storage_key, p_original_name, p_content_type,
     p_size_bytes, 'PRIVATE', p_checksum_sha256);
  COMMIT;
  SELECT p_file_id AS file_id;
END$$

-- ============================================================
-- Hàng đợi tác vụ (background_jobs)
-- Trạng thái: PENDING → RUNNING → SUCCESS | FAILED.
-- sp_job_claim chỉ chuyển PENDING → RUNNING một lần, nên một tác vụ không bao
-- giờ chạy hai lần dù có nhiều worker cùng nhận.
-- ============================================================
CREATE PROCEDURE sp_job_create(
  IN p_job_id CHAR(36),
  IN p_job_type VARCHAR(60),
  IN p_requested_by CHAR(36),
  IN p_parameters JSON
)
BEGIN
  INSERT INTO background_jobs (id, job_type, status, progress, requested_by, parameters)
  VALUES (p_job_id, p_job_type, 'PENDING', 0, p_requested_by,
          COALESCE(p_parameters, JSON_OBJECT()));
  COMMIT;
  SELECT p_job_id AS job_id;
END$$

CREATE PROCEDURE sp_job_claim(IN p_job_id CHAR(36))
BEGIN
  DECLARE v_claimed INT DEFAULT 0;

  UPDATE background_jobs
  SET status = 'RUNNING', started_at = UTC_TIMESTAMP(6), progress = 5
  WHERE id = p_job_id AND status = 'PENDING';

  SET v_claimed = ROW_COUNT();
  COMMIT;

  SELECT id, job_type, requested_by, parameters, v_claimed AS claimed
  FROM background_jobs
  WHERE id = p_job_id;
END$$

CREATE PROCEDURE sp_job_progress(IN p_job_id CHAR(36), IN p_progress SMALLINT)
BEGIN
  UPDATE background_jobs
  SET progress = LEAST(GREATEST(p_progress, 0), 99)
  WHERE id = p_job_id AND status = 'RUNNING';
  COMMIT;
END$$

CREATE PROCEDURE sp_job_finish(
  IN p_job_id CHAR(36),
  IN p_status VARCHAR(16),
  IN p_result_file_id CHAR(36),
  IN p_error_message TEXT
)
BEGIN
  UPDATE background_jobs
  SET status = p_status,
      progress = IF(p_status = 'SUCCESS', 100, progress),
      result_file_id = p_result_file_id,
      error_message = p_error_message,
      started_at = COALESCE(started_at, UTC_TIMESTAMP(6)),
      finished_at = UTC_TIMESTAMP(6)
  WHERE id = p_job_id AND status IN ('PENDING', 'RUNNING');
  COMMIT;
END$$

CREATE PROCEDURE sp_job_get(IN p_job_id CHAR(36))
BEGIN
  SELECT j.id, j.job_type, j.status, j.progress, j.requested_by, j.parameters,
         j.result_file_id, j.error_message, j.started_at, j.finished_at, j.created_at,
         f.original_name AS file_name, f.content_type AS file_content_type,
         f.size_bytes AS file_size
  FROM background_jobs j
  LEFT JOIN file_assets f ON f.id = j.result_file_id AND f.deleted_at IS NULL
  WHERE j.id = p_job_id;
END$$

CREATE PROCEDURE sp_job_list(
  IN p_requested_by CHAR(36),
  IN p_type_prefix VARCHAR(60),
  IN p_limit INT
)
BEGIN
  SELECT j.id, j.job_type, j.status, j.progress, j.requested_by, j.parameters,
         j.result_file_id, j.error_message, j.started_at, j.finished_at, j.created_at,
         f.original_name AS file_name, f.content_type AS file_content_type,
         f.size_bytes AS file_size
  FROM background_jobs j
  LEFT JOIN file_assets f ON f.id = j.result_file_id AND f.deleted_at IS NULL
  WHERE j.requested_by = p_requested_by
    AND (p_type_prefix IS NULL OR j.job_type LIKE CONCAT(p_type_prefix, '%'))
  ORDER BY j.created_at DESC
  LIMIT p_limit;
END$$

-- Tác vụ PENDING quá lâu (worker khởi động lại, Redis mất tin nhắn...) để chạy bù.
CREATE PROCEDURE sp_job_pending_list(IN p_created_before DATETIME(6), IN p_limit INT)
BEGIN
  SELECT id
  FROM background_jobs
  WHERE status = 'PENDING' AND created_at < p_created_before
  ORDER BY created_at
  LIMIT p_limit;
END$$

-- ============================================================
-- sp_audit_log_list
-- Nhật ký thao tác: ai làm gì, lúc nào, dữ liệu trước/sau. Lọc theo loại đối
-- tượng, id đối tượng, hành động, khoảng thời gian; tìm theo tên/email người làm.
-- ============================================================
CREATE PROCEDURE sp_audit_log_list(
  IN p_entity_type VARCHAR(80),
  IN p_entity_id CHAR(36),
  IN p_action VARCHAR(100),
  IN p_search VARCHAR(150),
  IN p_from DATETIME(6),
  IN p_to DATETIME(6),
  IN p_limit INT,
  IN p_offset INT
)
BEGIN
  DECLARE v_pattern VARCHAR(160) DEFAULT NULL;

  IF NULLIF(TRIM(p_search), '') IS NOT NULL THEN
    SET v_pattern = CONCAT('%', TRIM(p_search), '%');
  END IF;

  SELECT
    a.id,
    a.action,
    a.entity_type,
    a.entity_id,
    a.before_data,
    a.after_data,
    a.created_at,
    a.actor_user_id,
    u.email AS actor_email,
    u.role AS actor_role,
    p.full_name AS actor_name,
    COUNT(*) OVER () AS total_count
  FROM audit_logs a
  LEFT JOIN users u ON u.id = a.actor_user_id
  LEFT JOIN user_profiles p ON p.user_id = a.actor_user_id
  WHERE (p_entity_type IS NULL OR a.entity_type = p_entity_type)
    AND (p_entity_id IS NULL OR a.entity_id = p_entity_id)
    AND (p_action IS NULL OR a.action = p_action)
    AND (p_from IS NULL OR a.created_at >= p_from)
    AND (p_to IS NULL OR a.created_at < p_to)
    AND (v_pattern IS NULL
         OR p.full_name LIKE v_pattern
         OR u.email LIKE v_pattern
         OR a.action LIKE v_pattern)
  ORDER BY a.created_at DESC, a.id
  LIMIT p_limit OFFSET p_offset;
END$$

-- ============================================================
-- sp_invoice_issue
-- Lập hoá đơn cho một payment đã thu tiền (một payment một hoá đơn, gọi lại
-- trả hoá đơn cũ). Số hoá đơn HDyyyymm-nnnnn tăng dần trong tháng.
-- Trả kèm thông tin khách, giao dịch và nội dung để backend dựng file PDF.
-- ============================================================
CREATE PROCEDURE sp_invoice_issue(
  IN p_invoice_id CHAR(36),
  IN p_payment_id CHAR(36)
)
BEGIN
  DECLARE v_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_amount NUMERIC(14,2) DEFAULT 0;
  DECLARE v_currency CHAR(3) DEFAULT 'VND';
  DECLARE v_paid_at DATETIME(6) DEFAULT NULL;
  DECLARE v_member_id CHAR(36) DEFAULT NULL;
  DECLARE v_prefix VARCHAR(12) DEFAULT NULL;
  DECLARE v_seq INT DEFAULT 0;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  -- Hai yêu cầu cùng lúc lấy trùng số: backend gọi lại một lần.
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SELECT 'RETRY' AS error_code, 'Số hoá đơn bị trùng, thử lại.' AS error_message;
  END;

  START TRANSACTION;

  SELECT status, amount, currency, paid_at, member_id
  INTO v_status, v_amount, v_currency, v_paid_at, v_member_id
  FROM payments
  WHERE id = p_payment_id
  FOR UPDATE;

  IF v_status IS NULL THEN
    SET v_error_code = 'PAYMENT_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy giao dịch thanh toán.';
  ELSEIF v_status <> 'PAID' THEN
    SET v_error_code = 'PAYMENT_NOT_PAID';
    SET v_error_message = 'Chỉ xuất hoá đơn cho giao dịch đã thanh toán.';
  ELSEIF NOT EXISTS (SELECT 1 FROM invoices WHERE payment_id = p_payment_id) THEN
    SET v_prefix = CONCAT('HD', DATE_FORMAT(UTC_TIMESTAMP(6), '%Y%m'), '-');
    SELECT COUNT(*) + 1 INTO v_seq FROM invoices WHERE invoice_number LIKE CONCAT(v_prefix, '%');

    INSERT INTO invoices
      (id, invoice_number, member_id, payment_id, subtotal, currency, status, issued_at, paid_at)
    VALUES
      (p_invoice_id, CONCAT(v_prefix, LPAD(v_seq, 5, '0')), v_member_id, p_payment_id,
       v_amount, v_currency, 'PAID', UTC_TIMESTAMP(6), v_paid_at);
  END IF;

  IF v_error_code IS NULL THEN
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT
    v_error_code AS error_code,
    v_error_message AS error_message,
    d.*
  FROM (SELECT 1 AS one) AS x
  LEFT JOIN (
    SELECT
      i.invoice_number,
      i.issued_at,
      pym.id AS payment_id,
      pym.payment_number,
      pym.purpose,
      pym.amount,
      pym.currency,
      pym.method,
      pym.status AS payment_status,
      pym.paid_at,
      m.user_id AS member_user_id,
      m.member_code,
      m.full_name AS member_name,
      COALESCE(m.email, u.email) AS member_email,
      COALESCE(m.phone, u.phone) AS member_phone,
      b.name AS branch_name,
      b.address_line AS branch_address,
      (SELECT pl.name FROM membership_subscriptions s
       JOIN membership_plans pl ON pl.id = s.plan_id
       WHERE s.payment_id = pym.id LIMIT 1) AS plan_name,
      (SELECT pc.quantity FROM pt_credit_purchases pc
       WHERE pc.payment_id = pym.id LIMIT 1) AS pt_quantity,
      (SELECT pc.unit_price FROM pt_credit_purchases pc
       WHERE pc.payment_id = pym.id LIMIT 1) AS pt_unit_price
    FROM invoices i
    JOIN payments pym ON pym.id = i.payment_id
    LEFT JOIN members m ON m.id = pym.member_id
    LEFT JOIN users u ON u.id = m.user_id
    LEFT JOIN branches b ON b.id = m.home_branch_id
    WHERE i.payment_id = p_payment_id
  ) AS d ON v_error_code IS NULL;
END$$

-- ============================================================
-- sp_pt_booking_contact
-- Thông tin liên hệ của một buổi PT để gửi email (huỷ buổi...).
-- ============================================================
CREATE PROCEDURE sp_pt_booking_contact(IN p_booking_id CHAR(36))
BEGIN
  SELECT
    b.id,
    b.booking_number,
    b.start_at,
    b.end_at,
    b.status,
    b.cancellation_reason,
    b.cancelled_by_role,
    mu.email AS member_email,
    mp.full_name AS member_name,
    tu.email AS trainer_email,
    tp.full_name AS trainer_name
  FROM pt_bookings b
  JOIN members m ON m.id = b.member_id
  JOIN users mu ON mu.id = m.user_id
  LEFT JOIN user_profiles mp ON mp.user_id = mu.id
  JOIN trainer_profiles t ON t.id = b.trainer_id
  JOIN users tu ON tu.id = t.user_id
  LEFT JOIN user_profiles tp ON tp.user_id = tu.id
  WHERE b.id = p_booking_id
  LIMIT 1;
END$$

-- ============================================================
-- sp_admin_product_find_by_sku
-- Nhập sản phẩm từ Excel/CSV: SKU đã có thì cập nhật, chưa có thì tạo mới.
-- ============================================================
CREATE PROCEDURE sp_admin_product_find_by_sku(IN p_sku VARCHAR(60))
BEGIN
  SELECT p.id AS product_id, p.row_version
  FROM product_variants v
  JOIN products p ON p.id = v.product_id
  WHERE v.sku = p_sku AND v.deleted_at IS NULL AND p.deleted_at IS NULL
  LIMIT 1;
END$$

-- ============================================================
-- sp_health_ping
-- /health/ready gọi để biết MySQL còn trả lời; backend không tự viết SELECT.
-- ============================================================
CREATE PROCEDURE sp_health_ping()
BEGIN
  SELECT 1 AS alive;
END$$

DELIMITER ;
