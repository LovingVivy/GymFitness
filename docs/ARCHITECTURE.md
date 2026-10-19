# KIẾN TRÚC HỆ THỐNG IRONIX FITNESS

## 1. Tổng quan thành phần

```mermaid
flowchart LR
    browser["Trình duyệt<br/>React SPA"]
    subgraph docker["Docker Compose"]
      nginx["frontend<br/>nginx: file tĩnh + reverse proxy"]
      api["backend<br/>FastAPI (uvicorn)"]
      worker["worker<br/>python -m app.tasks.worker"]
      mysql[("MySQL 8.0<br/>bảng + stored procedure")]
      redis[("Redis<br/>cache · rate limit · hàng đợi")]
      storage[("app_storage<br/>ảnh, file xuất, outbox")]
      mailpit["Mailpit / SMTP"]
    end
    sepay["SePay<br/>webhook ngân hàng"]
    vietqr["img.vietqr.io"]

    browser -->|"/, /assets"| nginx
    browser -->|"/api, /health, /docs"| nginx --> api
    browser -.->|"ảnh QR"| vietqr
    sepay -->|"POST /api/v1/payments/webhooks/sepay"| api
    api -->|"CALL sp_*"| mysql
    api <--> redis
    api --> storage
    worker <-->|"BLPOP gf:jobs"| redis
    worker -->|"CALL sp_*"| mysql
    worker --> storage
    worker -->|SMTP| mailpit
```

| Thành phần | Vai trò |
| --- | --- |
| `frontend` | Phục vụ SPA đã build, chuyển `/api`, `/health`, `/docs` sang backend, gắn header bảo mật |
| `backend` | REST API, kiểm tra quyền, nghiệp vụ, gọi stored procedure, đẩy tác vụ nền |
| `worker` | Chạy tác vụ nền: gửi email, dựng file Excel/CSV/PDF |
| `mysql` | Nguồn dữ liệu duy nhất; mọi truy vấn là stored procedure có transaction |
| `redis` | Cache danh mục/báo cáo, bộ đếm rate limit, hàng đợi id tác vụ |
| `mailpit` | Hộp thư giả lập khi dev/demo (production dùng SMTP thật) |

## 2. Phân lớp backend

```mermaid
flowchart TB
    routes["api/routes<br/>khai báo endpoint, kiểu dữ liệu, quyền (PermissionDep)"]
    deps["api/deps<br/>xác thực JWT, nạp người dùng, kiểm tra quyền"]
    services["services<br/>quy tắc nghiệp vụ, cache, đẩy tác vụ nền"]
    repos["repositories<br/>chỉ CALL stored procedure với tham số bind"]
    core["core<br/>config · security · permissions · cache · rate_limit · logging · pdf · exporters · mailer · totp"]
    tasks["tasks<br/>queue · handlers · worker"]
    db[("MySQL<br/>database/*.sql")]

    routes --> deps
    routes --> services --> repos --> db
    services --> core
    services --> tasks --> services
```

- **Không có câu SQL trong Python.** `repositories/procedures.py` là chỗ duy nhất tạo lệnh `CALL`, tên procedure là hằng số trong code, giá trị luôn là tham số bind (chống SQL injection).
- **Transaction nằm trong procedure.** Các nghiệp vụ tiền và lượt PT khoá dòng (`SELECT … FOR UPDATE`) và ghi sổ cái trong cùng transaction.
- **Lỗi thống nhất.** Mọi lỗi trả `{"error": {"code", "message", "details"}}`; procedure trả `error_code` để service đổi sang HTTP status.

## 3. Vòng đời một request

```mermaid
sequenceDiagram
    participant B as Trình duyệt
    participant N as nginx
    participant M as Middleware
    participant R as Route + quyền
    participant S as Service
    participant DB as MySQL

    B->>N: GET /api/v1/admin/payments?sort=-amount
    N->>M: X-Forwarded-For, X-Request-ID
    M->>M: gắn request_id, rate limit theo IP
    M->>R: chuyển tiếp
    R->>R: giải mã JWT, nạp user, kiểm tra payments:view
    R->>S: list_payments(...)
    S->>DB: CALL sp_admin_payment_list(...)
    DB-->>S: các dòng + total_count
    S-->>R: AdminPaymentPage
    R-->>M: 200 JSON
    M->>M: header bảo mật, log JSON (status, duration_ms, user_id)
    M-->>B: phản hồi + X-Request-ID
```

## 4. Hàng đợi tác vụ

```mermaid
sequenceDiagram
    participant UI as Giao diện quản trị
    participant API as Backend
    participant DB as MySQL (background_jobs)
    participant Q as Redis (gf:jobs)
    participant W as Worker

    UI->>API: POST /admin/exports {report, format, filters}
    API->>API: kiểm tra quyền reports:export + quyền xem báo cáo
    API->>DB: sp_job_create (PENDING)
    API->>Q: RPUSH job_id
    API-->>UI: 202 {id, status: PENDING}
    W->>Q: BLPOP
    W->>DB: sp_job_claim (PENDING → RUNNING, đúng một lần)
    W->>W: dựng file Excel/CSV/PDF
    W->>DB: sp_file_save, sp_job_finish (SUCCESS + file id)
    loop mỗi 0,8 giây
      UI->>API: GET /admin/jobs/{id}
    end
    UI->>API: GET /files/{file_id} (chỉ chủ file)
```

Không có Redis: API chạy tác vụ trong thread pool của chính nó. Worker quét lại tác vụ
`PENDING` quá 2 phút để không mất việc khi Redis hoặc worker khởi động lại (ADR-020).

## 5. Thanh toán tự động

```mermaid
sequenceDiagram
    participant H as Hội viên
    participant API as Backend
    participant DB as MySQL
    participant SP as SePay
    participant W as Worker

    H->>API: POST /subscriptions {plan_id, pt_sessions}
    API->>DB: sp_subscription_create (payment PENDING, mã IRX…)
    API-->>H: mã chuyển khoản + ảnh VietQR
    H->>SP: chuyển khoản bằng app ngân hàng
    SP->>API: webhook (Apikey, nội dung, số tiền)
    API->>DB: ghi payment_event (chống trùng), khớp mã + số tiền
    API->>DB: sp_subscription_mark_paid (gói ACTIVE, cộng lượt PT, sổ cái)
    API->>DB: thông báo trong ứng dụng
    API->>W: tác vụ email.payment_receipt
    W->>DB: sp_invoice_issue (số HDyyyymm-nnnnn)
    W-->>H: email kèm hoá đơn PDF
```

## 6. Bảo mật

| Mối đe doạ | Biện pháp |
| --- | --- |
| Dò mật khẩu | Khoá tài khoản sau 5 lần sai, rate limit 10 req/phút/IP cho đăng nhập, xác thực 2 bước tuỳ chọn |
| Lộ mật khẩu/token | PBKDF2 600.000 vòng; token đặt lại chỉ lưu SHA-256; khoá TOTP mã hoá Fernet |
| Giả mạo phiên | JWT HS256 ký bằng secret ≥ 32 ký tự; token mục đích riêng (`purpose`) không dùng làm phiên |
| SQL injection | Chỉ stored procedure + tham số bind |
| XSS | React escape mặc định; không chèn HTML thô; SVG/QR hiển thị qua `<img>`; CSP cho `/files` |
| CSRF | Không dùng cookie phiên; token gửi bằng header `Authorization` |
| Leo thang quyền | Kiểm tra quyền ở từng route + luật theo dữ liệu trong service (Manager chỉ quản lý hội viên) |
| Truy cập file người khác | `/files/{id}` chỉ trả cho chủ file; hoá đơn kiểm tra chủ giao dịch |
| Lạm dụng API | Rate limit 300 req/phút/IP; webhook ngân hàng xác thực API key |
| Clickjacking, MIME sniffing | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` |

## 7. Cache

| Nhóm | Dữ liệu | TTL | Vô hiệu khi |
| --- | --- | --- | --- |
| `catalog` | Gói tập công khai, sản phẩm, danh sách PT | 300 s | Sửa gói/sản phẩm/tài khoản PT, PT lưu lịch, nhập sản phẩm |
| `reports` | Báo cáo doanh thu, tăng trưởng hội viên | 120 s | Có giao dịch thành công, tạo/xoá tài khoản |

Khoá có dạng `gf:cache:<nhóm>:<phiên bản>:<khoá>`; vô hiệu một nhóm chỉ cần tăng
`gf:cache:ver:<nhóm>` (ADR-021).

## 8. Log và giám sát

- Mỗi request ghi một dòng log `app.access` gồm `method`, `path`, `status`, `duration_ms`, `client_ip`, `user_id`, `request_id`.
- `request_id` lấy từ header `X-Request-ID` (nginx sinh) hoặc tự tạo, trả lại trong phản hồi và gắn vào mọi log trong request.
- `LOG_FORMAT=json` cho production (đọc được bằng Loki/ELK/CloudWatch), `text` cho dev.
- `/health/live`: tiến trình sống. `/health/ready`: MySQL kết nối được (bắt buộc) và trạng thái Redis (`up`/`down`/`disabled`). Docker dùng làm healthcheck.

## 9. Triển khai

```mermaid
flowchart LR
    dev["Lập trình viên<br/>git push main"] --> gh["GitHub Actions"]
    gh -->|"lint, test + coverage, build"| ok{"Xanh?"}
    ok -->|có| ghcr[("GHCR<br/>gymfitness-backend<br/>gymfitness-frontend")]
    ghcr -->|"SSH: compose pull && up -d"| server["Máy chủ<br/>docker-compose.prod.yml"]
```

Chi tiết: [DEPLOYMENT.md](DEPLOYMENT.md).
