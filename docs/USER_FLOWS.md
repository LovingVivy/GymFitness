# LUỒNG HOẠT ĐỘNG HỆ THỐNG GYM FITNESS MANAGEMENT

## 1. Mục đích tài liệu

Tài liệu này tổng hợp các luồng nghiệp vụ chính của hệ thống Gym Fitness Management. Đây là tài liệu tham chiếu khi thiết kế database, API, giao diện và kiểm thử.

Hệ thống có ba nhóm người dùng chính:

| Vai trò | Trách nhiệm chính |
| --- | --- |
| `ADMIN` | Quản lý tài khoản, hội viên, PT, gói tập, giao dịch, sản phẩm, thiết bị, báo cáo và audit log |
| `USER` | Đăng ký hội viên, xem lịch Gym/Yoga, dùng QR vào phòng, mua và đặt PT, mua sản phẩm |
| `PT` | Quản lý hồ sơ chuyên môn, lịch rảnh/bận, tiếp nhận và xử lý yêu cầu hướng dẫn |

Vai trò Manager trong đặc tả ban đầu được gộp vào Admin. Backend là nơi quyết định quyền truy cập; frontend chỉ có trách nhiệm hiển thị giao diện phù hợp.

---

## 2. Luồng tổng thể của User

```text
Chọn gói tập
  -> đăng ký hoặc đăng nhập
  -> hoàn thiện hồ sơ
  -> xác nhận gói
  -> quét QR thanh toán
  -> thanh toán thành công
  -> kích hoạt hội viên
  -> tạo lịch Gym/Yoga
  -> cấp QR check-in
  -> tập luyện / đặt lớp / mua buổi PT
  -> chọn PT trên lịch
  -> PT chấp thuận hoặc từ chối
  -> hoàn thành buổi tập
  -> nhắc gia hạn khi gần hết gói
```

Trang Home và Product là phần giới thiệu/bán hàng. Phần cốt lõi bắt đầu từ lúc user chọn gói, tạo tài khoản và thanh toán thành công.

---

## 3. Đăng ký, đăng nhập và hồ sơ

### 3.1. Chọn gói khi chưa đăng nhập

Khi user nhấn **Chọn gói tập** nhưng chưa đăng nhập:

```text
Chọn gói
  -> chuyển đến /signup hoặc /login
  -> đăng ký/đăng nhập thành công
  -> quay lại gói đã chọn
  -> tiếp tục thanh toán
```

Gói đã chọn và trang cần quay lại phải được lưu bằng query parameter hoặc session an toàn, ví dụ:

```text
/signup?returnTo=/plans&plan=gym-monthly
```

### 3.2. Thông tin đăng ký

Thông tin tài khoản bắt buộc:

- Họ và tên.
- Email.
- Số điện thoại.
- Mật khẩu.

Thông tin thể chất và tập luyện:

- Chiều cao.
- Cân nặng.
- Kinh nghiệm: mới tập, cơ bản, trung cấp hoặc nâng cao.
- Mục tiêu: giảm cân, tăng cơ, duy trì sức khỏe hoặc tăng độ linh hoạt.
- Số buổi dự kiến tập mỗi tuần.

Cần phân biệt hai dữ liệu:

- `weekly_training_sessions`: số buổi user muốn tự tập mỗi tuần, dùng để đề xuất lịch.
- `pt_session_quantity`: số buổi PT trả phí user mua, dùng làm hạn mức đặt PT.

### 3.3. Hồ sơ cá nhân

User có thể cập nhật:

- Ảnh đại diện.
- Họ tên và số điện thoại.
- Chiều cao, cân nặng và mục tiêu.
- Kinh nghiệm và số buổi tập mỗi tuần.
- Danh sách địa chỉ nhận hàng.

Ảnh đại diện phải được kiểm tra định dạng, dung lượng và quyền truy cập trước khi lưu.

---

## 4. Đăng ký và thanh toán gói hội viên

### 4.1. Chọn loại gói

Hai nhóm gói chính:

- Gym theo tháng hoặc theo năm.
- Yoga theo tháng hoặc theo năm.

User có thể sở hữu đồng thời gói Gym và Yoga nếu nghiệp vụ thanh toán cho phép.

### 4.2. Luồng thanh toán

```text
Chọn gói
  -> tạo đơn thanh toán PENDING
  -> hiển thị QR thanh toán đúng số tiền/nội dung
  -> cổng thanh toán xác nhận
  -> Payment = PAID
  -> Subscription = ACTIVE
  -> tính start_date và end_date
  -> mở trang lịch trình và QR check-in
```

Quy tắc mặc định:

- `start_date` là thời điểm thanh toán được xác nhận thành công.
- `end_date` được tính theo thời hạn thật của gói, không quy đổi tháng thành số ngày cố định.
- Chỉ webhook hoặc bước xác minh phía backend mới được chuyển payment sang `PAID`.
- Thanh toán thất bại hoặc hết hạn không kích hoạt gói, lịch và QR check-in.

Vòng đời subscription:

```text
PENDING -> ACTIVE -> FROZEN
                  -> EXPIRED
                  -> CANCELLED
```

### 4.3. Phân biệt hai loại QR

| QR | Mục đích |
| --- | --- |
| QR thanh toán | Gắn với đơn hàng, số tiền và nội dung giao dịch cụ thể |
| QR check-in | Token ngắn hạn dùng để xác thực quyền vào phòng |

Hai loại QR không dùng chung token hoặc payload.

---

## 5. Trang lịch trình Gym và Yoga

Trang lịch trình chỉ được mở khi user có ít nhất một subscription đã thanh toán và đang `ACTIVE`.

Lịch được chia thành hai phần hoặc hai tab:

- **GYM**: lịch tập sức mạnh/cardio theo mục tiêu, kinh nghiệm và số buổi mỗi tuần.
- **YOGA**: lịch Yoga độc lập theo cấp độ và mục tiêu linh hoạt/phục hồi.

Nếu user chỉ có một loại gói, tab còn lại hiển thị trạng thái chưa đăng ký và nút mua gói. Nếu có cả hai gói, user được chuyển đổi giữa hai lịch.

Mỗi ngày trên lịch có thể hiển thị:

- Buổi tập đề xuất.
- Ngày nghỉ hoặc phục hồi.
- Lớp đã đặt.
- Buổi PT đang chờ xác nhận.
- Buổi PT đã được chấp thuận.
- Trạng thái hoàn thành, hủy hoặc vắng mặt.

Khi nhấn một ngày, user có thể xem chi tiết buổi tập và chọn **Đặt PT cho ngày này**.

---

## 6. QR check-in/check-out

Sau khi gói được kích hoạt, nút QR nổi xuất hiện ở góc giao diện hội viên.

```text
User mở QR
  -> backend phát token có chữ ký và thời hạn ngắn
  -> nhân viên/thiết bị quét QR
  -> backend kiểm tra tài khoản và subscription
  -> kiểm tra token hết hạn hoặc đã dùng
  -> tạo check-in
  -> quét/check-out khi user rời phòng
```

Điều kiện check-in:

- User đang hoạt động và không bị khóa.
- Có subscription `ACTIVE` phù hợp.
- QR có chữ ký hợp lệ và chưa hết hạn.
- Nonce/token chưa được sử dụng.
- Không có lượt check-in đang mở bị trùng.

QR nên tự làm mới sau khoảng 30–60 giây. Không đưa `user_id` thuần túy hoặc thông tin cá nhân trực tiếp vào QR.

---

## 7. Mua buổi PT

User có thể mua PT sau khi đã đăng ký gói hội viên.

```text
Chọn số buổi PT
  -> số buổi x đơn giá
  -> tạo payment PENDING
  -> thanh toán QR
  -> payment PAID
  -> cộng PT credit vào ví lượt tập
```

Thông tin số lượt cần quản lý:

```text
available = purchased - reserved - used
```

- `purchased`: tổng số buổi PT đã thanh toán.
- `reserved`: số buổi đang chờ PT phản hồi hoặc đã có booking tương lai.
- `used`: số buổi đã hoàn thành hoặc bị tính phí theo chính sách hủy/no-show.

Không cộng lượt PT khi payment chưa được xác nhận thành công.

---

## 8. PT thiết lập lịch rảnh/bận

PT sử dụng lịch cá nhân để tạo khung giờ:

- `AVAILABLE`: có thể nhận yêu cầu.
- `BUSY`: PT chủ động đánh dấu bận.
- `PENDING`: khung giờ đang được giữ cho một yêu cầu.
- `BOOKED`: PT đã chấp thuận booking.

User chỉ nhìn thấy trạng thái khả dụng và thông tin chuyên môn cần thiết. User không được thấy tên hoặc dữ liệu của khách hàng khác trong lịch PT.

PT không được tạo các khung giờ chồng lấn. Khi một booking được chấp thuận, backend phải khóa khung giờ trong transaction để tránh nhận hai user cùng lúc.

---

## 9. User yêu cầu tập cùng PT

### 9.1. Tạo yêu cầu

Tại một ngày trong lịch Gym/Yoga:

```text
Chọn ngày
  -> chọn Đặt PT
  -> lọc PT theo Gym/Yoga, chuyên môn và giờ rảnh
  -> chọn PT và khung giờ
  -> backend kiểm tra quyền và lượt PT
  -> giữ một PT credit
  -> tạo yêu cầu REQUESTED
  -> gửi thông báo cho PT
```

Backend phải kiểm tra:

- Subscription của user đang `ACTIVE`.
- Ngày được chọn nằm trong thời hạn gói.
- PT phù hợp loại hình tập và đang `AVAILABLE`.
- User còn đủ `available` PT credit.
- User và PT không có booking bị trùng giờ.

User không được chọn nhiều ngày hơn số lượt PT đã thanh toán. Frontend phải vô hiệu hóa thao tác khi hết lượt và backend vẫn phải kiểm tra lại bằng transaction.

### 9.2. PT xử lý yêu cầu

PT nhận thông báo có user yêu cầu hướng dẫn và có thể:

#### Chấp thuận

- Request chuyển từ `REQUESTED` sang `ACCEPTED`.
- Khung giờ chuyển thành `BOOKED`.
- PT credit tiếp tục nằm trong `reserved`.
- Booking xuất hiện trên lịch của cả user và PT.
- User nhận thông báo xác nhận.

#### Từ chối

- Request chuyển từ `REQUESTED` sang `REJECTED`.
- PT bắt buộc chọn hoặc nhập lý do.
- Khung giờ được mở lại nếu không có chặn khác.
- PT credit được trả từ `reserved` về `available`.
- User nhận thông báo kèm lý do.

Lý do từ chối gợi ý:

- Có lịch đột xuất.
- Không phù hợp chuyên môn yêu cầu.
- Khung giờ không còn khả dụng.
- Đề nghị chọn thời gian khác.
- Lý do khác.

### 9.3. Vòng đời booking PT

```text
REQUESTED -> ACCEPTED -> COMPLETED
          -> REJECTED
          -> CANCELLED
          -> EXPIRED

ACCEPTED  -> CANCELLED
          -> NO_SHOW
```

Quy tắc PT credit:

- Tạo request: chuyển 1 lượt từ `available` sang `reserved`.
- PT từ chối hoặc request hết hạn: trả lượt về `available`.
- Buổi tập hoàn thành: chuyển lượt từ `reserved` sang `used`.
- User hủy đúng thời hạn: trả lượt theo chính sách.
- User hủy muộn hoặc không đến: có thể chuyển lượt sang `used`.

Mọi thay đổi lượt PT và trạng thái booking phải thực hiện trong cùng transaction.

---

## 10. Thông báo

Hệ thống lưu notification record trước, sau đó có thể gửi thêm email.

Thông báo cho PT:

- Có yêu cầu booking mới.
- User hủy booking.
- Booking sắp diễn ra.

Thông báo cho User:

- PT chấp thuận yêu cầu.
- PT từ chối kèm lý do.
- Booking sắp diễn ra.
- Payment thành công hoặc thất bại.
- Số lượt PT còn ít hoặc đã hết.
- Gói hội viên sắp hết hạn.

Thông báo gần hết hạn được tạo tại các mốc đề xuất:

- Trước 7 ngày.
- Trước 3 ngày.
- Trước 1 ngày.
- Khi subscription hết hạn.

Thông báo gia hạn phải có nút **Gia hạn ngay** và dẫn user đến đúng gói hiện tại.

---

## 11. Mua sản phẩm và địa chỉ giao hàng

User có thể thêm địa chỉ trong profile hoặc tại bước thanh toán đơn hàng.

```text
Thêm sản phẩm vào giỏ
  -> kiểm tra giỏ hàng
  -> chọn địa chỉ đã lưu hoặc thêm địa chỉ mới
  -> chọn có lưu địa chỉ mới vào profile hay không
  -> thanh toán
  -> tạo đơn hàng
  -> theo dõi trạng thái giao hàng
```

Một user có thể có nhiều địa chỉ và một địa chỉ mặc định. Thông tin nên gồm:

- Tên người nhận.
- Số điện thoại.
- Tỉnh/thành, quận/huyện, phường/xã.
- Địa chỉ chi tiết.
- Ghi chú giao hàng.
- Cờ địa chỉ mặc định.

Đơn hàng phải lưu snapshot địa chỉ tại thời điểm mua. Khi user sửa hoặc xóa địa chỉ trong profile, địa chỉ trên đơn hàng cũ không được thay đổi.

---

## 12. Luồng Admin

Admin có thể:

- Quản lý tài khoản User và PT.
- Khóa/mở tài khoản và đặt lại trạng thái truy cập.
- Quản lý hồ sơ hội viên.
- Tạo và cấu hình gói Gym, Yoga, PT.
- Theo dõi subscription, gia hạn, đóng băng, hủy hoặc hết hạn.
- Xem và hỗ trợ check-in/check-out.
- Quản lý lịch PT và xử lý tranh chấp booking.
- Theo dõi payment, invoice, đơn hàng và hoàn tiền.
- Quản lý sản phẩm, tồn kho và trạng thái giao hàng.
- Quản lý thiết bị và bảo trì.
- Xem dashboard và xuất báo cáo.
- Xem audit log cho mọi hành động nhạy cảm.

Admin không được sửa trực tiếp số lượt PT mà không tạo transaction record và audit log.

---

## 13. Các trang chính dự kiến

### Public

- `/`: Home.
- `/products`: danh sách sản phẩm.
- `/plans`: lựa chọn gói Gym/Yoga.
- `/login`: đăng nhập.
- `/signup`: đăng ký.

### User

- `/member/dashboard`: tổng quan hội viên.
- `/member/profile`: hồ sơ, ảnh đại diện và địa chỉ.
- `/member/membership`: gói hiện tại và gia hạn.
- `/member/schedule`: lịch Gym/Yoga và thao tác đặt PT.
- `/member/pt-credits`: mua và xem lịch sử lượt PT.
- `/member/pt-bookings`: yêu cầu và lịch PT.
- `/member/check-ins`: QR và lịch sử vào phòng.
- `/member/orders`: đơn mua sản phẩm.
- `/member/notifications`: thông báo.

### PT

- `/pt/dashboard`: tổng quan công việc.
- `/pt/profile`: hồ sơ và chuyên môn.
- `/pt/calendar`: thiết lập rảnh/bận.
- `/pt/requests`: yêu cầu đang chờ xử lý.
- `/pt/bookings`: lịch đã nhận.
- `/pt/members`: user đang hướng dẫn.
- `/pt/notifications`: thông báo.

### Admin

- `/admin/dashboard`: dashboard quản trị.
- `/admin/users`: tài khoản và phân quyền.
- `/admin/members`: hội viên.
- `/admin/trainers`: PT.
- `/admin/plans`: gói tập.
- `/admin/subscriptions`: đăng ký hội viên.
- `/admin/check-ins`: lịch sử điểm danh.
- `/admin/bookings`: lớp học và PT booking.
- `/admin/payments`: thanh toán và hóa đơn.
- `/admin/products`: sản phẩm và tồn kho.
- `/admin/orders`: đơn hàng.
- `/admin/equipment`: thiết bị và bảo trì.
- `/admin/reports`: báo cáo.
- `/admin/audit-logs`: lịch sử hành động.

---

## 14. Luồng nghiệm thu end-to-end ưu tiên

```text
1. User chọn gói Gym hoặc Yoga khi chưa đăng nhập.
2. Hệ thống yêu cầu đăng ký và giữ lại gói đã chọn.
3. User nhập thông tin cá nhân, thể chất và kinh nghiệm.
4. User quét QR thanh toán gói.
5. Backend xác nhận payment và kích hoạt subscription.
6. User thấy ngày bắt đầu/kết thúc và lịch Gym/Yoga.
7. User mở QR và check-in phòng tập thành công.
8. User mua một số buổi PT bằng QR thanh toán.
9. PT thiết lập các khung giờ AVAILABLE/BUSY.
10. User chọn ngày, PT và khung giờ trên lịch.
11. Hệ thống giữ một PT credit và gửi thông báo cho PT.
12. PT chấp thuận; booking xuất hiện trên lịch hai bên.
13. Buổi tập hoàn thành; PT credit chuyển sang used.
14. Khi gần hết hạn, user nhận thông báo và gia hạn gói.
15. User mua sản phẩm bằng địa chỉ có sẵn hoặc địa chỉ mới.
16. Admin xem được subscription, payment, check-in, booking, order và audit log.
```

Luồng được coi là đạt khi mọi bước thực hiện qua giao diện/API, không cần sửa code hoặc can thiệp database trực tiếp.

---

## 15. Nguyên tắc kỹ thuật bắt buộc

- Mọi kiểm tra quyền, thời hạn gói, lịch trùng và số lượt PT phải được thực hiện ở backend.
- Các thay đổi payment, subscription, booking và PT credit phải có transaction rõ ràng.
- Tiền dùng `Decimal/Numeric`, không dùng float.
- QR không chứa thông tin cá nhân hoặc ID thuần túy.
- Password không lưu plaintext; secret không hard-code.
- Hành động nhạy cảm phải có audit log.
- Dữ liệu nghiệp vụ ưu tiên soft-delete để giữ lịch sử.
- Thời gian lưu UTC và chuyển timezone khi hiển thị.
- API danh sách phải có pagination, search, filter và sort phù hợp.
- Mỗi luồng cần unit test, integration test và ít nhất một kịch bản E2E quan trọng.
