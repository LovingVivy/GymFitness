# Chạy database MySQL

Yêu cầu: MySQL 8.0 trở lên.

## MySQL Workbench

1. Mở một SQL tab mới.
2. Mở hoặc dán toàn bộ nội dung `01_tables.sql`, sau đó chọn **Execute All**.
3. Mở SQL tab thứ hai.
4. Mở hoặc dán toàn bộ nội dung `02_triggers.sql`, sau đó chọn **Execute All**.
5. Mở SQL tab thứ ba.
6. Mở hoặc dán toàn bộ nội dung `03_procedures.sql`, sau đó chọn **Execute All**.
7. Mở SQL tab thứ tư.
8. Mở hoặc dán toàn bộ nội dung `04_seed.sql`, sau đó chọn **Execute All**.
9. Mở SQL tab thứ năm.
10. Mở hoặc dán toàn bộ nội dung `05_procedures_pt.sql`, sau đó chọn **Execute All**.
11. Mở SQL tab thứ sáu.
12. Mở hoặc dán toàn bộ nội dung `06_procedures_payment.sql`, sau đó chọn **Execute All**.
13. Mở SQL tab thứ bảy.
14. Mở hoặc dán toàn bộ nội dung `07_pt_schedule.sql`, sau đó chọn **Execute All**.

File đầu tiên tự tạo và chọn database `gymfitness`. Các file sau cũng tự chạy `USE gymfitness` trước khi tạo trigger/procedure/seed.

## MySQL Command Line

```bash
mysql -u root -p < database/01_tables.sql
mysql -u root -p < database/02_triggers.sql
mysql -u root -p < database/03_procedures.sql
mysql -u root -p < database/04_seed.sql
mysql -u root -p < database/05_procedures_pt.sql
mysql -u root -p < database/06_procedures_payment.sql
mysql -u root -p < database/07_pt_schedule.sql
```

## Script Python (khuyến nghị)

`scripts/apply_sql.py` đọc thông tin kết nối từ `backend/.env` và tự xử lý directive
`DELIMITER` (driver MySQL không hiểu directive này, chỉ mysql client mới hiểu):

```bash
python scripts/apply_sql.py database/01_tables.sql
python scripts/apply_sql.py database/02_triggers.sql
python scripts/apply_sql.py database/03_procedures.sql
python scripts/apply_sql.py database/04_seed.sql
python scripts/apply_sql.py database/05_procedures_pt.sql
python scripts/apply_sql.py database/06_procedures_payment.sql
python scripts/apply_sql.py database/07_pt_schedule.sql
```

## Kiểm tra kết quả

```sql
USE gymfitness;

SELECT COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'gymfitness';

SELECT COUNT(*) AS trigger_count
FROM information_schema.triggers
WHERE trigger_schema = 'gymfitness';

SELECT COUNT(*) AS foreign_key_count
FROM information_schema.referential_constraints
WHERE constraint_schema = 'gymfitness';

SELECT routine_name
FROM information_schema.routines
WHERE routine_schema = 'gymfitness' AND routine_type = 'PROCEDURE';

SHOW TRIGGERS FROM gymfitness;
```

Kết quả thiết kế hiện tại:

```text
table_count       = 44
trigger_count     = 10
foreign_key_count = 83
procedure_count   = 32
```

Năm script bootstrap dành cho database trống. Sau khi backend được scaffold, thay đổi schema tiếp theo phải được quản lý bằng migration Alembic thay vì chạy lại toàn bộ file bootstrap.

## Stored procedures

Toàn bộ truy vấn của ứng dụng nằm trong `03_procedures.sql`.
Backend chỉ gọi `CALL <procedure>(...)`, không viết `SELECT`/`INSERT`/`UPDATE` trong code.

### Xác thực

| Procedure | Vai trò |
| --- | --- |
| `sp_auth_register` | Kiểm tra trùng email/phone rồi tạo `users` + `user_profiles` + `members` trong một transaction |
| `sp_auth_find_user_by_email` | Lấy tài khoản kèm hồ sơ theo email để kiểm tra mật khẩu |
| `sp_auth_find_user_by_id` | Lấy tài khoản kèm hồ sơ theo id |
| `sp_auth_mark_login_success` | Ghi `last_login_at`, xoá bộ đếm đăng nhập sai |
| `sp_auth_mark_login_failed` | Tăng bộ đếm và tạm khoá tài khoản khi vượt ngưỡng |

### Hồ sơ và gói tập

| Procedure | Vai trò |
| --- | --- |
| `sp_profile_get` | Hồ sơ đầy đủ: tài khoản, thông tin cá nhân, ảnh đại diện, hội viên, gói đang đăng ký kèm `days_remaining`, và ví lượt PT |
| `sp_profile_update` | Cập nhật thông tin cá nhân/thể chất; trường không truyền thì giữ nguyên |
| `sp_plan_list_active` | Danh sách gói tập đang mở bán |
| `sp_plan_find_by_id` | Chi tiết một gói tập |
| `sp_subscription_create` | Tạo payment `PENDING` + subscription `PENDING`; nếu `p_pt_quantity > 0` thì kèm giao dịch mua lượt PT trong cùng payment (ADR-014) |
| `sp_subscription_mark_paid` | Backend xác nhận thanh toán: payment → `PAID`, subscription → `ACTIVE`, tính `start_at`/`end_at` theo lịch tháng thật (ADR-003) và cộng lượt PT mua kèm |
| `sp_file_save_avatar` | Lưu metadata ảnh vào `file_assets`, gắn vào `user_profiles`, soft-delete ảnh cũ và trả `old_storage_key` để backend xoá file trên đĩa |
| `sp_file_get` | Metadata tệp để backend đọc nội dung từ đĩa |

### Thanh toán chuyển khoản QR tự động (`06_procedures_payment.sql`)

| Procedure | Vai trò |
| --- | --- |
| `sp_payment_get_for_user` | Trạng thái payment, chỉ trả về nếu payment thuộc chính tài khoản đó |
| `sp_payment_find_by_number` | Khớp mã chuyển khoản (`payment_number`) trong webhook |
| `sp_payment_event_record` | Ghi webhook thô vào `payment_events`, idempotent theo `(provider, provider_event_id)` |
| `sp_payment_event_finish` | Đánh dấu webhook đã xử lý, gắn mã tham chiếu ngân hàng vào payment |
| `sp_payment_notify_paid` | Thông báo "Thanh toán thành công" (idempotent theo payment) |

### Hồ sơ PT, lượt PT và thông báo (`05_procedures_pt.sql`)

| Procedure | Vai trò |
| --- | --- |
| `sp_trainer_find_by_user` | Hồ sơ PT của một tài khoản role `PT` |
| `sp_pt_credit_get` | Ví lượt PT (`purchased`/`reserved`/`used`/`available`) |
| `sp_pt_credit_purchase_create` | Tạo payment `PENDING` + giao dịch mua lượt `PENDING` |
| `sp_pt_credit_purchase_mark_paid` | Xác nhận thanh toán, cộng lượt và ghi sổ cái |
| `sp_payment_get` | Thông tin payment để backend điều phối theo `purpose` |
| `sp_notification_list` | Thông báo trong ứng dụng |
| `sp_notification_unread_count` | Số thông báo chưa đọc |
| `sp_notification_mark_read` | Đánh dấu một thông báo đã đọc |
| `sp_notification_mark_all_read` | Đánh dấu tất cả đã đọc |

### Lịch làm việc của PT và buổi PT (`07_pt_schedule.sql`, ADR-015)

File này vừa tạo bảng `trainer_weekly_schedule`, `trainer_time_off` vừa nâng cấp
`pt_bookings` (thêm `cancelled_at`, `cancelled_by`, `cancelled_by_role`; cho phép
`availability_id` NULL) và thay trigger kiểm tra booking. Chạy lại nhiều lần an toàn.

| Procedure | Vai trò |
| --- | --- |
| `sp_trainer_list` | PT đang hoạt động **đã khai lịch**, kèm chuyên môn và các ngày làm việc |
| `sp_trainer_schedule_get` | Lịch tuần của một PT (giờ địa phương `HH:MM`) |
| `sp_trainer_schedule_replace` | PT lưu lại toàn bộ lịch tuần (JSON) trong một transaction, chặn khung chồng lấn |
| `sp_trainer_time_off_list` / `_create` / `_delete` | Lịch nghỉ đột xuất |
| `sp_trainer_busy_list` | Giờ đã có người đặt của PT (không kèm thông tin hội viên) để loại khỏi ô trống |
| `sp_pt_session_book` | Hội viên đặt một ô trong lịch tuần → `ACCEPTED` ngay, giữ 1 lượt, báo PT |
| `sp_pt_session_cancel` | Hội viên hoặc PT huỷ trước giờ tập; PT huỷ hoặc hội viên huỷ sớm thì hoàn lượt |
| `sp_pt_session_finish` | PT chốt buổi đã diễn ra: `COMPLETED` hoặc `NO_SHOW`, lượt chuyển sang used |
| `sp_pt_booking_list_for_trainer` | Buổi dạy của PT: sắp tới trước, sau đó lịch sử |
| `sp_pt_booking_list_for_member` | Buổi PT của hội viên |

Ô trống (60 phút) do backend sinh từ lịch tuần, trừ lịch nghỉ và giờ đã đặt; khi đặt,
procedure kiểm tra lại toàn bộ trong transaction có khoá dòng PT nên hai người không
thể cùng lấy một ô. Trigger `trg_pt_bookings_validate_*` vẫn là lớp chặn trùng lịch cuối cùng.

### Luồng PT end-to-end

```sql
-- 1. PT khai lịch tuần: T2 và T4, 17:00–21:00 (giờ Việt Nam)
CALL sp_trainer_schedule_replace('<pt-user-id>',
     '[{"weekday":1,"start_time":"17:00","end_time":"21:00"},
       {"weekday":3,"start_time":"17:00","end_time":"21:00"}]');

-- 2. Hội viên đặt 18:00–19:00 thứ 2 ngày 11/01/2027 (= 11:00–12:00 UTC)
CALL sp_pt_session_book('<booking-id>', 'PTB-0001', '<member-user-id>', '<trainer-id>',
     '2027-01-11 11:00:00', '2027-01-11 12:00:00', 1, '18:00', '19:00',
     '18:00 11/01/2027', 'Buổi đầu tiên');

-- 3a. Hội viên huỷ (hoàn lượt nếu còn >= 12 giờ = 720 phút)
CALL sp_pt_session_cancel('<booking-id>', '<member-user-id>', NULL, 720, 420);

-- 3b. Hoặc sau giờ tập, PT chốt buổi
CALL sp_pt_session_finish('<booking-id>', '<pt-user-id>', 'COMPLETED', 420);
```

### Ví dụ luồng đăng ký gói hoàn chỉnh

```sql
CALL sp_auth_register('<user-id>', '<member-id>', 'a@example.com', '0900000000', '<hash>', 'Nguyen Van A');

SET @plan = (SELECT id FROM membership_plans WHERE code = 'GYM_MONTHLY');
CALL sp_subscription_create('<sub-id>', '<pay-id>', 'PAY-0001', 'idem-0001', '<member-id>', @plan, '<user-id>');

-- Bước backend xác minh thanh toán
CALL sp_subscription_mark_paid('<pay-id>', '<user-id>');

CALL sp_profile_get('<user-id>');   -- trả về gói ACTIVE kèm days_remaining
```

Mở khoá thủ công một tài khoản bị khoá do đăng nhập sai nhiều lần:

```sql
UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE email = 'user@example.com';
```

### Lưu ý về transaction

Các procedure ghi dữ liệu tự `COMMIT` công việc của mình. Vì vậy nếu sau này một
luồng cần gộp nhiều thao tác vào cùng một transaction (ví dụ ghi audit log ngay
sau khi đăng ký), phải bỏ `COMMIT` bên trong procedure và để tầng gọi quyết định
ranh giới transaction.

### Lưu ý về timezone

Engine của backend đặt `SET time_zone = '+00:00'` cho mọi kết nối, nên
`CURRENT_TIMESTAMP` của MySQL và `UTC_TIMESTAMP()` trong procedure ghi cùng một
mốc UTC. API trả về các mốc thời gian kèm hậu tố `Z` để trình duyệt tự đổi sang
giờ địa phương khi hiển thị.

## Seed data

`04_seed.sql` tạo chi nhánh mặc định, 4 gói tập (`GYM_MONTHLY`, `GYM_YEARLY`,
`YOGA_MONTHLY`, `YOGA_YEARLY`) và 2 tài khoản huấn luyện viên. File này idempotent
— chạy lại nhiều lần không tạo bản ghi trùng.

### Tài khoản seed

| Email | Mật khẩu | Vai trò | Ghi chú |
| --- | --- | --- | --- |
| `pt.gym@ironix.vn` | `pt12345678` | `PT` | Trần Hoàng Nam · PT000001 · Gym, tăng cơ |
| `pt.yoga@ironix.vn` | `pt12345678` | `PT` | Lê Thu Hà · PT000002 · Yoga, linh hoạt |

Mật khẩu trong file seed là hash PBKDF2-HMAC-SHA256 (600.000 vòng) do backend sinh
ra bằng `app.core.security.hash_password`; đây không phải mật khẩu plaintext.

```bash
python scripts/apply_sql.py database/04_seed.sql
```


