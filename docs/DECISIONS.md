# ARCHITECTURE DECISIONS

## ADR-001 — MySQL 8.0+ là database chính

- **Trạng thái:** Accepted
- **Quyết định:** Dùng MySQL 8.0+, `CHAR(36)` primary key do ứng dụng sinh và `DATETIME(6)` lưu UTC.
- **Lý do:** Phù hợp lựa chọn công nghệ của dự án; InnoDB cung cấp transaction và foreign key, JSON lưu metadata linh hoạt.

## ADR-002 — Ba vai trò hệ thống

- **Trạng thái:** Accepted
- **Quyết định:** Chỉ dùng `ADMIN`, `USER`, `PT`. Trách nhiệm Manager trong đặc tả ban đầu được gộp vào Admin.
- **Lý do:** Phù hợp luồng nghiệp vụ mới do chủ dự án xác nhận.

## ADR-003 — Thời hạn gói theo tháng lịch

- **Trạng thái:** Accepted
- **Quyết định:** Gói tháng/năm lưu `duration_months`; gói đặc biệt có thể lưu `duration_days`. Chỉ một loại thời hạn có giá trị.
- **Lý do:** Một tháng không tương đương cố định 30 ngày và một năm không luôn tương đương 365 ngày.

## ADR-004 — Payment xác nhận ở backend

- **Trạng thái:** Accepted
- **Quyết định:** Chỉ webhook đã xác minh hoặc thao tác Admin có audit mới chuyển payment thành `PAID` và kích hoạt quyền lợi.
- **Lý do:** Không tin trạng thái thanh toán do frontend gửi lên.

## ADR-005 — Lượt PT dùng account và ledger

- **Trạng thái:** Accepted
- **Quyết định:** Lưu tổng purchased/reserved/used trong `pt_credit_accounts` và ghi mọi biến động vào `pt_credit_ledger`.
- **Lý do:** Ngăn đặt vượt lượt, hỗ trợ idempotency, hoàn lượt và đối soát lịch sử.

## ADR-006 — Giữ lượt ngay khi gửi yêu cầu PT

- **Trạng thái:** Superseded bởi ADR-015 (vẫn giữ lượt khi đặt, nhưng không còn bước PT duyệt)
- **Quyết định:** Khi tạo booking `REQUESTED`, giữ một lượt PT. Từ chối hoặc hết hạn sẽ hoàn lượt; hoàn thành chuyển lượt sang used.
- **Lý do:** Ngăn user gửi nhiều yêu cầu vượt quá số lượt đã thanh toán.

## ADR-007 — Ngăn lịch chồng lấn ở database

- **Trạng thái:** Accepted
- **Quyết định:** Dùng trigger MySQL để kiểm tra overlap và service transaction với `SELECT ... FOR UPDATE` cho availability, PT booking và class session.
- **Lý do:** Trigger bảo vệ các lệnh ghi trực tiếp; row lock trong service xử lý an toàn các request đồng thời.

## ADR-008 — QR thanh toán tách QR check-in

- **Trạng thái:** Accepted
- **Quyết định:** QR thanh toán thuộc payment; QR check-in dùng signed token/nonce ngắn hạn và chỉ lưu hash nonce.
- **Lý do:** Hai loại QR có vòng đời, dữ liệu và yêu cầu bảo mật khác nhau.

## ADR-009 — Snapshot dữ liệu đơn hàng

- **Trạng thái:** Accepted
- **Quyết định:** Order lưu snapshot địa chỉ, SKU, tên, thuộc tính và giá tại lúc đặt hàng.
- **Lý do:** Thay đổi profile hoặc catalog không được sửa lịch sử đơn hàng.

## ADR-010 — Database hỗ trợ nhiều chi nhánh

- **Trạng thái:** Accepted
- **Quyết định:** Có bảng `branches` và liên kết member, PT, phòng, check-in, thiết bị với chi nhánh.
- **Lý do:** Chi phí bổ sung thấp và tránh phải thay đổi schema lớn khi phòng gym mở rộng.

## ADR-011 — Băm mật khẩu PBKDF2 và JWT bằng thư viện chuẩn

- **Trạng thái:** Accepted
- **Quyết định:** Băm mật khẩu bằng PBKDF2-HMAC-SHA256 (600.000 vòng, salt ngẫu nhiên 16 byte) và ký JWT HS256 thủ công bằng `hmac`/`hashlib` của thư viện chuẩn Python; không cài thêm thư viện ngoài.
- **Lý do:** Môi trường triển khai không cài được gói qua `pip` (sandbox chặn ghi). PBKDF2 là thuật toán KDF chuẩn, đủ an toàn cho demo; cấu trúc hash `pbkdf2_sha256$iterations$salt$digest` cho phép nâng lên Argon2 sau này mà không phá vỡ dữ liệu cũ (verify phân nhánh theo prefix).

## ADR-012 — Thanh toán chuyển khoản VietQR, xác nhận qua webhook SePay

- **Trạng thái:** Accepted
- **Quyết định:** Mỗi payment có `payment_number` dạng `IRX` + `YYMMDD` + 8 ký tự hex (chỉ chữ và số) làm nội dung chuyển khoản. Frontend hiển thị VietQR (`img.vietqr.io`) và hỏi `GET /api/v1/payments/{id}` mỗi 3 giây. SePay gọi `POST /api/v1/payments/webhooks/sepay` với header `Authorization: Apikey <SEPAY_WEBHOOK_API_KEY>`; backend ghi `payment_events`, tìm mã trong nội dung, chỉ kích hoạt khi số tiền ≥ số phải trả. `POST /payments/{id}/mark-paid` chỉ còn là công cụ giả lập cho chủ payment ở môi trường dev (`PAYMENT_SIMULATION_ENABLED`) và cho Admin.
- **Lý do:** Thực thi ADR-004: trình duyệt không bao giờ tự kích hoạt quyền lợi. Mã không có dấu câu vì ngân hàng hay cắt/đổi ký tự đặc biệt. Webhook idempotent theo `(provider, provider_event_id)` để SePay gửi lại không cộng quyền lợi hai lần; chuyển thiếu tiền giữ `PENDING` và lưu lại để đối soát thủ công.

## ADR-013 — Từ chối JWT secret yếu ngoài môi trường dev

- **Trạng thái:** Accepted
- **Quyết định:** Khi `APP_ENV` khác `development`/`test`, backend không khởi động nếu `JWT_SECRET_KEY` trống, là giá trị mẫu hoặc ngắn hơn 32 ký tự. Ở dev, secret trống được thay bằng khoá ngẫu nhiên theo tiến trình.
- **Lý do:** Secret mẫu nằm trong repo; ai đọc được repo có thể tự ký token Admin.

## ADR-014 — Một payment cho gói hội viên và lượt PT mua kèm

- **Trạng thái:** Accepted
- **Quyết định:** `POST /subscriptions` nhận thêm `pt_sessions`. Cùng một payment (`purpose = MEMBERSHIP`) được tham chiếu bởi subscription và bởi `pt_credit_purchases`; `sp_subscription_mark_paid` kích hoạt gói và cộng lượt PT trong cùng transaction.
- **Lý do:** Trước đây hội viên phải quét hai mã QR liên tiếp; bỏ ngang sau lần một thì mất đơn PT. Không cần bảng đơn hàng mới vì `payment_id` ở cả hai bảng đều là UNIQUE riêng.

## ADR-015 — PT khai lịch tuần, hội viên đặt là xác nhận ngay

- **Trạng thái:** Accepted
- **Quyết định:** PT khai giờ làm việc lặp lại hằng tuần (`trainer_weekly_schedule`, giờ địa phương) và nghỉ đột xuất (`trainer_time_off`). Backend sinh ô 60 phút còn trống trong 14 ngày tới, từ 2 giờ sau thời điểm hiện tại. Hội viên đặt một ô → booking `ACCEPTED` ngay. PT chỉ xử lý ngoại lệ: huỷ kèm lý do (luôn hoàn lượt), chốt `COMPLETED`/`NO_SHOW` sau giờ tập. Hội viên huỷ trước 12 giờ được hoàn lượt, sát giờ hơn thì mất lượt. PT chưa khai lịch không hiện với hội viên; lần đăng nhập đầu PT được đưa tới "Lịch của bạn". Đổi lịch hoặc thêm lịch nghỉ không tự huỷ buổi đã đặt mà liệt kê để PT tự quyết.
- **Lý do:** Mô hình cũ bắt PT vừa bật/tắt rảnh-bận vừa duyệt từng yêu cầu — cùng một việc làm hai lần, còn hội viên không biết buổi có chắc chắn không. Múi giờ cố định UTC+7 (Việt Nam không đổi giờ mùa hè) nên không phụ thuộc gói `tzdata`.
