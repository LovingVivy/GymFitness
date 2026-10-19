-- GymFitness seed data — chi nhánh và gói tập
-- Chạy sau 01_tables.sql. Idempotent: chạy lại nhiều lần không tạo bản ghi trùng.
--
--   mysql -u root -p < database/04_seed.sql
--   python scripts/apply_sql.py database/04_seed.sql

USE gymfitness;

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ============================================================
-- Chi nhánh mặc định
-- ============================================================
INSERT INTO branches (id, code, name, address_line, phone, timezone, is_active)
SELECT '00000000-0000-0000-0000-000000000001',
       'IRONIX-Q1',
       'IRONIX Fitness Quận 1',
       '123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh',
       '028 3822 1234',
       'Asia/Ho_Chi_Minh',
       TRUE
WHERE NOT EXISTS (SELECT 1 FROM branches WHERE code = 'IRONIX-Q1');

-- ============================================================
-- Gói hội viên: Gym và Yoga, theo tháng hoặc theo năm.
-- ADR-003: gói tháng/năm lưu duration_months để giữ đúng lịch tháng,
-- không quy đổi thành số ngày cố định. Chỉ một trong hai trường có giá trị.
-- ============================================================
INSERT INTO membership_plans
  (id, code, name, activity_type, description, duration_months, duration_days,
   price, currency, max_visits, freeze_days_allowed, is_active)
SELECT '10000000-0000-0000-0000-000000000001',
       'GYM_MONTHLY',
       'Gym theo tháng',
       'GYM',
       'Tập không giới hạn khu vực Gym, gia hạn linh hoạt mỗi tháng.',
       1, NULL, 500000.00, 'VND', NULL, 7, TRUE
WHERE NOT EXISTS (SELECT 1 FROM membership_plans WHERE code = 'GYM_MONTHLY');

INSERT INTO membership_plans
  (id, code, name, activity_type, description, duration_months, duration_days,
   price, currency, max_visits, freeze_days_allowed, is_active)
SELECT '10000000-0000-0000-0000-000000000002',
       'GYM_YEARLY',
       'Gym theo năm',
       'GYM',
       'Tập không giới hạn khu vực Gym trong 12 tháng, tiết kiệm 30%.',
       12, NULL, 4200000.00, 'VND', NULL, 30, TRUE
WHERE NOT EXISTS (SELECT 1 FROM membership_plans WHERE code = 'GYM_YEARLY');

INSERT INTO membership_plans
  (id, code, name, activity_type, description, duration_months, duration_days,
   price, currency, max_visits, freeze_days_allowed, is_active)
SELECT '10000000-0000-0000-0000-000000000003',
       'YOGA_MONTHLY',
       'Yoga theo tháng',
       'YOGA',
       'Lịch Yoga độc lập theo cấp độ, gia hạn linh hoạt mỗi tháng.',
       1, NULL, 350000.00, 'VND', NULL, 7, TRUE
WHERE NOT EXISTS (SELECT 1 FROM membership_plans WHERE code = 'YOGA_MONTHLY');

INSERT INTO membership_plans
  (id, code, name, activity_type, description, duration_months, duration_days,
   price, currency, max_visits, freeze_days_allowed, is_active)
SELECT '10000000-0000-0000-0000-000000000004',
       'YOGA_YEARLY',
       'Yoga theo năm',
       'YOGA',
       'Lịch Yoga độc lập trong 12 tháng, tiết kiệm 30%.',
       12, NULL, 2940000.00, 'VND', NULL, 30, TRUE
WHERE NOT EXISTS (SELECT 1 FROM membership_plans WHERE code = 'YOGA_YEARLY');

-- ============================================================
-- Tài khoản huấn luyện viên (role = PT)
--
-- Đăng nhập demo:
--   pt.gym@ironix.vn  / pt12345678   (Trần Hoàng Nam — Gym)
--   pt.yoga@ironix.vn / pt12345678   (Lê Thu Hà — Yoga)
--
-- password_hash là PBKDF2-HMAC-SHA256 (600.000 vòng) do backend sinh ra,
-- không phải mật khẩu plaintext.
-- ============================================================
INSERT INTO users (id, email, phone, password_hash, role, status)
SELECT '20000000-0000-0000-0000-000000000001',
       'pt.gym@ironix.vn',
       '0938111222',
       'pbkdf2_sha256$600000$xtXzUcgeJUoV-IoSbu4mdQ==$rKU2JaU4Kug4kn53OP1JvkwHPfMV1l2WJt8eEYdEVO8=',
       'PT',
       'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'pt.gym@ironix.vn');

INSERT INTO users (id, email, phone, password_hash, role, status)
SELECT '20000000-0000-0000-0000-000000000002',
       'pt.yoga@ironix.vn',
       '0938333444',
       'pbkdf2_sha256$600000$xtXzUcgeJUoV-IoSbu4mdQ==$rKU2JaU4Kug4kn53OP1JvkwHPfMV1l2WJt8eEYdEVO8=',
       'PT',
       'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'pt.yoga@ironix.vn');

INSERT INTO user_profiles (user_id, full_name, gender, experience_level)
SELECT '20000000-0000-0000-0000-000000000001', 'Trần Hoàng Nam', 'MALE', 'ADVANCED'
WHERE NOT EXISTS (
  SELECT 1 FROM user_profiles WHERE user_id = '20000000-0000-0000-0000-000000000001'
);

INSERT INTO user_profiles (user_id, full_name, gender, experience_level)
SELECT '20000000-0000-0000-0000-000000000002', 'Lê Thu Hà', 'FEMALE', 'ADVANCED'
WHERE NOT EXISTS (
  SELECT 1 FROM user_profiles WHERE user_id = '20000000-0000-0000-0000-000000000002'
);

INSERT INTO trainer_profiles
  (id, user_id, employee_code, branch_id, bio, certifications, hourly_rate, status)
SELECT '30000000-0000-0000-0000-000000000001',
       '20000000-0000-0000-0000-000000000001',
       'PT000001',
       '00000000-0000-0000-0000-000000000001',
       'HLV sức mạnh và tăng cơ, 8 năm kinh nghiệm huấn luyện 1:1.',
       'NASM-CPT, CSCS',
       200000.00,
       'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM trainer_profiles WHERE employee_code = 'PT000001');

INSERT INTO trainer_profiles
  (id, user_id, employee_code, branch_id, bio, certifications, hourly_rate, status)
SELECT '30000000-0000-0000-0000-000000000002',
       '20000000-0000-0000-0000-000000000002',
       'PT000002',
       '00000000-0000-0000-0000-000000000001',
       'HLV Yoga và phục hồi, chuyên sâu về hơi thở và độ linh hoạt.',
       'RYT-500, Yoga Alliance',
       180000.00,
       'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM trainer_profiles WHERE employee_code = 'PT000002');

INSERT INTO trainer_specialties (trainer_id, specialty)
SELECT '30000000-0000-0000-0000-000000000001', 'GYM'
WHERE NOT EXISTS (
  SELECT 1 FROM trainer_specialties
  WHERE trainer_id = '30000000-0000-0000-0000-000000000001' AND specialty = 'GYM'
);

INSERT INTO trainer_specialties (trainer_id, specialty)
SELECT '30000000-0000-0000-0000-000000000001', 'MUSCLE_GAIN'
WHERE NOT EXISTS (
  SELECT 1 FROM trainer_specialties
  WHERE trainer_id = '30000000-0000-0000-0000-000000000001' AND specialty = 'MUSCLE_GAIN'
);

INSERT INTO trainer_specialties (trainer_id, specialty)
SELECT '30000000-0000-0000-0000-000000000002', 'YOGA'
WHERE NOT EXISTS (
  SELECT 1 FROM trainer_specialties
  WHERE trainer_id = '30000000-0000-0000-0000-000000000002' AND specialty = 'YOGA'
);

INSERT INTO trainer_specialties (trainer_id, specialty)
SELECT '30000000-0000-0000-0000-000000000002', 'FLEXIBILITY'
WHERE NOT EXISTS (
  SELECT 1 FROM trainer_specialties
  WHERE trainer_id = '30000000-0000-0000-0000-000000000002' AND specialty = 'FLEXIBILITY'
);

-- ============================================================
-- Cửa hàng: danh mục và sản phẩm mẫu cho trang /products.
-- Mỗi sản phẩm có một biến thể mặc định giữ SKU, giá và tồn kho;
-- attributes.art là tên hình minh hoạ ở frontend, attributes.badge là nhãn nổi bật.
-- INSERT IGNORE theo khoá chính nên chạy lại không tạo trùng và không ghi đè
-- thay đổi của quản trị viên.
-- ============================================================
INSERT IGNORE INTO product_categories (id, code, name, activity_type) VALUES
  ('20000000-0000-0000-0000-000000000001', 'GYM_ACCESSORY', 'Phụ kiện', 'GYM'),
  ('20000000-0000-0000-0000-000000000002', 'GYM_APPAREL', 'Trang phục', 'GYM'),
  ('20000000-0000-0000-0000-000000000003', 'GYM_BAG', 'Túi tập', 'GYM'),
  ('20000000-0000-0000-0000-000000000004', 'GYM_NUTRITION', 'Dinh dưỡng', 'GYM'),
  ('20000000-0000-0000-0000-000000000005', 'YOGA_EQUIPMENT', 'Dụng cụ', 'YOGA'),
  ('20000000-0000-0000-0000-000000000006', 'YOGA_APPAREL', 'Trang phục', 'YOGA'),
  ('20000000-0000-0000-0000-000000000007', 'YOGA_BAG', 'Túi tập', 'YOGA');

INSERT IGNORE INTO products (id, category_id, slug, name, description, status) VALUES
  ('21000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'gang-tay-grip-pro', 'Găng tay Grip Pro', 'Da microfiber · Đệm gel chống trượt', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 'ao-training-dry-fit', 'Áo Training Dry-Fit', 'Thoáng khí · Co giãn 4 chiều', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000002', 'quan-short-flex-7', 'Quần short Flex 7"', 'Lớp lót kép · Túi khóa kéo', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000004', '20000000-0000-0000-0000-000000000003', 'tui-mini-locker', 'Túi mini Locker', 'Ngăn giày riêng · Chống thấm', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000005', '20000000-0000-0000-0000-000000000004', 'whey-protein-isolate', 'Whey Protein Isolate', '25g protein · Vị chocolate', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000006', '20000000-0000-0000-0000-000000000001', 'binh-lac-core-700ml', 'Bình lắc Core 700ml', 'BPA free · Lưới chống vón', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000007', '20000000-0000-0000-0000-000000000004', 'thanh-protein-crunch', 'Thanh Protein Crunch', '20g protein · Ít đường', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000008', '20000000-0000-0000-0000-000000000005', 'tham-yoga-align-5mm', 'Thảm Yoga Align 5mm', 'Cao su tự nhiên · Bám chắc', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000009', '20000000-0000-0000-0000-000000000005', 'gach-tap-balance', 'Gạch tập Balance', 'EVA mật độ cao · Bo cạnh mềm', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000010', '20000000-0000-0000-0000-000000000005', 'day-ho-tro-flow', 'Dây hỗ trợ Flow', 'Khóa kim loại · Dài 2.4m', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000011', '20000000-0000-0000-0000-000000000006', 'quan-legging-motion', 'Quần Legging Motion', 'Cạp cao · Không lộ đường may', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000012', '20000000-0000-0000-0000-000000000006', 'ao-bra-calm-support', 'Áo Bra Calm Support', 'Nâng đỡ vừa · Vải mát', 'ACTIVE'),
  ('21000000-0000-0000-0000-000000000013', '20000000-0000-0000-0000-000000000007', 'tui-tham-yoga-sling', 'Túi thảm Yoga Sling', 'Đeo chéo · Vải canvas bền', 'ACTIVE');

INSERT IGNORE INTO product_variants (id, product_id, sku, attributes, price, stock_quantity) VALUES
  ('22000000-0000-0000-0000-000000000001', '21000000-0000-0000-0000-000000000001', 'GYM-GLOVES-01', JSON_OBJECT('art', 'gloves', 'badge', 'Bán chạy'), 289000.00, 50),
  ('22000000-0000-0000-0000-000000000002', '21000000-0000-0000-0000-000000000002', 'GYM-SHIRT-01', JSON_OBJECT('art', 'shirt', 'badge', 'Mới'), 359000.00, 50),
  ('22000000-0000-0000-0000-000000000003', '21000000-0000-0000-0000-000000000003', 'GYM-SHORTS-01', JSON_OBJECT('art', 'shorts'), 329000.00, 50),
  ('22000000-0000-0000-0000-000000000004', '21000000-0000-0000-0000-000000000004', 'GYM-BAG-01', JSON_OBJECT('art', 'bag'), 449000.00, 50),
  ('22000000-0000-0000-0000-000000000005', '21000000-0000-0000-0000-000000000005', 'GYM-WHEY-01', JSON_OBJECT('art', 'whey', 'badge', 'Top 1'), 1290000.00, 50),
  ('22000000-0000-0000-0000-000000000006', '21000000-0000-0000-0000-000000000006', 'GYM-SHAKER-01', JSON_OBJECT('art', 'shaker'), 169000.00, 50),
  ('22000000-0000-0000-0000-000000000007', '21000000-0000-0000-0000-000000000007', 'GYM-BAR-01', JSON_OBJECT('art', 'bar'), 49000.00, 50),
  ('22000000-0000-0000-0000-000000000008', '21000000-0000-0000-0000-000000000008', 'YOGA-MAT-01', JSON_OBJECT('art', 'mat', 'badge', 'Khuyên dùng'), 699000.00, 50),
  ('22000000-0000-0000-0000-000000000009', '21000000-0000-0000-0000-000000000009', 'YOGA-BLOCK-01', JSON_OBJECT('art', 'block'), 159000.00, 50),
  ('22000000-0000-0000-0000-000000000010', '21000000-0000-0000-0000-000000000010', 'YOGA-STRAP-01', JSON_OBJECT('art', 'strap'), 129000.00, 50),
  ('22000000-0000-0000-0000-000000000011', '21000000-0000-0000-0000-000000000011', 'YOGA-LEGGING-01', JSON_OBJECT('art', 'legging', 'badge', 'Mới'), 479000.00, 50),
  ('22000000-0000-0000-0000-000000000012', '21000000-0000-0000-0000-000000000012', 'YOGA-BRA-01', JSON_OBJECT('art', 'bra'), 389000.00, 50),
  ('22000000-0000-0000-0000-000000000013', '21000000-0000-0000-0000-000000000013', 'YOGA-SLING-01', JSON_OBJECT('art', 'sling'), 299000.00, 50);
