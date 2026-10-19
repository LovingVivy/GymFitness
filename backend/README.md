# GymFitness Backend

Backend dùng FastAPI, SQLAlchemy 2, PyMySQL, Alembic, MySQL và Redis. Cấu trúc hiện tại là nền móng cho các module auth, hội viên, lịch tập, PT, QR check-in, thanh toán và bán hàng.

## Cấu trúc

- app/api: route HTTP, xác thực và kiểm tra quyền (`deps.py`)
- app/core: cấu hình, bảo mật (JWT, PBKDF2, TOTP), phân quyền, cache, rate limit, log JSON, PDF/Excel/CSV, email
- app/db: engine và session MySQL
- app/models: SQLAlchemy models (tham chiếu schema; truy vấn đi qua stored procedure)
- app/repositories: chỉ gọi stored procedure
- app/services: nghiệp vụ
- app/schemas: request và response models
- app/tasks: hàng đợi tác vụ (`queue.py`), handler (`handlers.py`), worker (`worker.py`)
- migrations: migration Alembic
- tests: unit test (`test_unit.py`) và integration test gọi API thật

## Chạy bằng Python trên máy

Từ thư mục gốc dự án:

~~~powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
Copy-Item backend\.env.example backend\.env
cd backend
uvicorn app.main:app --reload
~~~

Sửa tài khoản MySQL trong backend/.env trước khi chạy. Database và bảng phải được tạo bằng database/01_tables.sql rồi database/02_triggers.sql.

Nếu muốn tạo riêng tài khoản cho ứng dụng, chạy bằng tài khoản MySQL root:

~~~sql
CREATE USER IF NOT EXISTS 'gymfitness_app'@'localhost' IDENTIFIED BY 'mat_khau_manh';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE
ON gymfitness.*
TO 'gymfitness_app'@'localhost';
FLUSH PRIVILEGES;
~~~

Sau đó đặt MYSQL_USER và MYSQL_PASSWORD tương ứng trong backend/.env.

## Worker tác vụ nền

Email (đặt lại mật khẩu, hoá đơn, huỷ buổi PT) và xuất báo cáo chạy qua hàng đợi tác vụ.
Có Redis thì chạy worker ở terminal riêng:

~~~powershell
cd backend
python -m app.tasks.worker
~~~

Không có Redis (`JOB_QUEUE_MODE=auto`), API tự chạy tác vụ trong luồng nền, không cần worker.

## Chạy bằng Docker

Từ thư mục gốc dự án:

~~~powershell
Copy-Item .env.example .env
docker compose up --build
~~~

Docker Compose chạy MySQL, Redis, backend, worker, frontend (http://localhost:8080) và Mailpit (http://localhost:8025). MySQL trong Docker dùng cổng 3307 trên máy để không xung đột với MySQL cục bộ ở cổng 3306. Các file trong database/ chỉ tự chạy khi volume mysql_data được tạo lần đầu.

## Endpoint nền tảng

- GET /health/live: tiến trình API đang hoạt động
- GET /health/ready: API kết nối được MySQL, kèm trạng thái Redis
- GET /docs: Swagger UI trong môi trường development

## Kiểm thử

~~~powershell
cd backend
python -m pytest
python -m pytest --cov
python -m ruff check .
~~~

Bộ test là integration test: gọi API thật trên MySQL thật vì mọi truy vấn nằm trong stored procedure. Cần nạp đủ các file trong `database/` trước khi chạy.

`--cov` in độ phủ của package `app` (cấu hình trong `pyproject.toml`) và báo lỗi nếu độ phủ dưới 80%.

## CI

`.github/workflows/ci.yml` chạy trên mỗi lần push lên `main` và mỗi pull request:

- **Backend:** `ruff check`, `ruff format --check`, dựng MySQL 8.0, nạp toàn bộ file trong `database/`, chạy `pytest --cov` và lưu `coverage.xml` làm artifact.
- **Frontend:** `npm ci` và `npm run build` trong `client/`.
- **Docker:** build image backend từ `backend/Dockerfile`.

## Postman

`docs/postman/GymFitness.postman_collection.json` có request cho mọi endpoint, xếp theo thứ tự chạy được từ trên xuống (đăng ký → gói tập → đặt PT → quản trị). Hướng dẫn nằm trong phần mô tả của collection.

## Migration

Schema hiện tại được bootstrap bằng hai file SQL trong database. Từ checkpoint backend tiếp theo, mọi thay đổi schema mới được tạo qua Alembic:

~~~powershell
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
~~~

Không chạy autogenerate cho đến khi các SQLAlchemy model đã phản ánh đầy đủ schema hiện tại, nếu không Alembic có thể đề xuất xóa các bảng bootstrap chưa được map.
