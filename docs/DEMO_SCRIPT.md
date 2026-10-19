# KỊCH BẢN VIDEO DEMO (≈ 8 phút)

Mục tiêu: trong một video ngắn, chứng minh từng nhóm yêu cầu của bài tập lớn bằng thao tác
thật trên hệ thống. Mỗi cảnh ghi rõ cần chuẩn bị gì, làm gì và nói gì.

## Chuẩn bị trước khi quay

1. `docker compose down -v && docker compose up --build` để có dữ liệu mẫu mới (≈ 11.000 bản ghi).
2. Mở sẵn các tab trình duyệt: http://localhost:8080, http://localhost:8080/docs, http://localhost:8025 (Mailpit), trang Actions của repo GitHub.
3. Đăng nhập admin, tạo sẵn một tài khoản **Quản lý** (tab Tài khoản → Thêm → Quản lý).
4. Cài Google Authenticator trên điện thoại.
5. Chuẩn bị file `san-pham.xlsx` từ **File mẫu** với 2–3 dòng, cố ý để 1 dòng sai (Nhóm = `BOXING`).
6. Phóng to trình duyệt 110–125% cho dễ nhìn; tắt thông báo hệ điều hành.

## Cảnh quay

| # | Thời lượng | Cảnh | Thao tác | Lời thoại gợi ý |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:30 | Giới thiệu | Trang chủ, lướt nhanh Sản phẩm | "IRONIX là hệ thống quản lý phòng tập Gym/Yoga gồm React, FastAPI, MySQL, Redis chạy bằng Docker Compose." |
| 2 | 0:30–1:30 | Hội viên mua gói | Đăng ký tài khoản mới → chọn gói Gym năm + 3 buổi PT → màn hình VietQR → bấm **Giả lập đã nhận tiền (dev)** → tải hoá đơn PDF → mở Mailpit thấy email hoá đơn | "Thanh toán xác nhận qua webhook ngân hàng; ở dev dùng nút giả lập. Hoá đơn PDF có số HD và gửi qua email bằng hàng đợi tác vụ." |
| 3 | 1:30–2:30 | Đặt PT | Đặt PT → chọn PT Gym → chọn ô trống → buổi xác nhận ngay; đăng nhập PT xem buổi dạy và thông báo | "PT khai lịch tuần, hội viên đặt ô trống là xác nhận ngay, lượt PT được giữ trong sổ cái." |
| 4 | 2:30–3:30 | Bảo mật | Đăng xuất → **Quên mật khẩu?** → Mailpit mở email → đặt mật khẩu mới. Vào Hồ sơ → **Bật xác thực 2 bước** → quét QR → đăng nhập lại nhập mã 6 số | "Đặt lại mật khẩu bằng token một lần, chỉ lưu bản băm. 2FA chuẩn TOTP. Đăng nhập sai nhiều lần bị khoá và có rate limit." |
| 5 | 3:30–4:45 | Quản trị: CRUD + dữ liệu lớn | Admin → Tài khoản: tìm "nguyen", lọc Hội viên, bấm tiêu đề cột để sắp xếp, chuyển trang. Thanh toán: lọc Đã thu, sắp xếp theo số tiền, **Xuất file → Excel** mở file | "Dữ liệu mẫu hơn 11.000 bản ghi. Tìm kiếm, lọc, sắp xếp, phân trang ở database. Xuất file chạy nền rồi tự tải về." |
| 6 | 4:45–5:30 | Nhập Excel + versioning | Cửa hàng → **Nhập Excel/CSV** → chọn file mẫu đã sửa → hộp kết quả báo 1 dòng lỗi. Mở 2 tab cùng sửa một gói tập → tab thứ hai báo "vừa được người khác sửa" | "Nhập theo SKU, báo lỗi từng dòng. Khoá lạc quan bằng row_version chống ghi đè." |
| 7 | 5:30–6:15 | Phân quyền | Đăng nhập Quản lý: chỉ 6 tab, không có Nhật ký, gói tập chỉ xem, không có nút Huỷ giao dịch. Mở Swagger gọi `DELETE /admin/users/{id}` bằng token quản lý → 403 | "RBAC theo màn hình và theo hành động, backend kiểm tra lại mọi request." |
| 8 | 6:15–6:45 | Audit log | Admin → **Nhật ký** → mở **Trước / sau** của lần sửa gói tập | "Ai làm gì, lúc nào, dữ liệu trước và sau — cũng là lịch sử phiên bản." |
| 9 | 6:45–7:30 | Vận hành | Swagger `/docs`; Postman chạy collection; terminal `docker compose logs backend` thấy log JSON có `request_id`; gọi `/health/ready` | "OpenAPI đầy đủ, Postman 80+ request, log có cấu trúc và health check." |
| 10 | 7:30–8:00 | Chất lượng + CI/CD | Trang GitHub Actions: các job backend/frontend/docker/deploy xanh, báo cáo coverage ≈ 93% | "Unit test và integration test, coverage trên 90%, CI build, test và đẩy image lên GHCR." |

## Mẹo quay

- Quay bằng OBS hoặc Xbox Game Bar (`Win + G`), 1080p, 30 fps.
- Thu thoại riêng rồi ghép nếu môi trường ồn.
- Cắt các đoạn chờ build/khởi động; giữ mỗi cảnh dưới 1 phút.
- Che hoặc làm mờ mật khẩu, khoá 2FA và API key nếu chúng xuất hiện trên màn hình.
