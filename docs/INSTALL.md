# HƯỚNG DẪN CÀI ĐẶT

Có hai cách chạy dự án. Cách 1 nhanh nhất, chỉ cần Docker. Cách 2 dùng khi phát triển, chạy
trực tiếp trên máy (Windows, macOS, Linux).

## Cách 1 — Docker (khuyên dùng để chạy thử, demo)

Yêu cầu: Docker Desktop (Windows/macOS) hoặc Docker Engine + Compose v2 (Linux).

1. Tạo file cấu hình:

   ```bash
   cp .env.example .env
   ```

2. Mở `.env` và đặt ít nhất:

   | Biến | Ý nghĩa |
   | --- | --- |
   | `JWT_SECRET_KEY` | Chuỗi ngẫu nhiên ≥ 32 ký tự: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
   | `ADMIN_DEFAULT_PASSWORD` | Mật khẩu tài khoản quản trị `admin`, tạo khi backend khởi động lần đầu |
   | `PAYMENT_BANK_CODE`, `PAYMENT_ACCOUNT_NO`, `PAYMENT_ACCOUNT_NAME` | Tuỳ chọn: tài khoản nhận tiền để hiện ảnh VietQR |

3. Khởi động:

   ```bash
   docker compose up --build
   ```

   Lần đầu mất vài phút: build image, MySQL nạp `database/01…12` (gồm ≈ 11.000 bản ghi mẫu).

4. Mở:

   | Địa chỉ | Nội dung |
   | --- | --- |
   | http://localhost:8080 | Giao diện |
   | http://localhost:8080/docs | Swagger |
   | http://localhost:8025 | Mailpit — email đặt lại mật khẩu, hoá đơn... |

5. Dừng: `Ctrl+C` rồi `docker compose down`. Xoá sạch dữ liệu để nạp lại từ đầu: `docker compose down -v`.

> MySQL chỉ tự nạp file SQL khi volume `mysql_data` được tạo lần đầu. Sau khi cập nhật mã nguồn
> có file SQL mới, chạy `docker compose down -v` (mất dữ liệu) hoặc nạp file mới bằng
> `scripts/apply_sql.py` như cách 2.

## Cách 2 — Chạy trực tiếp khi phát triển

### Yêu cầu

| Phần mềm | Phiên bản |
| --- | --- |
| Python | 3.12 |
| Node.js | 20 trở lên |
| MySQL Server | 8.0 |
| Redis | Không bắt buộc (không có thì cache/rate limit chạy trong bộ nhớ, tác vụ nền chạy trong luồng của API) |

### Bước 1 — Database

Tạo database và (khuyên dùng) tài khoản riêng cho ứng dụng bằng tài khoản root:

```sql
CREATE DATABASE gymfitness CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'gymfitness_app'@'localhost' IDENTIFIED BY 'mat_khau_manh';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON gymfitness.* TO 'gymfitness_app'@'localhost';
```

Nạp schema, procedure và dữ liệu mẫu (cần quyền tạo bảng/procedure, dùng root hoặc tài khoản có quyền DDL).
Cấu hình kết nối lấy từ `backend/.env` (bước 2) hoặc biến môi trường `MYSQL_*`:

```bash
python scripts/apply_sql.py database/01_tables.sql database/02_triggers.sql database/03_procedures.sql database/04_seed.sql database/05_procedures_pt.sql database/06_procedures_payment.sql database/07_pt_schedule.sql database/08_admin.sql database/09_admin_shop.sql database/10_seed_demo.sql database/11_platform.sql database/12_lifecycle.sql
```

`10_seed_demo.sql` là dữ liệu mẫu, có thể bỏ. Database đã có từ trước chỉ cần nạp lại các file
đã thay đổi (các file đều chạy lại an toàn), ví dụ `03_procedures.sql`, `07_pt_schedule.sql`, `08_admin.sql`, `09_admin_shop.sql`,
`11_platform.sql`, `12_lifecycle.sql`.

### Bước 2 — Backend

```bash
python -m venv .venv
```

Kích hoạt môi trường ảo (Windows PowerShell: `.venv\Scripts\Activate.ps1`, macOS/Linux: `source .venv/bin/activate`), rồi:

```bash
python -m pip install -r backend/requirements-dev.txt
```

```bash
cp backend/.env.example backend/.env
```

Sửa `backend/.env`: thông tin `MYSQL_*`, `JWT_SECRET_KEY`, `ADMIN_DEFAULT_PASSWORD`. Chạy API:

```bash
cd backend && uvicorn app.main:app --reload
```

API chạy ở http://localhost:8000, Swagger ở http://localhost:8000/docs.

Nếu có Redis và muốn tác vụ nền chạy ở tiến trình riêng (giống production), mở thêm một terminal:

```bash
cd backend && python -m app.tasks.worker
```

API tự chạy bảo trì định kỳ mỗi 5 phút (chuyển gói hết hạn, nhắc gia hạn, tự đóng buổi PT
quá hạn). Khi đã chạy worker riêng có thể đặt `MAINTENANCE_IN_API=false`.

Không cấu hình `SMTP_HOST` thì email được ghi ra `backend/storage/outbox/*.eml` (mở bằng Outlook/Thunderbird hoặc trình soạn thảo).

### Bước 3 — Frontend

```bash
cd client && npm install && npm run dev
```

Mở http://localhost:5173. Vite chuyển các request `/api` sang `http://localhost:8000`.

### Bước 4 — Kiểm thử

Bộ test cần MySQL đã nạp đủ file SQL (nên dùng database riêng cho test):

```bash
cd backend && python -m pytest --cov
```

```bash
cd backend && python -m ruff check . && python -m ruff format --check .
```

## Tài khoản dùng thử

| Tài khoản | Mật khẩu | Vai trò |
| --- | --- | --- |
| `admin` (hoặc `ADMIN_EMAIL`) | Giá trị `ADMIN_DEFAULT_PASSWORD` | Quản trị |
| `pt.gym@ironix.vn`, `pt.yoga@ironix.vn` | Xem `database/README.md` | Huấn luyện viên |
| Tự đăng ký ở `/signup` | Tự đặt | Hội viên |

Quản lý (`MANAGER`): đăng nhập quản trị → Tài khoản → Thêm tài khoản → chọn vai trò **Quản lý**.
Tài khoản mẫu trong `10_seed_demo.sql` không đăng nhập được; muốn dùng thì đặt lại mật khẩu ở trang quản trị.

## Sự cố thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `JWT_SECRET_KEY chưa được cấu hình an toàn` | Đặt chuỗi ≥ 32 ký tự hoặc chạy với `APP_ENV=development` |
| `PROCEDURE ... does not exist` hoặc sai số tham số | Nạp lại file SQL tương ứng (`03`, `07`, `08`, `09`, `11`, `12`) |
| `Redis không khả dụng, dùng chế độ dự phòng` trong log | Bình thường khi không chạy Redis; API vẫn hoạt động |
| PDF không có dấu tiếng Việt | Đặt `PDF_FONT_PATH` tới một file `.ttf` có tiếng Việt (DejaVuSans, Arial) |
| Không thấy email đặt lại mật khẩu | Docker: xem http://localhost:8025. Không Docker: xem `backend/storage/outbox` |
