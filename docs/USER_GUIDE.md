# HƯỚNG DẪN SỬ DỤNG IRONIX FITNESS

Mục lục: [Hội viên](#1-hội-viên) · [Huấn luyện viên](#2-huấn-luyện-viên-pt) ·
[Quản lý](#3-quản-lý-manager) · [Quản trị](#4-quản-trị-admin) · [Bảo mật tài khoản](#5-bảo-mật-tài-khoản-cho-mọi-vai-trò)

## 1. Hội viên

### 1.1. Đăng ký và mua gói

1. Vào **Gói tập** (`/plans`), chọn Gym hoặc Yoga, theo tháng hoặc theo năm. Có thể mua kèm buổi PT.
2. Chưa có tài khoản: hệ thống chuyển sang **Đăng ký**, giữ lại gói đã chọn.
3. Màn hình thanh toán hiện mã VietQR. Mở ứng dụng ngân hàng, quét mã, **giữ nguyên nội dung chuyển khoản**.
4. Khi ngân hàng báo tiền về (thường vài giây), màn hình chuyển sang "Đã nhận". Gói được kích hoạt ngay.
5. Hoá đơn PDF được gửi vào email; bấm **Tải hoá đơn PDF** để tải lại.

### 1.2. Lịch tập và hồ sơ

- **Lịch tập** (`/schedule`): lịch theo tháng của gói đang dùng.
- **Hồ sơ** (`/profile`): ảnh đại diện, gói hiện tại và số ngày còn lại, thông tin thể chất, bảo mật tài khoản.

### 1.3. Đặt buổi với huấn luyện viên

1. Vào **Đặt PT** (`/pt-booking`). Chưa có lượt thì chọn số buổi, bấm **Mua … buổi** và thanh toán như mua gói (đang chọn sẵn một ô giờ thì nút là **Mua … buổi & đặt giờ này**).
2. Chọn PT. Chỉ hiện PT có chuyên môn trùng loại hình gói của bạn (gói Gym → PT Gym).
3. Chọn một ô giờ còn trống (đặt trước ít nhất 2 giờ, tối đa 14 ngày). Buổi được **xác nhận ngay**, 1 lượt được giữ lại.
4. Huỷ buổi trước giờ tập **ít nhất 12 giờ** thì được hoàn lượt; huỷ sát giờ hơn thì lượt bị tính.
5. Nếu PT huỷ buổi, bạn nhận thông báo, email kèm lý do và lượt được hoàn.

## 2. Huấn luyện viên (PT)

1. Đăng nhập, vào **Lịch của bạn** (`/pt-schedule`):
   - Khai **lịch tuần**: các khung giờ làm việc theo thứ (mỗi khung ≥ 60 phút, không chồng nhau).
   - Thêm **lịch nghỉ** khi bận đột xuất.
   - Nếu có buổi đã đặt nằm ngoài lịch mới hoặc trùng lịch nghỉ, trang hiện cảnh báo kèm danh sách; buổi đó không tự mất, hãy vào **Buổi dạy** để huỷ kèm lý do.
2. **Buổi dạy** (`/pt`): danh sách buổi sắp tới và lịch sử.
   - Huỷ buổi trước giờ: bắt buộc nhập lý do, hội viên luôn được hoàn lượt.
   - Sau giờ bắt đầu: bấm **Hoàn thành** hoặc **Vắng mặt** để chốt buổi.
3. Biểu tượng chuông hiển thị thông báo khi có hội viên đặt hoặc huỷ buổi.

## 3. Quản lý (Manager)

Đăng nhập xong vào thẳng **Trang quản trị** (`/admin`). Các tab được thấy:

| Tab | Việc làm được |
| --- | --- |
| Báo cáo | Doanh thu và tăng trưởng hội viên theo tuần/tháng/quý/năm; xuất Excel/CSV/PDF |
| Tài khoản | Tìm, lọc, sắp xếp; **tạo/sửa/đặt lại mật khẩu tài khoản hội viên**; xuất danh sách |
| Gói tập | Chỉ xem |
| Cửa hàng | Thêm/sửa/ẩn/xoá sản phẩm, **nhập từ Excel/CSV**, xuất danh sách |
| Thanh toán | Xem giao dịch, **xác nhận đã thu tiền** (tiền mặt tại quầy), tải hoá đơn PDF |
| Ra vào | Check-in tại quầy bằng mã hội viên/email/số điện thoại, check-out, lịch sử |

Không làm được: quản lý tài khoản nhân sự (PT, quản lý, quản trị), xoá tài khoản, sửa gói tập,
huỷ giao dịch, xem nhật ký thao tác.

## 4. Quản trị (Admin)

Có mọi quyền của Quản lý, thêm:

- **Tài khoản**: tạo PT (chọn chuyên môn, giá mỗi buổi), Quản lý, Quản trị; xoá mềm tài khoản (giữ lịch sử thanh toán).
- **Gói tập**: thêm, sửa giá/thời hạn, ngừng bán, xoá. Đổi giá chỉ áp dụng cho lượt mua mới.
- **Thanh toán**: huỷ giao dịch đang chờ (gói và lượt PT kèm theo cũng bị huỷ).
- **Nhật ký**: mọi thao tác ghi của quản trị — ai, lúc nào, dữ liệu **trước/sau**; lọc theo đối tượng, ngày; xuất file.

### Thao tác chung trên danh sách

- **Tìm kiếm**: gõ vào ô tìm, kết quả lọc sau 0,3 giây; không phân biệt dấu ("nguyen" tìm được "Nguyễn").
- **Sắp xếp**: bấm tiêu đề cột có biểu tượng ↕ (bấm lần 1 tăng dần, lần 2 giảm dần, lần 3 bỏ sắp xếp).
- **Xuất file**: nút **Xuất file ↓** → chọn Excel/CSV/PDF. File được tạo nền theo đúng bộ lọc và thứ tự đang xem rồi tự tải về.
- **Sửa đồng thời**: nếu người khác vừa sửa cùng gói tập/sản phẩm, hệ thống báo "vừa được người khác sửa" thay vì ghi đè. Tải lại trang rồi sửa lại.

### Nhập sản phẩm từ Excel/CSV

1. Tab **Cửa hàng** → **File mẫu** để tải file `.xlsx` có sẵn cột và 2 dòng ví dụ.
2. Điền mỗi sản phẩm một dòng. Cột bắt buộc: SKU, Tên sản phẩm, Danh mục, Nhóm (GYM/YOGA), Giá, Tồn kho.
3. **Nhập Excel/CSV** → chọn file. SKU đã có thì cập nhật, chưa có thì thêm mới.
4. Hộp kết quả cho biết số dòng thêm, cập nhật và lỗi (kèm số dòng, lý do) để sửa rồi nhập lại.

## 5. Bảo mật tài khoản (cho mọi vai trò)

### Quên mật khẩu

Trang đăng nhập → **Quên mật khẩu?** → nhập email → mở email "Đặt lại mật khẩu IRONIX" →
bấm **Tạo mật khẩu mới** (liên kết dùng một lần, hết hạn sau 30 phút).

### Xác thực 2 bước

1. Menu tài khoản (biểu tượng người) → **Bảo mật tài khoản** → **Bật xác thực 2 bước**.
2. Quét mã QR bằng Google Authenticator hoặc Microsoft Authenticator (hoặc nhập khoá thủ công).
3. Nhập mã 6 số đang hiển thị để hoàn tất.
4. Từ lần sau, đăng nhập xong sẽ được hỏi mã 6 số.
5. Tắt: cần nhập mật khẩu hiện tại và mã 6 số.

Nhập sai mật khẩu hoặc mã 5 lần liên tiếp, tài khoản bị khoá 15 phút; quản trị viên có thể mở
khoá bằng **Đặt lại mật khẩu**.
