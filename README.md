# IRONIX Fitness — Hệ thống quản lý phòng tập

Ứng dụng web quản lý phòng Gym/Yoga: đăng ký và thanh toán gói tập bằng VietQR, lịch tập,
đặt huấn luyện viên (PT), cửa hàng, khu quản trị có phân quyền, báo cáo và xuất dữ liệu.

| Thành phần | Công nghệ |
| --- | --- |
| Frontend | React 19, Vite 7 (SPA), nginx khi chạy Docker |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy (chỉ để gọi stored procedure) |
| Database | MySQL 8.0 — toàn bộ truy vấn nằm trong stored procedure (`database/`) |
| Hạ tầng | Redis (cache, rate limit, hàng đợi tác vụ), worker nền, Mailpit (email dev) |
| Chất lượng | pytest + coverage (≈ 93%), ruff, GitHub Actions CI/CD, Postman collection |

## Tính năng chính

- **Tài khoản và bảo mật:** đăng ký/đăng nhập JWT, quên mật khẩu qua email, xác thực 2 bước (TOTP), khoá tạm khi nhập sai nhiều lần, rate limit.
- **Phân quyền (RBAC):** 4 vai trò `ADMIN`, `MANAGER`, `USER`, `PT`; kiểm tra theo màn hình và theo hành động ở backend.
- **Hội viên:** chọn gói Gym/Yoga, thanh toán VietQR (webhook SePay xác nhận tự động), lịch tập, hồ sơ, hoá đơn PDF.
- **PT:** khai lịch làm việc hằng tuần và lịch nghỉ; hội viên đặt ô trống là xác nhận ngay; huỷ/hoàn lượt theo quy tắc; chốt buổi hoàn thành/vắng mặt.
- **Quản trị:** tổng quan, tài khoản, gói tập, cửa hàng, giao dịch, lịch sử ra vào, báo cáo doanh thu/tăng trưởng, nhật ký thao tác.
- **Dữ liệu:** tìm kiếm, lọc, sắp xếp, phân trang; xuất Excel/CSV/PDF chạy nền; nhập sản phẩm từ Excel/CSV; soft-delete; khoá phiên bản (`row_version`); audit log.
- **Vận hành:** log JSON có request id, `/health/live` và `/health/ready`, header bảo mật, Docker Compose, CI/CD đẩy image lên GHCR.

## Chạy nhanh bằng Docker

Cần Docker Desktop (hoặc Docker Engine + Compose v2).

```bash
cp .env.example .env
```

Mở `.env`, đặt `JWT_SECRET_KEY` (chuỗi ngẫu nhiên dài) và `ADMIN_DEFAULT_PASSWORD` (mật khẩu tài khoản `admin`), rồi:

```bash
docker compose up --build
```

| Địa chỉ | Nội dung |
| --- | --- |
| http://localhost:8080 | Giao diện web |
| http://localhost:8080/docs | Swagger (OpenAPI) |
| http://localhost:8025 | Mailpit — xem mọi email hệ thống gửi (đặt lại mật khẩu, hoá đơn...) |

Lần đầu MySQL tự nạp toàn bộ `database/*.sql`, gồm khoảng 11.000 bản ghi mẫu (`10_seed_demo.sql`).
Đăng nhập quản trị bằng tên `admin` và mật khẩu đã đặt trong `.env`.

## Chạy khi phát triển (không Docker)

Hướng dẫn chi tiết từng bước: [docs/INSTALL.md](docs/INSTALL.md). Tóm tắt:

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r backend/requirements-dev.txt
```

```bash
python scripts/apply_sql.py database/01_tables.sql database/02_triggers.sql database/03_procedures.sql database/04_seed.sql database/05_procedures_pt.sql database/06_procedures_payment.sql database/07_pt_schedule.sql database/08_admin.sql database/09_admin_shop.sql database/10_seed_demo.sql database/11_platform.sql
```

```bash
cd backend && uvicorn app.main:app --reload
```

```bash
cd client && npm install && npm run dev
```

Giao diện dev chạy ở http://localhost:5173 và gọi API qua proxy của Vite.

## Kiểm thử

```bash
cd backend && python -m pytest --cov
```

Gồm unit test (`tests/test_unit.py`: phân quyền, TOTP, cache, rate limit, xuất file, PDF...) và
integration test gọi API thật trên MySQL. Coverage tối thiểu cấu hình 80% (hiện ≈ 93%).

## Tài liệu

| Tài liệu | Nội dung |
| --- | --- |
| [docs/SRS.md](docs/SRS.md) | Đặc tả yêu cầu phần mềm (chức năng, phi chức năng, use case) |
| [docs/ERD.md](docs/ERD.md) | Mô hình dữ liệu |
| [docs/USER_FLOWS.md](docs/USER_FLOWS.md) | Luồng nghiệp vụ |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Sơ đồ kiến trúc, luồng request, hàng đợi, bảo mật |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Các quyết định kiến trúc (ADR) |
| [docs/INSTALL.md](docs/INSTALL.md) | Hướng dẫn cài đặt môi trường dev |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Triển khai production, CI/CD |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Hướng dẫn sử dụng cho từng vai trò |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Kịch bản quay video demo 5–10 phút |
| [docs/postman/](docs/postman/GymFitness.postman_collection.json) | Postman collection cho toàn bộ API |
| [database/README.md](database/README.md) | Thứ tự nạp SQL, stored procedure, dữ liệu mẫu |
| [backend/README.md](backend/README.md) | Cấu trúc backend, test, worker |

## Cấu trúc thư mục

```text
backend/          FastAPI: api (route), services (nghiệp vụ), repositories (gọi procedure),
                  core (config, bảo mật, cache, rate limit, log, PDF/Excel), tasks (hàng đợi, worker)
client/           React SPA, Dockerfile + nginx.conf
database/         01…11 *.sql: bảng, trigger, stored procedure, dữ liệu mẫu, migration
docs/             Tài liệu dự án và Postman collection
scripts/          apply_sql.py (nạp file SQL có DELIMITER)
.github/workflows CI/CD
```
