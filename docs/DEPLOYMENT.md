# HƯỚNG DẪN TRIỂN KHAI

## 1. Mô hình triển khai

Một máy chủ Linux có Docker chạy `docker-compose.prod.yml`: MySQL, Redis, backend, worker,
frontend (nginx, cổng 80). Image backend/frontend được CI build và đẩy lên GitHub Container
Registry (GHCR); máy chủ chỉ `pull` và khởi động lại. Kiến trúc: [ARCHITECTURE.md](ARCHITECTURE.md).

Nên đặt một reverse proxy có HTTPS phía trước (Caddy, Traefik, nginx + Let's Encrypt hoặc
Cloudflare Tunnel) và đổi `FRONTEND_PORT` sang cổng nội bộ.

## 2. CI/CD (GitHub Actions)

File: `.github/workflows/ci.yml`.

| Job | Chạy khi | Việc làm |
| --- | --- | --- |
| `backend` | Mọi push / pull request | ruff, dựng MySQL, nạp `database/*.sql`, pytest + coverage (chặn khi < 80%) |
| `frontend` | Mọi push / pull request | `npm ci`, `npm run build` |
| `docker` | Sau khi hai job trên xanh | Kiểm tra cú pháp compose, build image backend và frontend |
| `deploy` | Push lên `main` và các job trên xanh | Đẩy image lên GHCR (`latest` + mã commit); nếu có secrets SSH thì cập nhật máy chủ |

Image được đẩy lên:

```text
ghcr.io/<owner>/<repo>-backend:latest
ghcr.io/<owner>/<repo>-frontend:latest
```

Package GHCR mới tạo mặc định là private. Máy chủ cần `docker login ghcr.io` bằng một Personal
Access Token có quyền `read:packages`, hoặc đổi package sang public trong GitHub → Packages.

### Secrets cho bước cập nhật máy chủ (tuỳ chọn)

Khai báo ở GitHub → Settings → Secrets and variables → Actions. Thiếu `DEPLOY_HOST` thì bước SSH được bỏ qua.

| Secret | Ví dụ | Ý nghĩa |
| --- | --- | --- |
| `DEPLOY_HOST` | `203.0.113.10` | Địa chỉ máy chủ |
| `DEPLOY_USER` | `deploy` | Người dùng SSH (thuộc nhóm `docker`) |
| `DEPLOY_SSH_KEY` | nội dung private key | Khoá SSH không mật khẩu dành riêng cho CI |
| `DEPLOY_PATH` | `/opt/gymfitness` | Thư mục chứa `docker-compose.prod.yml` và `.env` (mặc định `/opt/gymfitness`) |

## 3. Chuẩn bị máy chủ lần đầu

1. Cài Docker Engine và Compose v2, tạo thư mục triển khai:

   ```bash
   sudo mkdir -p /opt/gymfitness && sudo chown $USER /opt/gymfitness
   ```

2. Chép lên máy chủ: `docker-compose.prod.yml`, thư mục `database/`, `scripts/apply_sql.py`.

3. Tạo `/opt/gymfitness/.env`:

   | Biến | Ghi chú |
   | --- | --- |
   | `IMAGE_PREFIX` | `ghcr.io/<owner>/<repo>` (chữ thường) |
   | `IMAGE_TAG` | `latest` hoặc mã commit |
   | `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | Mật khẩu mạnh, khác nhau |
   | `JWT_SECRET_KEY` | ≥ 32 ký tự ngẫu nhiên; backend từ chối khởi động nếu yếu |
   | `ADMIN_EMAIL`, `ADMIN_DEFAULT_PASSWORD` | Tài khoản quản trị đầu tiên; đổi mật khẩu sau lần đăng nhập đầu |
   | `FRONTEND_ORIGINS` | `["https://gym.example.com"]` |
   | `FRONTEND_BASE_URL` | `https://gym.example.com` (liên kết trong email) |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM` | SMTP thật (Gmail App Password, Amazon SES, Mailgun...) |
   | `PAYMENT_*`, `SEPAY_WEBHOOK_API_KEY` | Tài khoản nhận tiền và API key webhook SePay |
   | `DOCS_ENABLED` | `false` để ẩn Swagger ở production |

4. Khởi động MySQL rồi nạp schema **không kèm dữ liệu mẫu**:

   ```bash
   docker compose -f docker-compose.prod.yml up -d mysql
   ```

   ```bash
   for f in 01_tables 02_triggers 03_procedures 04_seed 05_procedures_pt 06_procedures_payment 07_pt_schedule 08_admin 09_admin_shop 11_platform; do docker compose -f docker-compose.prod.yml exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/$f.sql; done
   ```

   Ứng dụng nên dùng tài khoản MySQL chỉ có quyền `SELECT, INSERT, UPDATE, DELETE, EXECUTE` trên `gymfitness.*`.

5. Khởi động toàn bộ:

   ```bash
   docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d
   ```

6. Kiểm tra: `curl http://localhost/health/ready` phải trả `{"status":"ready", ...}`.

7. Cấu hình webhook SePay trỏ tới `https://gym.example.com/api/v1/payments/webhooks/sepay`, chứng thực "API Key" trùng `SEPAY_WEBHOOK_API_KEY`.

## 4. Cập nhật phiên bản

Tự động: push lên `main`, job `deploy` làm hết. Thủ công trên máy chủ:

```bash
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

Khi bản mới có thay đổi database, nạp file SQL tương ứng **trước** khi khởi động backend mới
(các file trong `database/` đều chạy lại an toàn).

## 5. Sao lưu và khôi phục

Sao lưu hằng ngày (cron):

```bash
docker compose -f docker-compose.prod.yml exec -T mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers gymfitness' | gzip > backup-$(date +%F).sql.gz
```

Khôi phục:

```bash
gunzip -c backup-YYYY-MM-DD.sql.gz | docker compose -f docker-compose.prod.yml exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" gymfitness'
```

Sao lưu cả volume `app_storage` (ảnh đại diện, file xuất) nếu cần giữ.

## 6. Giám sát

- Log JSON: `docker compose -f docker-compose.prod.yml logs -f backend worker` hoặc gom về Loki/ELK. Tìm theo `request_id` để lần một request qua mọi dòng log.
- Healthcheck Docker dùng `/health/live` (backend) và trang chủ (frontend); dùng `/health/ready` cho công cụ giám sát ngoài (UptimeRobot...).
- Trạng thái tác vụ nền: bảng `background_jobs` (`status = 'FAILED'` kèm `error_message`).
