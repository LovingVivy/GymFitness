# GymFitness Backend

Backend dùng FastAPI, SQLAlchemy 2, PyMySQL, Alembic, MySQL và Redis. Cấu trúc hiện tại là nền móng cho các module auth, hội viên, lịch tập, PT, QR check-in, thanh toán và bán hàng.

## Cấu trúc

- app/api: route HTTP
- app/core: cấu hình ứng dụng
- app/db: engine và session MySQL
- app/models: SQLAlchemy models
- app/repositories: truy cập dữ liệu
- app/services: nghiệp vụ
- app/schemas: request và response models
- app/tasks: tác vụ nền và nhắc gia hạn
- migrations: migration Alembic
- tests: kiểm thử backend

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

## Chạy bằng Docker

Từ thư mục gốc dự án:

~~~powershell
Copy-Item .env.example .env
docker compose up --build
~~~

MySQL trong Docker dùng cổng 3307 trên máy để không xung đột với MySQL cục bộ ở cổng 3306. Hai file SQL hiện tại chỉ tự chạy khi volume mysql_data được tạo lần đầu.

## Endpoint nền tảng

- GET /health/live: tiến trình API đang hoạt động
- GET /health/ready: API kết nối được MySQL
- GET /docs: Swagger UI trong môi trường development

## Kiểm thử

~~~powershell
cd backend
python -m pytest
python -m ruff check .
~~~

## Migration

Schema hiện tại được bootstrap bằng hai file SQL trong database. Từ checkpoint backend tiếp theo, mọi thay đổi schema mới được tạo qua Alembic:

~~~powershell
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
~~~

Không chạy autogenerate cho đến khi các SQLAlchemy model đã phản ánh đầy đủ schema hiện tại, nếu không Alembic có thể đề xuất xóa các bảng bootstrap chưa được map.
