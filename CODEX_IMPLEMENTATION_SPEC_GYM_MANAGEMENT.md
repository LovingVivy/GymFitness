# CODEX IMPLEMENTATION SPEC — GYM MANAGEMENT SYSTEM

**Phiên bản:** 1.0  
**Ngày lập:** 07/09/2026  
**Mục đích:** Tài liệu nguồn duy nhất để Codex triển khai hệ thống Quản lý trung tâm thể dục (Gym Management) theo Master Plan và bộ yêu cầu chất lượng/vận hành.

---

## 1. Mục tiêu dự án

Xây dựng một hệ thống quản lý trung tâm thể dục có thể chạy demo end-to-end, hỗ trợ:

- Quản lý tài khoản, phân quyền và hồ sơ người dùng.
- Quản lý hội viên, gói tập, đăng ký/gia hạn/đóng băng/hủy gói.
- Check-in/check-out bằng QR.
- Quản lý lớp học, lịch học, sức chứa, đặt chỗ, hủy, waitlist.
- Quản lý huấn luyện viên cá nhân (PT), lịch làm việc và đặt lịch.
- Thanh toán, hóa đơn, lịch sử giao dịch.
- Quản lý thiết bị và bảo trì.
- Dashboard doanh thu, hội viên, check-in, lớp học.
- Import/Export Excel/CSV, xuất PDF.
- Audit log, soft-delete, versioning cơ bản.
- Email/in-app notification và background jobs.
- API docs, test, Docker, CI/CD, logging, health check.

Hệ thống phải ưu tiên tính đúng đắn nghiệp vụ, khả năng truy vết, bảo mật và khả năng triển khai hơn là các hiệu ứng giao diện phức tạp.

---

## 2. Phạm vi và nguyên tắc triển khai

### 2.1. Phạm vi MVP bắt buộc

MVP chỉ được coi là hoàn thành khi có đủ các luồng sau:

1. Admin/Manager tạo và quản lý hội viên.
2. Hội viên mua hoặc được gán một gói tập.
3. Gói tập có vòng đời rõ ràng: `PENDING -> ACTIVE -> FROZEN/EXPIRED/CANCELLED`.
4. Hội viên check-in hợp lệ bằng QR.
5. Hội viên đặt lớp hoặc lịch PT nếu còn quyền sử dụng.
6. Hệ thống ghi nhận thanh toán và sinh hóa đơn.
7. Hệ thống gửi được thông báo hoặc tạo notification record.
8. Dashboard phản ánh dữ liệu giao dịch/check-in/lớp.
9. Mọi hành động nhạy cảm có audit log.
10. Có seed >= 2.000 bản ghi.
11. Có Swagger/OpenAPI, Postman, test, Docker Compose và health check.

### 2.2. Quy tắc dành cho Codex

- Không tự ý đổi nghiệp vụ đã mô tả trong tài liệu.
- Không bỏ qua validation chỉ để làm demo chạy được.
- Không hard-code secret, token, password, database URL.
- Không lưu password dạng plaintext.
- Không dùng float cho tiền; dùng Decimal/Numeric.
- Mọi API danh sách phải hỗ trợ pagination; các màn CRUD chính phải có search/filter/sort.
- Mọi thay đổi trạng thái quan trọng phải chạy trong transaction.
- Mọi dữ liệu "xóa" nghiệp vụ phải ưu tiên soft-delete nếu không có yêu cầu pháp lý phải xóa thật.
- Nếu phát hiện mâu thuẫn, ưu tiên: yêu cầu bắt buộc trong tài liệu này -> Master Plan -> implementation detail.
- Nếu chưa rõ một chi tiết nhỏ, chọn phương án đơn giản, an toàn, có test và ghi rõ trong `docs/DECISIONS.md`.

---

## 3. Kiến trúc đề xuất

### 3.1. Tech stack mặc định

Nếu repository hiện tại chưa khóa công nghệ, dùng:

**Backend**
- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- PostgreSQL 16

**Async / Cache**
- Redis
- Celery
- Celery Beat cho job định kỳ

**Frontend**
- React + TypeScript
- Vite
- React Router
- TanStack Query
- Form validation bằng Zod hoặc tương đương

**Storage**
- Local private storage trong môi trường dev.
- Thiết kế interface để có thể thay bằng S3-compatible storage.

**Testing**
- Pytest
- httpx/FastAPI TestClient
- Playwright hoặc Cypress cho E2E nếu thời gian cho phép.

**DevOps**
- Docker + Docker Compose
- GitHub Actions hoặc CI tương đương.

### 3.2. Sơ đồ logic

```text
Browser
   |
   v
Frontend (React)
   |
   v
REST API (FastAPI)
   |---- PostgreSQL
   |---- Redis cache
   |---- Redis/Celery broker
   |---- Private file storage
   |
   v
Celery Worker
   |---- Email
   |---- Export reports
   |---- PDF generation
   |---- Expiry jobs
```

### 3.3. Cấu trúc repository mong muốn

```text
gym-management/
  backend/
    app/
      api/
      core/
      db/
      models/
      schemas/
      services/
      repositories/
      tasks/
      integrations/
      utils/
    migrations/
    tests/
    Dockerfile
  frontend/
    src/
      api/
      components/
      features/
      layouts/
      pages/
      routes/
      types/
    Dockerfile
  docs/
    SRS.md
    ARCHITECTURE.md
    ERD.md
    API.md
    DEPLOYMENT.md
    USER_GUIDE.md
    DECISIONS.md
  scripts/
    seed.py
  docker-compose.yml
  .env.example
  README.md
```

---

## 4. Vai trò và phân quyền

Hệ thống dùng RBAC tối thiểu bốn vai trò:

### 4.1. Admin
- Toàn quyền.
- Quản lý tài khoản và vai trò.
- Xem audit log toàn hệ thống.
- Cấu hình gói tập, lớp, thiết bị.
- Xem dashboard toàn bộ.
- Có quyền khóa/mở tài khoản.

### 4.2. Manager
- Quản lý hội viên.
- Quản lý gói tập, đăng ký gói, check-in.
- Quản lý lớp, lịch PT, thanh toán, hóa đơn.
- Quản lý thiết bị/bảo trì.
- Xem dashboard nghiệp vụ.
- Không được cấp quyền Admin cho người khác.

### 4.3. Trainer
- Xem và cập nhật hồ sơ PT của chính mình.
- Quản lý lịch làm việc của bản thân.
- Xem booking được giao.
- Điểm danh/no-show các buổi phụ trách.
- Không được xem dữ liệu tài chính ngoài phần liên quan.

### 4.4. Member
- Quản lý hồ sơ cá nhân.
- Xem gói hiện tại/lịch sử gói.
- Tạo QR hoặc xem QR check-in.
- Đặt/hủy lớp.
- Đặt/hủy PT.
- Xem lịch sử check-in, thanh toán và hóa đơn của bản thân.

### 4.5. Enforcement

Backend là nơi quyết định quyền. Frontend chỉ ẩn/hiện UI và không được coi là lớp bảo mật.

Mỗi endpoint cần kiểm tra:
1. Đã authenticate hay chưa.
2. Role có quyền action hay không.
3. Resource scope có thuộc user hiện tại hay không.

---

## 5. Authentication & Account

### 5.1. Chức năng bắt buộc

- Register.
- Login.
- Refresh token.
- Logout/revoke refresh token.
- Forgot password.
- Reset password bằng token có thời hạn.
- Đổi password.
- Xem/cập nhật profile.
- 2FA TOTP là optional nhưng kiến trúc phải cho phép bổ sung.
- OAuth2 social login là optional; nếu triển khai thì không được làm giảm bảo mật của login thường.

### 5.2. JWT

- Access token ngắn hạn, đề xuất 15–30 phút.
- Refresh token dài hạn, đề xuất 7–30 ngày.
- Refresh token phải có khả năng revoke.
- Không đưa thông tin nhạy cảm vào payload.
- Token chứa tối thiểu: `sub`, `role`, `iat`, `exp`, `jti`.

### 5.3. Password

- Hash bằng Argon2 hoặc bcrypt.
- Có policy tối thiểu 8 ký tự.
- Reset token dùng một lần, có expiry.
- Rate limit login/reset password.

---

## 6. Hội viên và hồ sơ

### 6.1. Member

Các trường tối thiểu:
- `id`
- `member_code`
- `user_id` nullable nếu hội viên chưa có tài khoản đăng nhập
- `full_name`
- `email`
- `phone`
- `date_of_birth`
- `gender`
- `address`
- `emergency_contact_name`
- `emergency_contact_phone`
- `joined_at`
- `status`
- `notes`
- `created_at`
- `updated_at`
- `deleted_at`
- `row_version`

### 6.2. Quy tắc

- `member_code` duy nhất.
- Email/phone phải được normalize trước khi kiểm tra trùng.
- Không cho check-in nếu hội viên bị `SUSPENDED` hoặc `INACTIVE`.
- Soft-delete member không được làm mất lịch sử payment/check-in.
- Các thay đổi nhạy cảm phải tăng `row_version`.

---

## 7. Gói tập và đăng ký gói

### 7.1. MembershipPlan

Trường tối thiểu:
- `id`
- `name`
- `code`
- `description`
- `duration_days`
- `price`
- `currency`
- `max_visits` nullable
- `freeze_days_allowed`
- `is_active`
- timestamps

### 7.2. MembershipSubscription

Trường tối thiểu:
- `id`
- `member_id`
- `plan_id`
- `start_date`
- `end_date`
- `status`
- `remaining_visits` nullable
- `frozen_from`
- `frozen_until`
- `cancelled_at`
- `created_by`
- timestamps
- `row_version`

### 7.3. Trạng thái

```text
PENDING
  |
  +--> ACTIVE
         |
         +--> FROZEN --> ACTIVE
         |
         +--> EXPIRED
         |
         +--> CANCELLED
```

### 7.4. Quy tắc

- Chỉ subscription `ACTIVE` mới cho check-in, trừ rule đặc biệt được cấu hình.
- `end_date >= start_date`.
- Freeze không được vượt quá số ngày cho phép.
- Khi hết hạn, Celery Beat chạy job đổi `ACTIVE -> EXPIRED`.
- Gia hạn phải lưu lịch sử, không overwrite mất gói cũ.
- Không dùng float cho giá tiền.

---

## 8. Check-in / Check-out bằng QR

### 8.1. QR token

QR không được chỉ chứa `member_id` thuần túy.

Nên chứa signed token:
- member/subscription reference
- issued_at
- expires_at
- nonce

Token phải được ký bằng secret phía server.

### 8.2. Check-in rules

Một check-in hợp lệ khi:
- member active
- subscription active
- chưa hết hạn
- còn lượt nếu plan giới hạn lượt
- QR chưa hết hạn
- QR chưa bị replay nếu dùng one-time nonce

### 8.3. CheckIn record

- `id`
- `member_id`
- `subscription_id`
- `check_in_at`
- `check_out_at`
- `method` (`QR`, `MANUAL`)
- `created_by`
- `location`
- timestamps

### 8.4. Anti-replay

- QR ngắn hạn hoặc rotating QR.
- Rate limit endpoint.
- Có thể lưu nonce trong Redis đến khi hết hạn.
- Check-in duplicate trong khoảng ngắn phải bị chặn.

---

## 9. Lớp học

### 9.1. Entity

**ClassType**
- tên lớp
- mô tả
- thời lượng
- active

**ClassSession**
- class_type_id
- trainer_id
- room_id
- start_at
- end_at
- capacity
- status

**ClassBooking**
- session_id
- member_id
- status
- booked_at
- cancelled_at
- check_in_at

### 9.2. Booking status

- `BOOKED`
- `WAITLISTED`
- `CANCELLED`
- `ATTENDED`
- `NO_SHOW`

### 9.3. Quy tắc

- Không vượt `capacity`.
- Nếu đầy, booking mới vào waitlist.
- Khi có người hủy, người đầu waitlist được promote.
- Không cho một member booking trùng giờ.
- Không cho trainer phụ trách hai lớp trùng giờ.
- Cancellation deadline có thể cấu hình.
- Mọi promotion waitlist phải có audit/event.

---

## 10. Personal Trainer (PT)

### 10.1. TrainerProfile

- `user_id`
- `bio`
- `specialties`
- `certifications`
- `hourly_rate`
- `status`

### 10.2. TrainerAvailability

- `trainer_id`
- `start_at`
- `end_at`
- `recurrence_rule` optional
- `status`

### 10.3. PTBooking

- `member_id`
- `trainer_id`
- `start_at`
- `end_at`
- `status`
- `price`
- `notes`
- timestamps

### 10.4. Quy tắc

- Không double booking trainer.
- Không double booking member.
- Booking chỉ nằm trong availability.
- `end_at > start_at`.
- Trainer chỉ cập nhật kết quả buổi tập của booking mình phụ trách.
- Các thay đổi lịch phải phát notification.

---

## 11. Thanh toán và hóa đơn

### 11.1. Payment

- `id`
- `member_id`
- `subscription_id` nullable
- `pt_booking_id` nullable
- `amount`
- `currency`
- `method`
- `status`
- `external_reference`
- `paid_at`
- `created_by`
- timestamps

Payment status:
- `PENDING`
- `PAID`
- `FAILED`
- `REFUNDED`
- `VOID`

### 11.2. Invoice

- `id`
- `invoice_number`
- `member_id`
- `payment_id`
- `subtotal`
- `tax`
- `discount`
- `total`
- `status`
- `issued_at`
- `paid_at`
- `pdf_path`

Invoice status:
- `DRAFT`
- `ISSUED`
- `PAID`
- `VOID`

### 11.3. Business rules

- `total = subtotal + tax - discount`.
- Tất cả tiền dùng `NUMERIC/Decimal`.
- Issue invoice và cập nhật payment liên quan phải transaction-safe.
- Không được sửa trực tiếp invoice đã `ISSUED`; nếu cần thay đổi, void và tạo bản mới.
- PDF hóa đơn được sinh bằng background job nếu tác vụ nặng.
- File PDF không public trực tiếp; download qua authorized endpoint/signed URL.

---

## 12. Thiết bị và bảo trì

### 12.1. Equipment

- `id`
- `asset_code`
- `name`
- `category`
- `location`
- `purchase_date`
- `warranty_until`
- `status`
- `notes`
- timestamps
- `deleted_at`

Status:
- `ACTIVE`
- `MAINTENANCE`
- `OUT_OF_SERVICE`
- `RETIRED`

### 12.2. MaintenanceRecord

- `equipment_id`
- `scheduled_at`
- `started_at`
- `completed_at`
- `type`
- `cost`
- `vendor`
- `description`
- `status`

### 12.3. Quy tắc

- Equipment ở `OUT_OF_SERVICE` không được coi là available.
- Có lịch sử bảo trì.
- Chi phí bảo trì dùng Decimal.
- Có filter theo trạng thái, loại thiết bị, địa điểm.

---

## 13. Search / Filter / Sort / Pagination

Tối thiểu các module sau phải hỗ trợ:
- Members
- Plans
- Subscriptions
- Class sessions
- PT bookings
- Payments
- Invoices
- Equipment
- Audit logs

API convention:

```http
GET /api/v1/members?q=duong&status=ACTIVE&page=1&page_size=20&sort=-created_at
```

Response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "pages": 0
}
```

Giới hạn `page_size`, đề xuất max 100.

---

## 14. Audit log, soft-delete và versioning

### 14.1. AuditLog

- `id`
- `actor_user_id`
- `action`
- `entity_type`
- `entity_id`
- `before_data` JSONB nullable
- `after_data` JSONB nullable
- `ip_address`
- `user_agent`
- `created_at`

Audit tối thiểu:
- login failures quan trọng
- role changes
- member create/update/delete
- subscription state changes
- check-in manual override
- class/PT booking change
- payment/invoice state changes
- equipment maintenance status

### 14.2. Soft-delete

Các bảng nghiệp vụ chính dùng `deleted_at`.

Query mặc định không trả record đã xóa.

### 14.3. Versioning / optimistic locking

Các record nhạy cảm dùng `row_version`.

Update phải kiểm tra version:
```sql
UPDATE ...
SET ..., row_version = row_version + 1
WHERE id = :id AND row_version = :expected_version
```

Nếu không update được record nào -> trả `409 Conflict`.

---

## 15. Notification & background jobs

### 15.1. Notification

Kênh:
- In-app bắt buộc ở mức data model.
- Email tối thiểu cho một số luồng.

Loại notification:
- sắp hết hạn gói
- gói đã hết hạn
- booking lớp thành công/hủy/promotion từ waitlist
- booking PT
- payment thành công
- invoice đã phát hành
- thay đổi lịch

### 15.2. Job Queue

Celery dùng cho:
- gửi email
- export Excel/CSV lớn
- sinh PDF
- expire subscription
- nhắc gia hạn
- nhắc lịch lớp/PT

Job record nên có:
- `job_id`
- `type`
- `status`
- `progress`
- `result_path`
- `error_message`
- timestamps

Status:
- `PENDING`
- `RUNNING`
- `SUCCESS`
- `FAILED`

---

## 16. Import / Export

### 16.1. Import hội viên

Hỗ trợ:
- `.xlsx`
- `.csv`

Quy trình:
1. Upload.
2. Validate file type/size.
3. Parse trong worker nếu file lớn.
4. Validate từng row.
5. Import row hợp lệ theo strategy.
6. Trả summary và danh sách lỗi theo dòng.

Không được âm thầm bỏ qua row lỗi.

Import result:
```json
{
  "total_rows": 100,
  "success_rows": 94,
  "failed_rows": 6,
  "errors": [
    {"row": 7, "field": "email", "message": "invalid email"}
  ]
}
```

### 16.2. Export

Export:
- member list
- subscriptions
- check-in report
- revenue report
- class attendance
- equipment maintenance

Format:
- CSV
- Excel
- PDF đối với báo cáo/hóa đơn phù hợp.

---

## 17. Dashboard

Dashboard Manager/Admin tối thiểu có:

- Tổng hội viên active.
- Hội viên mới theo khoảng ngày.
- Số subscription active / expiring / expired.
- Check-in theo ngày.
- Revenue theo ngày/tháng.
- Số booking lớp.
- Tỷ lệ attended/no-show.
- Số PT booking.
- Thiết bị đang maintenance/out-of-service.

API dashboard phải nhận:
- `from_date`
- `to_date`
- optional scope/filter.

Cache Redis cho các report read-heavy.

Cache key phải bao gồm scope + filter + time range.

Invalidate cache khi dữ liệu nguồn thay đổi hoặc dùng TTL ngắn.

---

## 18. Database: danh sách bảng tối thiểu

```text
users
roles
user_roles / role field
refresh_tokens
password_reset_tokens

members
membership_plans
membership_subscriptions
subscription_freeze_history

check_ins

class_types
rooms
class_sessions
class_bookings

trainer_profiles
trainer_availability
pt_bookings

payments
invoices

equipment
maintenance_records

notifications
jobs
audit_logs

file_assets (optional)
```

Mọi bảng cần:
- primary key
- created_at
- updated_at nếu phù hợp
- foreign key rõ ràng
- index cho FK và field search/filter thường dùng.

---

## 19. API nhóm endpoint

Prefix mặc định: `/api/v1`

### Auth
```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
POST /auth/forgot-password
POST /auth/reset-password
GET  /auth/me
PATCH /auth/me
```

### Users / RBAC
```text
GET    /users
GET    /users/{id}
PATCH  /users/{id}
PATCH  /users/{id}/role
PATCH  /users/{id}/status
```

### Members
```text
GET    /members
POST   /members
GET    /members/{id}
PATCH  /members/{id}
DELETE /members/{id}
```

### Plans / Subscriptions
```text
GET/POST/PATCH/DELETE /plans
GET  /subscriptions
POST /subscriptions
POST /subscriptions/{id}/renew
POST /subscriptions/{id}/freeze
POST /subscriptions/{id}/unfreeze
POST /subscriptions/{id}/cancel
```

### Check-in
```text
POST /check-ins/qr-token
POST /check-ins
POST /check-ins/{id}/checkout
GET  /check-ins
```

### Classes
```text
GET/POST/PATCH/DELETE /class-types
GET/POST/PATCH/DELETE /class-sessions
POST /class-sessions/{id}/book
POST /class-bookings/{id}/cancel
POST /class-bookings/{id}/attendance
```

### PT
```text
GET    /trainers
GET    /trainers/{id}/availability
PUT    /trainers/me/availability
POST   /pt-bookings
PATCH  /pt-bookings/{id}
POST   /pt-bookings/{id}/cancel
```

### Payments / Invoices
```text
GET  /payments
POST /payments
POST /payments/{id}/mark-paid
POST /payments/{id}/refund

GET  /invoices
POST /invoices
POST /invoices/{id}/issue
POST /invoices/{id}/void
GET  /invoices/{id}/pdf
```

### Equipment
```text
GET/POST/PATCH/DELETE /equipment
GET/POST /equipment/{id}/maintenance
PATCH /maintenance/{id}
```

### Reporting / Import Export
```text
POST /imports/members
GET  /jobs/{id}
POST /exports/members
POST /exports/revenue
GET  /dashboard/summary
```

### Audit
```text
GET /audit-logs
GET /audit-logs/{id}
```

---

## 20. HTTP conventions

- `200` read/update thành công.
- `201` create thành công.
- `202` accepted cho background job.
- `204` delete/no-content.
- `400` request sai nghiệp vụ chung.
- `401` chưa đăng nhập.
- `403` không có quyền.
- `404` không tồn tại.
- `409` conflict/version/concurrency/duplicate state.
- `422` validation.
- `429` rate limit.
- `500` lỗi server không dự kiến.

Error format thống nhất:

```json
{
  "error": {
    "code": "SUBSCRIPTION_EXPIRED",
    "message": "Membership subscription has expired",
    "details": {}
  }
}
```

Không trả stack trace ra production.

---

## 21. Bảo mật

Bắt buộc:

- ORM/parameterized queries để chống SQL injection.
- Escape output và không render HTML không tin cậy.
- CORS allowlist, không dùng `*` ở production với credentials.
- CSRF: nếu dùng cookie auth, phải triển khai CSRF token; nếu Bearer token thuần thì document rõ.
- Rate limit:
  - login
  - forgot password
  - QR check-in
  - export
- Validate upload:
  - extension
  - MIME
  - size
  - randomized storage filename
- Secrets chỉ qua env/secret manager.
- Security headers.
- Không log password/token.
- PII trong log phải hạn chế/mask.
- Authorization test là bắt buộc.

---

## 22. Cache Redis

Cache chỉ dùng cho dữ liệu đọc nhiều:
- active plans
- dashboard aggregates
- report summary
- public/static category data

Không cache dữ liệu nhạy cảm nếu chưa xác định key scope.

Mọi cache key cần version/prefix:
```text
gym:v1:dashboard:{role}:{scope}:{from}:{to}
```

---

## 23. Logging và health check

### 23.1. Structured logging

JSON log tối thiểu:
- timestamp
- level
- service
- request_id
- user_id nếu có
- method
- path
- status_code
- duration_ms
- error_code nếu có

### 23.2. Request ID

Mỗi request nhận/generate `X-Request-ID`, trả lại response và đưa vào log.

### 23.3. Health endpoints

```text
GET /health/live
GET /health/ready
```

`live`: process còn chạy.  
`ready`: kiểm tra dependency cần thiết như DB, Redis.

---

## 24. OpenAPI / Swagger / Postman

- Swagger phải chạy tại `/docs`.
- OpenAPI schema phải mô tả request/response, auth, error.
- Endpoint deprecated phải đánh dấu.
- Tạo Postman collection cho các luồng chính.
- Tạo environment variables cho base URL/token.
- Không commit secret thật.

---

## 25. Testing

Mục tiêu tối thiểu: **30–40% coverage**, ưu tiên service/domain logic.

### 25.1. Unit tests

Bắt buộc test:
- subscription state transition
- freeze days
- expiry
- check-in eligibility
- QR expiry/replay
- class capacity/waitlist
- scheduling conflict
- invoice total
- RBAC service/policy
- optimistic locking nếu có abstraction

### 25.2. Integration tests

Bắt buộc:
- login/refresh
- member CRUD
- plan/subscription flow
- check-in
- class booking/waitlist
- PT booking
- payment + invoice
- import
- export job
- audit log
- forbidden access

### 25.3. E2E acceptance flow

```text
Admin login
 -> create member
 -> create/assign plan
 -> mark payment paid
 -> subscription active
 -> member QR check-in
 -> book class
 -> attendance
 -> book PT
 -> generate invoice/report
 -> verify audit + dashboard
```

---

## 26. Seed data

Tổng seed >= 2.000 record.

Đề xuất:
- 800 members
- 30 plans/plan variants
- 900 subscriptions/history
- 1.500 check-ins
- 100 class sessions
- 500 class bookings
- 30 trainers
- 200 PT bookings
- 500 payments/invoices
- 100 equipment/maintenance records

Không cần tất cả bảng cộng lại chính xác 2.000; yêu cầu là hệ thống có ít nhất 2.000 bản ghi dữ liệu mẫu và có dữ liệu đủ để test dashboard/filter.

Seed phải:
- reproducible bằng fixed random seed
- idempotent hoặc có hướng dẫn reset DB
- không chứa dữ liệu cá nhân thật

---

## 27. Docker / Docker Compose

`docker-compose.yml` tối thiểu:

```text
frontend
backend
postgres
redis
worker
beat
```

Có thể thêm:
```text
mailhog
nginx
```

Yêu cầu:
- `.env.example`
- persistent volume cho PostgreSQL
- healthcheck
- dependency startup hợp lý
- one-command startup:

```bash
docker compose up --build
```

---

## 28. CI/CD

Pipeline tối thiểu:

```text
checkout
 -> backend lint
 -> backend unit/integration tests
 -> frontend lint/typecheck
 -> frontend test
 -> build backend image
 -> build frontend image
 -> optional deploy demo
```

Pull request phải fail nếu test fail.

Không deploy nếu build/test chưa pass.

---

## 29. Backup / Restore

Demo tối thiểu:
- script backup PostgreSQL.
- script restore PostgreSQL.
- hướng dẫn trong `docs/DEPLOYMENT.md`.
- test restore ít nhất một lần trước bàn giao.

---

## 30. Tài liệu bắt buộc

Trong `docs/` phải có:

### `SRS.md`
- mục tiêu
- actors
- functional requirements
- non-functional requirements
- business rules
- acceptance criteria

### `ERD.md`
- entity
- field chính
- quan hệ
- cardinality
- index quan trọng

### `ARCHITECTURE.md`
- component diagram
- request flow
- async job flow
- deployment diagram

### `API.md`
- API conventions
- auth
- error model
- pagination

### `DEPLOYMENT.md`
- prerequisites
- env variables
- Docker
- migration
- seed
- backup/restore

### `USER_GUIDE.md`
Hướng dẫn theo từng vai trò:
- Admin
- Manager
- Trainer
- Member

### `DECISIONS.md`
Ghi ADR ngắn cho các quyết định Codex phải tự chốt trong quá trình code.

---

## 31. Kế hoạch triển khai theo Master Plan

### Sprint 1 — 4 tuần — 07/09/2026 đến 04/10/2026

#### Tuần 1 — Nền tảng hệ thống & tài khoản — deadline 13/09/2026
- Phân tích nghiệp vụ, ERD, database.
- Auth register/login/JWT/reset.
- RBAC.
- UI auth/profile/account management.
- Audit log, soft delete, security baseline.

**Definition of Done**
- Migration chạy từ database rỗng.
- Auth API có test.
- 4 role hoạt động.
- Unauthorized/forbidden được test.
- Có audit skeleton.

#### Tuần 2 — Hội viên, gói tập & check-in — deadline 20/09/2026
- Member CRUD.
- Plan CRUD.
- Subscription lifecycle.
- QR check-in/check-out.
- Expiry job.

**Definition of Done**
- Search/filter/sort/pagination chạy.
- Subscription state test pass.
- QR invalid/replay/expired bị từ chối.
- Job expiry có test.

#### Tuần 3 — Lớp học & PT — deadline 27/09/2026
- Class/session/room.
- Booking/waitlist.
- Trainer profile/availability.
- PT booking.
- Attendance/no-show.

**Definition of Done**
- Capacity không bị oversell khi concurrent request.
- Không double-book trainer/member.
- Waitlist promotion có test.

#### Tuần 4 — Thanh toán, thiết bị & dashboard — deadline 04/10/2026
- Payment.
- Invoice + PDF.
- Equipment + maintenance.
- Dashboard.
- Notification.

**Definition of Done**
- Money dùng Decimal.
- Payment/invoice có audit.
- Dashboard filter theo ngày.
- Redis cache hoạt động.
- Notification worker hoạt động.

### Sprint 2 — 1,5 tuần — 05/10/2026 đến 14/10/2026

#### Import/Export & Reporting — đến 07/10/2026
- Member import Excel/CSV.
- Error per row.
- Export Excel/CSV.
- PDF report.

#### Test/Security/Deployment — đến 14/10/2026
- E2E.
- Regression.
- Coverage 30–40%.
- Security review.
- Docker Compose.
- CI.
- Migration/seed.
- Health check.
- Backup/restore.
- Swagger/Postman.
- Video demo 5–10 phút.

---

## 32. Thứ tự Codex phải thực hiện

Codex không nên generate toàn bộ project một lần.

Làm theo checkpoint:

### Checkpoint 0 — Bootstrap
- scaffold backend/frontend
- Docker Compose
- env/config
- DB connection
- Redis connection
- health endpoints

### Checkpoint 1 — Auth & RBAC
- models
- migrations
- service
- endpoints
- frontend auth
- tests

### Checkpoint 2 — Member / Plan / Subscription
- model -> migration -> repository -> service -> API -> UI -> tests

### Checkpoint 3 — Check-in
- signed QR
- eligibility
- anti-replay
- tests

### Checkpoint 4 — Class / PT
- conflict and capacity rules first
- API
- UI
- tests

### Checkpoint 5 — Payment / Invoice
- Decimal
- transaction
- PDF job
- tests

### Checkpoint 6 — Equipment / Dashboard
- CRUD/maintenance
- aggregates
- Redis cache

### Checkpoint 7 — Import / Export / Notification
- async worker
- job status UI
- row errors

### Checkpoint 8 — Hardening
- audit
- rate limit
- CORS
- upload validation
- structured log
- coverage

### Checkpoint 9 — Release
- seed >= 2.000
- Postman
- docs
- deploy
- backup/restore
- video demo

Mỗi checkpoint phải chạy test trước khi tiếp tục.

---

## 33. Quy tắc code quality

- Service layer chứa business logic; route không chứa logic phức tạp.
- Repository/data-access không quyết định nghiệp vụ.
- Schema request/response tách khỏi ORM model.
- Transaction boundary phải rõ.
- Type hints đầy đủ.
- Không catch `Exception` rồi bỏ qua.
- Centralized exception handling.
- Không duplicate constants/status strings; dùng enum.
- Time lưu UTC; convert timezone ở presentation layer.
- Money: Decimal.
- Date/time conflicts cần test boundary.
- Database constraint phải hỗ trợ application validation, không chỉ tin frontend.

---

## 34. Definition of Done toàn dự án

Project chỉ DONE khi:

- [ ] Register/login/reset hoạt động.
- [ ] RBAC tối thiểu Admin/Manager/Trainer/Member.
- [ ] CRUD chính có search/filter/sort/pagination.
- [ ] Member + plan + subscription lifecycle hoàn chỉnh.
- [ ] QR check-in có validation/replay protection.
- [ ] Class booking có capacity + waitlist.
- [ ] PT booking có conflict detection.
- [ ] Payment + invoice + PDF.
- [ ] Equipment + maintenance.
- [ ] Dashboard + Redis cache.
- [ ] Excel/CSV import/export.
- [ ] PDF report.
- [ ] Audit log.
- [ ] Soft-delete.
- [ ] Versioning/optimistic locking cho record nhạy cảm.
- [ ] Email/in-app notification.
- [ ] Celery jobs.
- [ ] Swagger/OpenAPI.
- [ ] Postman collection.
- [ ] Unit/integration tests.
- [ ] Coverage >= 30%.
- [ ] Seed >= 2.000 records.
- [ ] Docker Compose.
- [ ] CI pipeline.
- [ ] CORS/rate limit/upload/security review.
- [ ] Structured logging.
- [ ] `/health/live` và `/health/ready`.
- [ ] Backup + restore documentation.
- [ ] SRS, ERD, use case/flow, architecture.
- [ ] Setup guide + user guide.
- [ ] Video demo 5–10 phút.

---

## 35. Prompt khởi động dành cho Codex

Khi giao repository cho Codex, dùng instruction sau:

> Hãy triển khai Gym Management System theo `docs/CODEX_IMPLEMENTATION_SPEC.md`. Tài liệu này là source of truth về nghiệp vụ và acceptance criteria. Trước khi code, đọc toàn bộ spec và kiểm tra repository hiện tại. Không rewrite phần đang chạy nếu không cần thiết. Làm từng checkpoint theo mục "Thứ tự Codex phải thực hiện". Với mỗi checkpoint: (1) nêu file sẽ tạo/sửa, (2) triển khai migration/model/service/API/UI tương ứng, (3) viết hoặc cập nhật test, (4) chạy test/lint liên quan, (5) báo kết quả và các decision đã ghi vào `docs/DECISIONS.md`. Không bỏ qua validation, authorization, transaction, audit hoặc test để làm nhanh. Không hard-code secrets. Nếu một chi tiết chưa được quy định, chọn phương án đơn giản và an toàn rồi ghi quyết định. Chỉ chuyển checkpoint khi phần hiện tại chạy được.

---

## 36. Tiêu chí nghiệm thu cuối cùng

Người kiểm thử phải có thể clone repository trên máy mới và thực hiện:

```bash
cp .env.example .env
docker compose up --build
```

Sau đó:
1. mở frontend;
2. login bằng seed Admin;
3. tạo hội viên;
4. mua/gán gói;
5. check-in;
6. đặt lớp;
7. đặt PT;
8. tạo payment/invoice;
9. xem dashboard;
10. export report;
11. kiểm tra audit;
12. mở Swagger;
13. chạy test.  

Nếu một trong các luồng cốt lõi này cần sửa code thủ công hoặc can thiệp DB trực tiếp thì chưa đạt yêu cầu bàn giao.


Các truy vấn cần viết hoàn toàn bằng SQL ko dùng tools, hiểu rõ về backend