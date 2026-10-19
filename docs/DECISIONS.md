# ARCHITECTURE DECISIONS

## ADR-001 — MySQL 8.0+ là database chính

- **Trạng thái:** Accepted
- **Quyết định:** Dùng MySQL 8.0+, `CHAR(36)` primary key do ứng dụng sinh và `DATETIME(6)` lưu UTC.
- **Lý do:** Phù hợp lựa chọn công nghệ của dự án; InnoDB cung cấp transaction và foreign key, JSON lưu metadata linh hoạt.

## ADR-002 — Ba vai trò hệ thống

- **Trạng thái:** Superseded bởi ADR-019 (thêm vai trò `MANAGER`)
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

## ADR-016 — Khu quản trị và tài khoản admin mặc định

- **Trạng thái:** Accepted
- **Quyết định:** Trang `/admin` (role `ADMIN`) gồm doanh thu theo tuần/tháng/quý/năm, quản lý tài khoản, gói tập và lịch sử ra vào. Đăng nhập nhận email hoặc `users.username`. Admin mặc định được tạo khi backend khởi động từ biến môi trường, chỉ khi chưa tồn tại; mật khẩu nằm trong `backend/.env`, không nằm trong seed hay code. Xoá tài khoản là xoá mềm và giải phóng email/sđt để đăng ký lại; không xoá được admin cuối cùng, chính mình, hoặc tài khoản còn buổi PT sắp tới. Xoá gói là xoá mềm + ngừng bán; đổi giá chỉ áp dụng cho lượt mua mới. Doanh thu chỉ tính payment `PAID`, gom theo giờ phòng tập và tách phần PT của payment gộp (ADR-014).
- **Lý do:** Repo công khai nên mật khẩu/hash admin không được commit. Xoá mềm giữ nguyên lịch sử thanh toán, gói tập và buổi PT cho báo cáo; mọi thao tác ghi của admin được lưu `audit_logs` để truy vết.

## ADR-017 — Phạm vi quản trị: gói tập, cửa hàng, thanh toán, báo cáo, tài khoản

- **Trạng thái:** Accepted
- **Quyết định:** Bỏ khỏi phạm vi các module phòng tập (`rooms`) và thiết bị/bảo trì (`equipment`, `maintenance_records`); bảng vẫn nằm trong schema nhưng không có API hay giao diện. Trang `/admin` gồm: Báo cáo (doanh thu, số lượng hội viên, mức tăng trưởng theo tuần/tháng/quý/năm), Tài khoản, Gói tập, Cửa hàng, Thanh toán, Ra vào. Cửa hàng quản lý sản phẩm với một biến thể mặc định (SKU, giá, tồn kho); mọi thay đổi tồn kho ghi vào `inventory_movements`; trang `/products` đọc từ database. Thanh toán: admin xem mọi giao dịch, xác nhận thủ công giao dịch `PENDING` (kích hoạt quyền lợi bằng đúng procedure của webhook) hoặc huỷ nó (`VOID`, kèm huỷ gói/lượt PT đang chờ). Tăng trưởng hội viên tính trên tài khoản `USER` chưa xoá theo ngày đăng ký. Tài khoản quản trị mặc định là `admin@gmail.com` (tên đăng nhập `admin`); mật khẩu vẫn chỉ đặt trong `backend/.env` theo ADR-016.
- **Lý do:** Chủ dự án thu hẹp phạm vi. Xác nhận thủ công đi qua cùng procedure với webhook nên không có hai đường kích hoạt quyền lợi khác nhau (ADR-004); hoàn tiền và đơn hàng chưa làm vì chưa có luồng đặt hàng phía hội viên.

## ADR-018 — Gói tập quyết định PT được đặt

- **Trạng thái:** Accepted
- **Quyết định:** Hội viên chỉ đặt được PT có chuyên môn (`trainer_specialties`) trùng loại hình `GYM`/`YOGA` của một gói hội viên còn hiệu lực trong giờ tập. `GET /trainers/bookable` trả đúng danh sách đó; `sp_pt_session_book` kiểm tra lại và trả `TRAINER_MISMATCH` nếu sai loại hình. Hội viên có cả gói Gym và Yoga thì đặt được cả hai nhóm PT; buổi tập gắn với gói khớp chuyên môn. Trang Lịch tập không còn danh sách PT mẫu: nút "Chọn PT" đọc PT và giờ trống thật, đặt qua cùng API với trang Đặt PT. Trang quản trị cảnh báo PT chưa khai lịch làm việc vì hội viên chưa thấy PT đó (ADR-015).
- **Lý do:** Chuyên môn do admin gán khi tạo tài khoản PT phải có hiệu lực thật; trước đây bộ lọc Gym/Yoga chỉ nằm ở giao diện và gói Gym vẫn đặt được PT Yoga. Danh sách PT mẫu ở Lịch tập khiến PT mới tạo không bao giờ xuất hiện và "yêu cầu" chỉ lưu trong trình duyệt.

## ADR-019 — RBAC bốn vai trò, phân quyền theo màn hình và hành động

- **Trạng thái:** Accepted
- **Quyết định:** Thêm vai trò `MANAGER` (CHECK `chk_users_role`, migration trong `11_platform.sql`). Quyền là danh sách `Permission` cố định trong `app/core/permissions.py`, gán theo vai trò; mỗi route khai báo quyền nó cần (`PermissionDep(...)`), service thêm luật theo dữ liệu (Manager chỉ tạo/sửa/đặt lại mật khẩu tài khoản `USER`). Danh sách quyền được trả trong `/auth/login` và `/profile` để frontend ẩn/hiện tab và nút. Manager: báo cáo, xuất dữ liệu, hội viên, check-in, xác nhận thu tiền, cửa hàng; không: tài khoản nhân sự, xoá tài khoản, sửa gói tập, huỷ giao dịch, nhật ký thao tác.
- **Lý do:** Yêu cầu tối thiểu 3 vai trò Admin/Manager/User và phân quyền theo màn hình lẫn hành động. Quyền cố định trong code (không lưu bảng) đủ cho quy mô dự án, dễ kiểm thử và không thể bị sửa sai qua giao diện.

## ADR-020 — Hàng đợi tác vụ: MySQL giữ trạng thái, Redis chuyển tin

- **Trạng thái:** Accepted
- **Quyết định:** Tác vụ lâu (gửi email, xuất báo cáo) được ghi vào `background_jobs` rồi đẩy id sang Redis (`gf:jobs`); tiến trình `python -m app.tasks.worker` nhận và chạy. `sp_job_claim` chỉ chuyển `PENDING → RUNNING` một lần nên không chạy trùng. Worker chạy bù tác vụ `PENDING` quá 2 phút. Không có Redis thì API chạy tác vụ trong thread pool (`JOB_QUEUE_MODE=auto`); bộ test dùng `inline`. Token đặt lại mật khẩu được sinh ngay trong tác vụ gửi mail nên token gốc không bao giờ nằm trong `background_jobs`.
- **Lý do:** Không thêm thư viện hàng đợi (Celery/RQ không chạy được trên Windows của nhóm), tận dụng bảng có sẵn trong schema, trạng thái tác vụ xem được bằng SQL và qua API.

## ADR-021 — Cache và rate limit dùng Redis, có dự phòng trong bộ nhớ

- **Trạng thái:** Accepted
- **Quyết định:** Cache đọc-xuyên (read-through) cho danh mục công khai (gói tập, sản phẩm, PT) và báo cáo doanh thu/tăng trưởng. Mỗi nhóm có số phiên bản trong khoá; thao tác ghi liên quan tăng phiên bản để vô hiệu cả nhóm (không quét khoá). Rate limit cửa sổ cố định theo IP: 10 request/phút cho đăng nhập, đăng ký, quên/đặt lại mật khẩu, xác minh 2FA; 300 request/phút cho phần còn lại; webhook ngân hàng được miễn. Redis không kết nối được thì cả hai dùng bộ nhớ của tiến trình, thử kết nối lại sau 30 giây.
- **Lý do:** Đáp ứng yêu cầu cache/rate limit mà không bắt máy dev phải có Redis; dùng chung Redis với hàng đợi tác vụ.

## ADR-022 — Versioning: khoá lạc quan bằng `row_version` và lịch sử trong audit log

- **Trạng thái:** Accepted
- **Quyết định:** Gói tập và sản phẩm (dữ liệu ảnh hưởng giá) nhận `row_version` từ client khi sửa; procedure so với bản hiện tại và trả `VERSION_CONFLICT` (409) nếu người khác vừa sửa. Mọi thao tác ghi của quản trị lưu `before_data`/`after_data` vào `audit_logs`, xem được ở tab Nhật ký và `GET /admin/audit-logs` như lịch sử phiên bản của bản ghi.
- **Lý do:** Tránh ghi đè âm thầm khi hai người cùng sửa; lịch sử thay đổi có sẵn mà không cần bảng `*_versions` riêng.

## ADR-023 — Xuất/nhập dữ liệu, hoá đơn PDF và email

- **Trạng thái:** Accepted
- **Quyết định:** Xuất CSV (UTF-8 có BOM cho Excel), Excel (`openpyxl`, giữ kiểu số/ngày) và PDF (`reportlab`) từ cùng một định nghĩa cột; chạy trong hàng đợi tác vụ, file lưu riêng tư và chỉ người yêu cầu tải được qua `/files/{id}`. Nhập sản phẩm từ `.xlsx`/`.csv` theo SKU, lưu từng dòng và báo lỗi theo số dòng. Mỗi payment đã thu có một hoá đơn (`invoices`, số `HDyyyymm-nnnnn`), PDF dựng khi cần và gửi kèm email biên nhận. PDF dùng font DejaVu Sans (Docker) hoặc Arial để có dấu tiếng Việt. Email gửi qua SMTP; dev/demo dùng Mailpit, không cấu hình SMTP thì ghi ra `storage/outbox`.
- **Lý do:** Đáp ứng yêu cầu nhập/xuất Excel/CSV, xuất PDF hoá đơn/báo cáo và thông báo email với ít thư viện nhất có thể.

## ADR-024 — Xác thực 2 bước TOTP và đặt lại mật khẩu bằng token một lần

- **Trạng thái:** Accepted
- **Quyết định:** TOTP chuẩn RFC 6238 (tự cài đặt, SHA-1, 6 số, bước 30 giây, lệch ±1 bước); khoá lưu mã hoá Fernet bằng khoá dẫn xuất từ `JWT_SECRET_KEY`. Đăng nhập tài khoản có 2FA trả `challenge_token` có `purpose`, không dùng được như access token. Token đặt lại mật khẩu ngẫu nhiên 256 bit, chỉ lưu SHA-256, một lần, 30 phút; endpoint quên mật khẩu luôn trả 202. Refresh token và đăng nhập OAuth2 bên thứ ba chưa làm: access token JWT 30 phút đáp ứng yêu cầu "JWT/OAuth2".
- **Lý do:** 2FA là mục tuỳ chọn nhưng tăng bảo mật cho tài khoản quản trị; không cần thư viện ngoài.

## ADR-025 — Sắp xếp danh sách bằng xếp hạng ROW_NUMBER

- **Trạng thái:** Accepted
- **Quyết định:** Các procedure danh sách quản trị nhận `p_sort` (tên cột, tiền tố `-` là giảm dần, chỉ nhận giá trị trong whitelist ở API) và xếp hạng bằng `ROW_NUMBER() OVER (...)` trong bảng dẫn xuất rồi sắp theo một cột số.
- **Lý do:** Cách viết `ORDER BY CASE ... END` nhiều khoá làm MySQL 8.0 sập (lỗi filesort) khi procedure chạy lại trong cùng kết nối với `LIMIT` khác; xếp hạng bằng window function tránh được lỗi và không cần SQL động.
