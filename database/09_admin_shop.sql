-- GymFitness — khu quản trị, phần 2 (ADR-017)
--
--   * Báo cáo số lượng hội viên và mức tăng trưởng theo kỳ.
--   * Quản lý thanh toán: danh sách, xác nhận thủ công, huỷ giao dịch đang chờ.
--   * Cửa hàng: danh mục sản phẩm, giá và tồn kho; trang /products đọc từ database.
--
-- Chạy lại nhiều lần an toàn. Chạy sau 08_admin.sql:
--   python scripts/apply_sql.py database/09_admin_shop.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS sp_admin_member_base;
DROP PROCEDURE IF EXISTS sp_admin_member_growth;
DROP PROCEDURE IF EXISTS sp_admin_payment_list;
DROP PROCEDURE IF EXISTS sp_admin_payment_confirm_log;
DROP PROCEDURE IF EXISTS sp_admin_payment_void;
DROP PROCEDURE IF EXISTS sp_product_list_public;
DROP PROCEDURE IF EXISTS sp_admin_product_list;
DROP PROCEDURE IF EXISTS sp_admin_product_save;
DROP PROCEDURE IF EXISTS sp_admin_product_delete;

DELIMITER $$

-- ============================================================
-- sp_admin_member_base
-- Số hội viên (tài khoản USER chưa xoá) đã đăng ký trước p_before:
-- điểm xuất phát để cộng dồn tổng hội viên theo từng kỳ.
-- ============================================================
CREATE PROCEDURE sp_admin_member_base(IN p_before DATETIME(6))
BEGIN
  SELECT COUNT(*) AS members
  FROM users
  WHERE role = 'USER' AND deleted_at IS NULL AND created_at < p_before;
END$$

-- ============================================================
-- sp_admin_member_growth
-- Hội viên mới trong [p_from, p_to), gom theo kỳ của giờ phòng tập.
-- period_start cùng quy ước với sp_admin_revenue.
-- ============================================================
CREATE PROCEDURE sp_admin_member_growth(
  IN p_from DATETIME(6),
  IN p_to DATETIME(6),
  IN p_period VARCHAR(8),
  IN p_offset_minutes INT
)
BEGIN
  SELECT
    CASE p_period
      WHEN 'WEEK' THEN DATE_FORMAT(DATE_SUB(DATE(l.local_created), INTERVAL WEEKDAY(l.local_created) DAY), '%Y-%m-%d')
      WHEN 'MONTH' THEN DATE_FORMAT(l.local_created, '%Y-%m-01')
      WHEN 'QUARTER' THEN CONCAT(YEAR(l.local_created), '-',
                                 LPAD((QUARTER(l.local_created) - 1) * 3 + 1, 2, '0'), '-01')
      ELSE CONCAT(YEAR(l.local_created), '-01-01')
    END AS period_start,
    COUNT(*) AS new_members
  FROM (
    SELECT DATE_ADD(u.created_at, INTERVAL p_offset_minutes MINUTE) AS local_created
    FROM users u
    WHERE u.role = 'USER'
      AND u.deleted_at IS NULL
      AND u.created_at >= p_from
      AND u.created_at < p_to
  ) AS l
  GROUP BY period_start
  ORDER BY period_start;
END$$

-- ============================================================
-- sp_admin_payment_list
-- Giao dịch theo trạng thái/loại/khoảng ngày tạo, tìm theo mã chuyển khoản,
-- mã tham chiếu ngân hàng hoặc hội viên. bank_note là ghi chú mới nhất của
-- webhook (vd. chuyển thiếu tiền) để đối soát thủ công.
-- paid_total: tổng tiền đã thu của toàn bộ dòng khớp bộ lọc (trước LIMIT).
-- p_sort: created_at, paid_at, amount; tiền tố '-' = giảm dần. Mặc định: mới tạo trước.
-- ============================================================
CREATE PROCEDURE sp_admin_payment_list(
  IN p_payment_id CHAR(36),
  IN p_search VARCHAR(150),
  IN p_status VARCHAR(16),
  IN p_purpose VARCHAR(24),
  IN p_from DATETIME(6),
  IN p_to DATETIME(6),
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
    pym.id,
    pym.payment_number,
    pym.purpose,
    pym.amount,
    pym.currency,
    pym.method,
    pym.status,
    pym.external_reference,
    pym.failure_reason,
    pym.created_at,
    pym.paid_at,
    pym.qr_expires_at,
    m.id AS member_id,
    m.member_code,
    m.full_name AS member_name,
    m.email AS member_email,
    m.phone AS member_phone,
    (SELECT pl.name
     FROM membership_subscriptions s
     JOIN membership_plans pl ON pl.id = s.plan_id
     WHERE s.payment_id = pym.id LIMIT 1) AS plan_name,
    (SELECT pc.quantity FROM pt_credit_purchases pc
     WHERE pc.payment_id = pym.id LIMIT 1) AS pt_quantity,
    (SELECT e.error_message FROM payment_events e
     WHERE e.payment_id = pym.id AND e.error_message IS NOT NULL
     ORDER BY e.created_at DESC LIMIT 1) AS bank_note,
    COUNT(*) OVER () AS total_count,
    SUM(CASE WHEN pym.status = 'PAID' THEN pym.amount ELSE 0 END) OVER () AS paid_total,
    CASE p_sort
      WHEN 'amount' THEN ROW_NUMBER() OVER (ORDER BY pym.amount, pym.created_at DESC, pym.id)
      WHEN '-amount' THEN ROW_NUMBER() OVER (ORDER BY pym.amount DESC, pym.created_at DESC, pym.id)
      WHEN 'paid_at' THEN ROW_NUMBER() OVER (ORDER BY pym.paid_at, pym.id)
      WHEN '-paid_at' THEN ROW_NUMBER() OVER (ORDER BY pym.paid_at DESC, pym.id)
      WHEN 'created_at' THEN ROW_NUMBER() OVER (ORDER BY pym.created_at, pym.id)
      ELSE ROW_NUMBER() OVER (ORDER BY pym.created_at DESC, pym.id)
    END AS sort_rank
  FROM payments pym
  LEFT JOIN members m ON m.id = pym.member_id
  WHERE (p_payment_id IS NULL OR pym.id = p_payment_id)
    AND (p_status IS NULL OR pym.status = p_status)
    AND (p_purpose IS NULL OR pym.purpose = p_purpose)
    AND (p_from IS NULL OR pym.created_at >= p_from)
    AND (p_to IS NULL OR pym.created_at < p_to)
    AND (v_pattern IS NULL
         OR pym.payment_number LIKE v_pattern
         OR pym.external_reference LIKE v_pattern
         OR m.full_name LIKE v_pattern
         OR m.member_code LIKE v_pattern
         OR m.email LIKE v_pattern
         OR m.phone LIKE v_pattern)
  ) AS t
  ORDER BY t.sort_rank
  LIMIT p_limit OFFSET p_offset;
END$$

-- ============================================================
-- sp_admin_payment_confirm_log
-- Gọi ngay sau khi quyền lợi đã được kích hoạt bằng sp_subscription_mark_paid
-- hoặc sp_pt_credit_purchase_mark_paid: ghi cách thu tiền thực tế và audit log
-- cho thao tác xác nhận thủ công của admin (ADR-004).
-- ============================================================
CREATE PROCEDURE sp_admin_payment_confirm_log(
  IN p_payment_id CHAR(36),
  IN p_method VARCHAR(20),
  IN p_actor_id CHAR(36)
)
BEGIN
  UPDATE payments
  SET method = COALESCE(p_method, method)
  WHERE id = p_payment_id;

  INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, after_data)
  SELECT UUID(), p_actor_id, 'PAYMENT_CONFIRM', 'payment', pym.id,
         JSON_OBJECT('payment_number', pym.payment_number, 'amount', pym.amount,
                     'method', pym.method, 'status', pym.status)
  FROM payments pym
  WHERE pym.id = p_payment_id;

  COMMIT;

  SELECT NULL AS error_code, NULL AS error_message;
END$$

-- ============================================================
-- sp_admin_payment_void
-- Huỷ một giao dịch đang PENDING: payment -> VOID, gói chờ kích hoạt ->
-- CANCELLED, lượt PT chờ cộng -> VOID. Giao dịch đã thu tiền không huỷ được.
-- ============================================================
CREATE PROCEDURE sp_admin_payment_void(
  IN p_payment_id CHAR(36),
  IN p_reason VARCHAR(255),
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_status VARCHAR(16) DEFAULT NULL;
  DECLARE v_number VARCHAR(40) DEFAULT NULL;
  DECLARE v_subscription_id CHAR(36) DEFAULT NULL;
  DECLARE v_reason VARCHAR(255) DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể huỷ giao dịch do lỗi hệ thống.' AS error_message;
  END;

  SET v_reason = COALESCE(NULLIF(TRIM(p_reason), ''), 'Quản trị viên huỷ giao dịch');

  START TRANSACTION;

  SELECT status, payment_number INTO v_status, v_number
  FROM payments
  WHERE id = p_payment_id
  FOR UPDATE;

  IF v_status IS NULL THEN
    SET v_error_code = 'PAYMENT_NOT_FOUND';
    SET v_error_message = 'Không tìm thấy giao dịch thanh toán.';
  ELSEIF v_status <> 'PENDING' THEN
    SET v_error_code = 'PAYMENT_NOT_PENDING';
    SET v_error_message = 'Chỉ huỷ được giao dịch đang chờ thanh toán.';
  END IF;

  IF v_error_code IS NULL THEN
    UPDATE payments
    SET status = 'VOID', failure_reason = v_reason, row_version = row_version + 1
    WHERE id = p_payment_id;

    SELECT MAX(id) INTO v_subscription_id
    FROM membership_subscriptions
    WHERE payment_id = p_payment_id AND status = 'PENDING';

    IF v_subscription_id IS NOT NULL THEN
      UPDATE membership_subscriptions
      SET status = 'CANCELLED',
          cancelled_at = UTC_TIMESTAMP(6),
          cancellation_reason = v_reason,
          row_version = row_version + 1
      WHERE id = v_subscription_id;

      INSERT INTO subscription_status_history
        (id, subscription_id, from_status, to_status, reason, changed_by)
      VALUES
        (UUID(), v_subscription_id, 'PENDING', 'CANCELLED', v_reason, p_actor_id);
    END IF;

    UPDATE pt_credit_purchases
    SET status = 'VOID'
    WHERE payment_id = p_payment_id AND status = 'PENDING';

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
    VALUES (UUID(), p_actor_id, 'PAYMENT_VOID', 'payment', p_payment_id,
            JSON_OBJECT('status', 'PENDING', 'payment_number', v_number),
            JSON_OBJECT('status', 'VOID', 'reason', v_reason));

    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code, v_error_message AS error_message;
END$$

-- ============================================================
-- sp_product_list_public
-- Sản phẩm đang bán cho trang /products. Mỗi sản phẩm có một biến thể mặc
-- định giữ SKU, giá và tồn kho; badge/art nằm trong attributes của biến thể.
-- ============================================================
CREATE PROCEDURE sp_product_list_public()
BEGIN
  SELECT
    p.id,
    p.slug,
    p.name,
    p.description,
    c.name AS category_name,
    c.activity_type,
    v.sku,
    v.price,
    v.currency,
    v.stock_quantity - v.reserved_quantity AS available_quantity,
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(v.attributes, '$.badge')), 'null') AS badge,
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(v.attributes, '$.art')), 'null') AS art
  FROM products p
  JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL AND v.is_active = TRUE
  LEFT JOIN product_categories c ON c.id = p.category_id
  WHERE p.deleted_at IS NULL AND p.status = 'ACTIVE'
  ORDER BY c.activity_type, p.created_at, p.name;
END$$

-- ============================================================
-- sp_admin_product_list
-- Mọi sản phẩm chưa xoá (kể cả đang ẩn), tìm theo tên/SKU, lọc theo nhóm
-- Gym/Yoga và trạng thái. p_product_id để đọc lại đúng một sản phẩm.
-- p_sort: name, price, stock_quantity, created_at; tiền tố '-' = giảm dần.
-- ============================================================
CREATE PROCEDURE sp_admin_product_list(
  IN p_product_id CHAR(36),
  IN p_search VARCHAR(150),
  IN p_activity_type VARCHAR(12),
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
    p.id,
    p.slug,
    p.name,
    p.description,
    p.status,
    p.created_at,
    p.row_version,
    c.name AS category_name,
    c.activity_type,
    v.id AS variant_id,
    v.sku,
    v.price,
    v.currency,
    v.stock_quantity,
    v.reserved_quantity,
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(v.attributes, '$.badge')), 'null') AS badge,
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(v.attributes, '$.art')), 'null') AS art,
    COUNT(*) OVER () AS total_count,
    CASE p_sort
      WHEN 'name' THEN ROW_NUMBER() OVER (ORDER BY p.name, p.id)
      WHEN '-name' THEN ROW_NUMBER() OVER (ORDER BY p.name DESC, p.id)
      WHEN 'price' THEN ROW_NUMBER() OVER (ORDER BY v.price, p.id)
      WHEN '-price' THEN ROW_NUMBER() OVER (ORDER BY v.price DESC, p.id)
      WHEN 'stock_quantity' THEN ROW_NUMBER() OVER (ORDER BY v.stock_quantity, p.id)
      WHEN '-stock_quantity' THEN ROW_NUMBER() OVER (ORDER BY v.stock_quantity DESC, p.id)
      WHEN 'created_at' THEN ROW_NUMBER() OVER (ORDER BY p.created_at, p.id)
      ELSE ROW_NUMBER() OVER (ORDER BY p.created_at DESC, p.name, p.id)
    END AS sort_rank
  FROM products p
  JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL
  LEFT JOIN product_categories c ON c.id = p.category_id
  WHERE p.deleted_at IS NULL
    AND (p_product_id IS NULL OR p.id = p_product_id)
    AND (p_activity_type IS NULL OR c.activity_type = p_activity_type)
    AND (p_status IS NULL OR p.status = p_status)
    AND (v_pattern IS NULL
         OR p.name LIKE v_pattern
         OR v.sku LIKE v_pattern
         OR c.name LIKE v_pattern)
  ) AS t
  ORDER BY t.sort_rank
  LIMIT p_limit OFFSET p_offset;
END$$

-- ============================================================
-- sp_admin_product_save
-- Tạo mới (p_is_new = TRUE) hoặc cập nhật sản phẩm cùng biến thể mặc định.
-- Danh mục tìm theo (tên, nhóm) và tự tạo nếu chưa có. Mọi thay đổi tồn kho
-- được ghi vào inventory_movements; tồn kho không được thấp hơn số đang giữ.
-- p_expected_version: row_version của sản phẩm client đang xem (NULL = bỏ qua);
-- lệch với bản hiện tại → VERSION_CONFLICT để không ghi đè thay đổi của người khác.
-- ============================================================
CREATE PROCEDURE sp_admin_product_save(
  IN p_product_id CHAR(36),
  IN p_variant_id CHAR(36),
  IN p_is_new BOOLEAN,
  IN p_slug VARCHAR(180),
  IN p_name VARCHAR(180),
  IN p_sku VARCHAR(60),
  IN p_category_name VARCHAR(100),
  IN p_activity_type VARCHAR(12),
  IN p_description TEXT,
  IN p_price NUMERIC(14,2),
  IN p_stock INT,
  IN p_status VARCHAR(16),
  IN p_badge VARCHAR(40),
  IN p_art VARCHAR(40),
  IN p_expected_version INT,
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_version INT DEFAULT NULL;
  DECLARE v_category_id CHAR(36) DEFAULT NULL;
  DECLARE v_variant_id CHAR(36) DEFAULT NULL;
  DECLARE v_stock INT DEFAULT 0;
  DECLARE v_reserved INT DEFAULT 0;
  DECLARE v_before JSON DEFAULT NULL;
  DECLARE v_attributes JSON DEFAULT NULL;
  DECLARE v_error_code VARCHAR(40) DEFAULT NULL;
  DECLARE v_error_message VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SELECT 'SKU_EXISTS' AS error_code, 'Mã SKU này đã được dùng cho sản phẩm khác.' AS error_message,
           NULL AS product_id;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INVALID_PRODUCT' AS error_code, 'Thông tin sản phẩm không hợp lệ.' AS error_message,
           NULL AS product_id;
  END;

  SET v_attributes = JSON_OBJECT('badge', NULLIF(TRIM(p_badge), ''), 'art', NULLIF(TRIM(p_art), ''));

  START TRANSACTION;

  SELECT MAX(id) INTO v_category_id
  FROM product_categories
  WHERE name = TRIM(p_category_name) AND activity_type <=> p_activity_type;

  IF v_category_id IS NULL THEN
    SET v_category_id = UUID();
    INSERT INTO product_categories (id, code, name, activity_type)
    VALUES (v_category_id,
            CONCAT(COALESCE(p_activity_type, 'ALL'), '_', UPPER(LEFT(REPLACE(v_category_id, '-', ''), 10))),
            TRIM(p_category_name), p_activity_type);
  END IF;

  IF p_is_new THEN
    INSERT INTO products (id, category_id, slug, name, description, status)
    VALUES (p_product_id, v_category_id, p_slug, p_name, NULLIF(TRIM(p_description), ''), p_status);

    INSERT INTO product_variants (id, product_id, sku, attributes, price, stock_quantity, is_active)
    VALUES (p_variant_id, p_product_id, p_sku, v_attributes, p_price, p_stock, TRUE);

    IF p_stock > 0 THEN
      INSERT INTO inventory_movements
        (id, variant_id, movement_type, quantity_delta, stock_balance, reserved_balance,
         reason, idempotency_key, created_by)
      VALUES
        (UUID(), p_variant_id, 'IMPORT', p_stock, p_stock, 0,
         'Nhập kho khi tạo sản phẩm', UUID(), p_actor_id);
    END IF;
  ELSE
    SELECT v.id, v.stock_quantity, v.reserved_quantity, p.row_version,
           JSON_OBJECT('name', p.name, 'sku', v.sku, 'price', v.price,
                       'stock', v.stock_quantity, 'status', p.status,
                       'row_version', p.row_version)
    INTO v_variant_id, v_stock, v_reserved, v_version, v_before
    FROM products p
    JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL
    WHERE p.id = p_product_id AND p.deleted_at IS NULL
    ORDER BY v.created_at
    LIMIT 1
    FOR UPDATE;

    IF v_variant_id IS NULL THEN
      SET v_error_code = 'PRODUCT_NOT_FOUND';
      SET v_error_message = 'Không tìm thấy sản phẩm.';
    ELSEIF p_expected_version IS NOT NULL AND p_expected_version <> v_version THEN
      SET v_error_code = 'VERSION_CONFLICT';
      SET v_error_message = 'Sản phẩm vừa được người khác sửa. Tải lại để xem bản mới nhất.';
    ELSEIF p_stock < v_reserved THEN
      SET v_error_code = 'STOCK_BELOW_RESERVED';
      SET v_error_message = CONCAT('Tồn kho không được thấp hơn ', v_reserved,
                                   ' sản phẩm đang giữ cho đơn hàng.');
    ELSE
      UPDATE products
      SET category_id = v_category_id,
          name = p_name,
          description = NULLIF(TRIM(p_description), ''),
          status = p_status,
          row_version = row_version + 1
      WHERE id = p_product_id;

      UPDATE product_variants
      SET sku = p_sku,
          attributes = v_attributes,
          price = p_price,
          compare_at_price = NULL,
          stock_quantity = p_stock,
          row_version = row_version + 1
      WHERE id = v_variant_id;

      IF p_stock <> v_stock THEN
        INSERT INTO inventory_movements
          (id, variant_id, movement_type, quantity_delta, stock_balance, reserved_balance,
           reason, idempotency_key, created_by)
        VALUES
          (UUID(), v_variant_id, 'ADJUST', p_stock - v_stock, p_stock, v_reserved,
           'Quản trị viên điều chỉnh tồn kho', UUID(), p_actor_id);
      END IF;
    END IF;
  END IF;

  IF v_error_code IS NULL THEN
    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
    VALUES (UUID(), p_actor_id, IF(p_is_new, 'PRODUCT_CREATE', 'PRODUCT_UPDATE'), 'product',
            p_product_id, v_before,
            JSON_OBJECT('name', p_name, 'sku', p_sku, 'price', p_price,
                        'stock', p_stock, 'status', p_status));
    COMMIT;
  ELSE
    ROLLBACK;
  END IF;

  SELECT v_error_code AS error_code,
         v_error_message AS error_message,
         CASE WHEN v_error_code IS NULL THEN p_product_id ELSE NULL END AS product_id;
END$$

-- ============================================================
-- sp_admin_product_delete
-- Xoá mềm: ẩn khỏi cửa hàng, giải phóng SKU. Đơn hàng cũ giữ snapshot riêng
-- (ADR-009) nên không bị ảnh hưởng.
-- ============================================================
CREATE PROCEDURE sp_admin_product_delete(
  IN p_product_id CHAR(36),
  IN p_actor_id CHAR(36)
)
BEGIN
  DECLARE v_updated INT DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SELECT 'INTERNAL_ERROR' AS error_code,
           'Không thể xoá sản phẩm do lỗi hệ thống.' AS error_message;
  END;

  START TRANSACTION;

  UPDATE products
  SET status = 'INACTIVE', deleted_at = UTC_TIMESTAMP(6), row_version = row_version + 1
  WHERE id = p_product_id AND deleted_at IS NULL;

  SET v_updated = ROW_COUNT();

  IF v_updated > 0 THEN
    UPDATE product_variants
    SET sku = CONCAT('DEL-', LEFT(id, 8), '-', LEFT(sku, 46)),
        is_active = FALSE,
        deleted_at = UTC_TIMESTAMP(6),
        row_version = row_version + 1
    WHERE product_id = p_product_id AND deleted_at IS NULL;

    INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id)
    VALUES (UUID(), p_actor_id, 'PRODUCT_DELETE', 'product', p_product_id);
  END IF;

  COMMIT;

  SELECT CASE WHEN v_updated = 0 THEN 'PRODUCT_NOT_FOUND' ELSE NULL END AS error_code,
         CASE WHEN v_updated = 0 THEN 'Không tìm thấy sản phẩm.' ELSE NULL END AS error_message;
END$$

DELIMITER ;
