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
