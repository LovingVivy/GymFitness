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
15. Mở SQL tab thứ tám.
16. Mở hoặc dán toàn bộ nội dung `08_admin.sql`, sau đó chọn **Execute All**.
17. Mở SQL tab thứ chín.
18. Mở hoặc dán toàn bộ nội dung `09_admin_shop.sql`, sau đó chọn **Execute All**.
19. Mở SQL tab thứ mười.
20. Mở hoặc dán toàn bộ nội dung `10_seed_demo.sql`, sau đó chọn **Execute All** (dữ liệu mẫu, không bắt buộc).
21. Mở SQL tab thứ mười một.
22. Mở hoặc dán toàn bộ nội dung `11_platform.sql`, sau đó chọn **Execute All**.
23. Mở SQL tab thứ mười hai.
24. Mở hoặc dán toàn bộ nội dung `12_lifecycle.sql`, sau đó chọn **Execute All**.

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
mysql -u root -p < database/08_admin.sql
mysql -u root -p < database/09_admin_shop.sql
mysql -u root -p < database/10_seed_demo.sql
mysql -u root -p < database/11_platform.sql
mysql -u root -p < database/12_lifecycle.sql
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
python scripts/apply_sql.py database/08_admin.sql
python scripts/apply_sql.py database/09_admin_shop.sql
python scripts/apply_sql.py database/10_seed_demo.sql
python scripts/apply_sql.py database/11_platform.sql
python scripts/apply_sql.py database/12_lifecycle.sql
```

Database đã có từ trước: các file đều chạy lại an toàn. Khi cập nhật mã nguồn, nạp lại
`03_procedures.sql` (gia hạn nối tiếp, hồ sơ hiện gói hết hạn), `07_pt_schedule.sql` (chặn
đặt PT bị khoá), `08_admin.sql`, `09_admin_shop.sql`, `11_platform.sql` và `12_lifecycle.sql`.

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
procedure_count   = 62
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
| `sp_trainer_list` | PT đang hoạt động **đã khai lịch**, kèm chuyên môn và các ngày làm việc; truyền `p_member_user_id` để chỉ lấy PT trùng loại hình gói tập của hội viên (ADR-018) |
| `sp_trainer_schedule_get` | Lịch tuần của một PT (giờ địa phương `HH:MM`) |
| `sp_trainer_schedule_replace` | PT lưu lại toàn bộ lịch tuần (JSON) trong một transaction, chặn khung chồng lấn |
| `sp_trainer_time_off_list` / `_create` / `_delete` | Lịch nghỉ đột xuất |
| `sp_trainer_busy_list` | Giờ đã có người đặt của PT (không kèm thông tin hội viên) để loại khỏi ô trống |
| `sp_pt_session_book` | Hội viên đặt một ô trong lịch tuần → `ACCEPTED` ngay, giữ 1 lượt, báo PT; từ chối `TRAINER_MISMATCH` nếu chuyên môn PT không trùng loại hình gói tập |
| `sp_pt_session_cancel` | Hội viên hoặc PT huỷ trước giờ tập; PT huỷ hoặc hội viên huỷ sớm thì hoàn lượt |
| `sp_pt_session_finish` | PT chốt buổi đã diễn ra: `COMPLETED` hoặc `NO_SHOW`, lượt chuyển sang used |
| `sp_pt_booking_list_for_trainer` | Buổi dạy của PT: sắp tới trước, sau đó lịch sử |
| `sp_pt_booking_list_for_member` | Buổi PT của hội viên |

Ô trống (60 phút) do backend sinh từ lịch tuần, trừ lịch nghỉ và giờ đã đặt; khi đặt,
procedure kiểm tra lại toàn bộ trong transaction có khoá dòng PT nên hai người không
thể cùng lấy một ô. Trigger `trg_pt_bookings_validate_*` vẫn là lớp chặn trùng lịch cuối cùng.

### Quản trị (`08_admin.sql`, ADR-016)

Thêm cột `users.username` (đăng nhập bằng email **hoặc** tên đăng nhập) và các
procedure cho trang `/admin`. Mọi thao tác ghi của admin được lưu vào `audit_logs`.
Chạy lại nhiều lần an toàn.

| Procedure | Vai trò |
| --- | --- |
| `sp_admin_bootstrap` | Tạo admin mặc định nếu chưa có; không bao giờ ghi đè mật khẩu |
| `sp_admin_overview` | Số liệu nhanh: hội viên (kèm số mới tháng này/tháng trước), hội viên còn gói, PT, doanh thu tháng này/tháng trước, giao dịch chờ |
| `sp_admin_user_list` | Tìm/lọc/phân trang tài khoản (tên, email, sđt, mã hội viên, tên đăng nhập) |
| `sp_admin_user_create` | Tạo USER (kèm hồ sơ hội viên), PT (kèm hồ sơ + chuyên môn) hoặc ADMIN |
| `sp_admin_user_update` | Sửa thông tin, trạng thái (khoá/mở), giá + chuyên môn của PT |
| `sp_admin_user_set_password` | Đặt lại mật khẩu và mở khoá đăng nhập |
| `sp_admin_user_delete` | Xoá mềm, giải phóng email/sđt; chặn khi còn buổi PT sắp tới hoặc là admin cuối |
| `sp_admin_plan_list` / `_save` / `_delete` | Quản lý gói tập (xoá = xoá mềm + ngừng bán) |
| `sp_admin_checkin_list` | Lịch sử ra vào theo khoảng ngày, tìm kiếm, lọc người đang trong phòng |
| `sp_admin_checkin_create` / `sp_admin_checkout` | Check-in tại quầy (cần gói còn hạn) và check-out |
| `sp_admin_revenue` | Doanh thu PAID gom theo tuần/tháng/quý/năm (giờ phòng tập), tách gói/PT |

Tài khoản admin mặc định (`admin@gmail.com`, tên đăng nhập `admin`) được backend tạo
lúc khởi động từ `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_DEFAULT_PASSWORD` trong
`backend/.env` — mật khẩu không nằm trong repo; để trống thì không tạo.

### Báo cáo hội viên, thanh toán và cửa hàng (`09_admin_shop.sql`, ADR-017)

| Procedure | Vai trò |
| --- | --- |
| `sp_admin_member_base` / `sp_admin_member_growth` | Hội viên mới theo tuần/tháng/quý/năm và số hội viên trước kỳ đầu để cộng dồn tổng |
| `sp_admin_payment_list` | Tìm/lọc/phân trang giao dịch, kèm gói, số buổi PT, ghi chú webhook và tổng đã thu |
| `sp_admin_payment_confirm_log` | Ghi hình thức thu tiền và audit log sau khi admin xác nhận thủ công |
| `sp_admin_payment_void` | Huỷ giao dịch `PENDING`: payment `VOID`, gói chờ `CANCELLED`, lượt PT chờ `VOID` |
| `sp_product_list_public` | Sản phẩm đang bán cho trang `/products` |
| `sp_admin_product_list` / `_save` / `_delete` | Quản lý sản phẩm, giá, tồn kho (ghi `inventory_movements`); xoá = xoá mềm + giải phóng SKU |

### Nền tảng (`11_platform.sql`, ADR-019 … ADR-025)

| Procedure / thay đổi | Mục đích |
| --- | --- |
| CHECK `chk_users_role` | Thêm vai trò `MANAGER` (tự gỡ CHECK cũ của database đang chạy) |
| `sp_password_reset_create`, `sp_password_reset_consume` | Token đặt lại mật khẩu một lần (chỉ lưu SHA-256), mở khoá tài khoản |
| `sp_auth_two_factor_get`, `sp_auth_two_factor_set` | Khoá TOTP đã mã hoá; bật/tắt có audit log |
| `sp_job_create`, `sp_job_claim`, `sp_job_progress`, `sp_job_finish`, `sp_job_get`, `sp_job_list`, `sp_job_pending_list` | Hàng đợi tác vụ nền trên bảng `background_jobs` |
| `sp_file_save` | Metadata file do backend tạo (báo cáo xuất) |
| `sp_audit_log_list` | Nhật ký thao tác có lọc, tìm kiếm, phân trang |
| `sp_invoice_issue` | Lập hoá đơn `HDyyyymm-nnnnn` cho payment đã thu, trả dữ liệu dựng PDF |
| `sp_pt_booking_contact` | Thông tin liên hệ để gửi email khi huỷ buổi PT |
| `sp_admin_product_find_by_sku` | Nhập sản phẩm từ Excel/CSV theo SKU |

Các procedure danh sách trong `08_admin.sql`/`09_admin_shop.sql` nhận thêm `p_sort`
(`sp_admin_user_list`, `sp_admin_checkin_list`, `sp_admin_payment_list`, `sp_admin_product_list`);
`sp_admin_plan_save` và `sp_admin_product_save` nhận `p_expected_version` (khoá lạc quan).

### Vòng đời gói và buổi PT (`12_lifecycle.sql`, ADR-026)

| Procedure | Mục đích |
| --- | --- |
| `sp_subscription_expire_due` | Chuyển gói quá hạn sang `EXPIRED`, ghi lịch sử, thông báo (bỏ qua gói đã gia hạn) |
| `sp_subscription_reminders_due` | Nhắc gia hạn ở mốc ≤ 7, ≤ 3, ≤ 1 ngày; mỗi mốc một lần (`idempotency_key`) |
| `sp_pt_session_autoclose` | Buổi PT kết thúc quá 24 giờ mà PT chưa chốt: tự ghi `COMPLETED`, trừ lượt |
| `sp_pt_cancel_upcoming_for_user` | Gọi từ `sp_admin_user_update` khi khoá/ngưng tài khoản: huỷ buổi chưa bắt đầu, hoàn lượt |
| `sp_profile_memberships` | Mọi gói còn hiệu lực của tài khoản (một dòng mỗi loại hình, tính cả chuỗi gia hạn) |

Backend gọi ba procedure định kỳ mỗi 5 phút (`app/tasks/maintenance.py`): trong worker, hoặc
trong API khi `MAINTENANCE_IN_API=true` (mặc định khi chạy không Docker).

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
`YOGA_MONTHLY`, `YOGA_YEARLY`), 2 tài khoản huấn luyện viên và 13 sản phẩm mẫu của
cửa hàng. File này idempotent
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

### Dữ liệu mẫu số lượng lớn (`10_seed_demo.sql`)

Tạo khoảng 11.000 bản ghi mô phỏng một phòng tập đã hoạt động 12 tháng, để các màn hình
quản trị (tài khoản, giao dịch, ra vào, doanh thu, tăng trưởng hội viên) có dữ liệu cho
tìm kiếm, lọc và phân trang. File không bắt buộc và **không dùng cho production**.

| Bảng | Số bản ghi (xấp xỉ) | Nội dung |
| --- | --- | --- |
| `users`, `user_profiles` | 306 mỗi bảng | 300 hội viên và 6 huấn luyện viên |
| `members` | 300 | Mã `DEMO000001` … `DEMO000300` |
| `trainer_profiles` và lịch tuần | 6 PT, 36 khung giờ | Mã `DEMOPT01` … `DEMOPT06`, T2–T7 08:00–20:00 |
| `membership_subscriptions` | 1.000+ | Kỳ đầu và các kỳ gia hạn của gói tháng |
| `payments` | 1.100+ | Thanh toán gói tập và mua lượt PT, đều `PAID` |
| `subscription_status_history` | 1.900+ | Kích hoạt và hết hạn gói |
| `check_ins` | 3.900+ | Lượt ra vào trong khung 06:00–20:00, đều đã check-out |
| `pt_credit_accounts`, `pt_credit_purchases` | ~90 mỗi bảng | Ví lượt PT của hội viên gói năm |
| `pt_bookings` | 550+ | Buổi PT đã diễn ra (`COMPLETED` hoặc `NO_SHOW`) |
| `pt_credit_ledger` | 1.100+ | Sổ cái mua, giữ và trừ lượt, khớp với số dư ví |

Số bản ghi thay đổi nhẹ theo ngày chạy vì mọi mốc thời gian được tính lùi từ lúc chạy
file: dữ liệu luôn trải trên 12 tháng gần nhất.

- **Chạy lại an toàn:** nếu dữ liệu mẫu đã có, file không làm gì cả. Toàn bộ nằm trong một
  transaction, lỗi giữa chừng sẽ rollback hết.
- **Không đăng nhập được:** tài khoản mẫu có `password_hash` không hợp lệ. Muốn dùng thử một
  tài khoản, đặt lại mật khẩu cho nó ở trang quản trị.
- **Nhận diện:** email `@demo.ironix.vn`, mã hội viên `DEMO…`, mã PT `DEMOPT…`, id bắt đầu
  bằng chữ `d`.
- **Tách khỏi bộ test:** buổi PT mẫu gắn với 6 PT mẫu, không gắn với hai PT ở
  `04_seed.sql`, vì `backend/tests/test_pt.py` xoá mọi buổi của hai PT đó sau mỗi test.

```bash
python scripts/apply_sql.py database/10_seed_demo.sql
```


