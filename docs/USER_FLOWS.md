# LUỒNG HOẠT ĐỘNG HỆ THỐNG GYM FITNESS MANAGEMENT

## 1. Mục đích tài liệu

Tài liệu này tổng hợp các luồng nghiệp vụ chính của hệ thống Gym Fitness Management. Đây là tài liệu tham chiếu khi thiết kế database, API, giao diện và kiểm thử.

Hệ thống có bốn vai trò (ADR-019):

| Vai trò | Trách nhiệm chính |
| --- | --- |
| `ADMIN` | Toàn quyền: tài khoản (kể cả nhân sự), gói tập, giao dịch, sản phẩm, báo cáo, nhật ký thao tác |
| `MANAGER` | Vận hành hằng ngày: hội viên, check-in, xác nhận thu tiền, cửa hàng, báo cáo, xuất dữ liệu |
| `USER` | Đăng ký hội viên, xem lịch Gym/Yoga, dùng QR vào phòng, mua và đặt PT, mua sản phẩm |
| `PT` | Quản lý hồ sơ chuyên môn, khai lịch làm việc hằng tuần, dạy và chốt buổi tập |

Quyền được kiểm tra ở backend theo từng màn hình và từng hành động (`app/core/permissions.py`); frontend chỉ dùng danh sách quyền để ẩn/hiện màn hình và nút.

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
  -> chọn PT và một ô giờ còn trống
  -> buổi được xác nhận ngay (PT vẫn có thể huỷ kèm lý do)
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

## 8. PT khai lịch làm việc (ADR-015)

PT không bật/tắt từng khung giờ và không duyệt từng yêu cầu. Thay vào đó PT khai:

- **Lịch tuần lặp lại**: các khung giờ làm việc theo thứ, ví dụ T2–T6 17:00–21:00 (giờ phòng tập, UTC+7). Mỗi khung dài ít nhất một buổi (60 phút) và không chồng lấn trong cùng ngày.
- **Lịch nghỉ đột xuất**: khoảng thời gian không nhận buổi (ốm, việc riêng...).

Từ lịch tuần, hệ thống tự chia thành các ô 60 phút. Hội viên chỉ thấy ô còn trống: đã trừ lịch nghỉ và các buổi người khác đã đặt, không lộ tên khách khác.

Đổi lịch tuần hoặc thêm lịch nghỉ **không tự huỷ** buổi đã đặt. Màn hình "Lịch của bạn" liệt kê các buổi bị lệch (`conflicts`) để PT chủ động huỷ kèm lý do; hội viên được hoàn lượt.

PT chưa khai lịch thì không xuất hiện trong danh sách cho hội viên.

---

## 9. Hội viên đặt buổi PT

### 9.1. Đặt một ô trống

```text
Chọn PT (chỉ PT có chuyên môn trùng loại hình gói, ADR-018)
  -> xem các ô trống trong 14 ngày tới
  -> chọn một ô
  -> backend kiểm tra và giữ 1 lượt PT
  -> buổi ở trạng thái ACCEPTED ngay
  -> PT nhận thông báo
```

Backend kiểm tra trong một transaction (khoá dòng PT để hai người không lấy cùng một ô):

- Đặt trước ít nhất 2 giờ và không quá 14 ngày.
- Đúng mốc của ô 60 phút trong lịch tuần, không rơi vào lịch nghỉ.
- Hội viên có gói còn hiệu lực vào giờ tập và gói khớp chuyên môn PT.
- Ô chưa có người đặt; hội viên không có buổi khác trùng giờ.
- Hội viên còn lượt PT khả dụng.

### 9.2. Huỷ buổi

| Ai huỷ | Điều kiện | Lượt PT |
| --- | --- | --- |
| PT | Trước giờ bắt đầu, **bắt buộc nhập lý do** (thay cho bước "từ chối" cũ) | Luôn hoàn lại |
| Hội viên | Trước giờ bắt đầu ít nhất 12 giờ | Hoàn lại |
| Hội viên | Sát giờ (dưới 12 giờ) | Tính là đã dùng |

Bên còn lại nhận thông báo trong ứng dụng và email. Không bên nào huỷ được khi buổi đã bắt đầu.

### 9.3. Chốt buổi

Sau giờ bắt đầu, PT chốt `COMPLETED` (đã dạy) hoặc `NO_SHOW` (hội viên vắng). Cả hai đều chuyển lượt từ `reserved` sang `used`.

### 9.4. Vòng đời buổi PT

```text
ACCEPTED ──► COMPLETED   (PT, sau giờ bắt đầu)       trừ lượt
         ├─► NO_SHOW     (PT, sau giờ bắt đầu)       trừ lượt
         ├─► CANCELLED   (PT, trước giờ, có lý do)   hoàn lượt
         └─► CANCELLED   (hội viên, trước giờ)       hoàn lượt nếu huỷ sớm
```

Mọi thay đổi lượt PT được ghi vào sổ cái `pt_credit_ledger` trong cùng transaction với trạng thái buổi.

---

## 10. Thông báo

Hệ thống lưu notification record trước, sau đó có thể gửi thêm email.

Thông báo cho PT:

- Có yêu cầu booking mới.
- User hủy booking.
- Booking sắp diễn ra.

Thông báo cho User:

- Buổi PT đã được đặt (xác nhận ngay).
- PT huỷ buổi kèm lý do (kèm email, lượt PT được hoàn).
- Buổi PT đã hoàn thành hoặc bị ghi vắng mặt.
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

## 12. Luồng quản trị (Admin và Manager)

Trang `/admin` hiển thị các tab theo quyền của tài khoản. Manager không thấy tab Nhật ký,
chỉ xem gói tập, không huỷ được giao dịch và chỉ quản lý được tài khoản hội viên.

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

## 13. Các trang đã có

| Đường dẫn | Ai dùng | Nội dung |
| --- | --- | --- |
| `/` | Mọi người | Trang chủ |
| `/products` | Mọi người | Cửa hàng |
| `/plans` | Mọi người | Chọn gói Gym/Yoga, thanh toán VietQR |
| `/login`, `/signup` | Mọi người | Đăng nhập (kèm xác thực 2 bước), đăng ký, quên mật khẩu |
| `/reset-password` | Mọi người | Đặt mật khẩu mới từ liên kết trong email |
| `/profile` | Đã đăng nhập | Hồ sơ, gói hiện tại, bảo mật tài khoản (bật/tắt 2FA) |
| `/schedule` | Hội viên | Lịch tập theo tháng |
| `/pt-booking` | Hội viên | Mua lượt PT, đặt và huỷ buổi |
| `/pt` | PT | Buổi dạy, chốt hoàn thành/vắng mặt |
| `/pt-schedule` | PT | Lịch làm việc hằng tuần và lịch nghỉ |
| `/admin` | Admin, Manager | Báo cáo, tài khoản, gói tập, cửa hàng, thanh toán, ra vào, nhật ký |

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
9. PT khai lịch làm việc hằng tuần.
10. User chọn PT và một ô giờ còn trống.
11. Hệ thống giữ một PT credit, xác nhận buổi ngay và báo cho PT.
12. Buổi xuất hiện trên lịch hai bên; PT có thể huỷ kèm lý do (hoàn lượt).
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

---

## 16. Bảo mật tài khoản

### 16.1. Quên mật khẩu

```text
Bấm "Quên mật khẩu?" ở trang đăng nhập
  -> nhập email
  -> luôn nhận thông báo chung (không lộ email nào đã đăng ký)
  -> hàng đợi tác vụ tạo token và gửi email có liên kết /reset-password?token=...
  -> mở liên kết, nhập mật khẩu mới
  -> mật khẩu đổi, tài khoản được mở khoá, liên kết hết hiệu lực
```

- Database chỉ lưu SHA-256 của token; token gốc chỉ có trong email.
- Liên kết dùng một lần, hết hạn sau 30 phút; yêu cầu mới làm liên kết cũ mất hiệu lực.

### 16.2. Xác thực 2 bước (TOTP)

```text
Hồ sơ -> Bảo mật tài khoản -> Bật xác thực 2 bước
  -> quét mã QR bằng Google/Microsoft Authenticator
  -> nhập mã 6 số để xác nhận (khoá chỉ được lưu khi mã đúng)

Đăng nhập: email + mật khẩu đúng
  -> nhận challenge_token (5 phút), chưa có phiên đăng nhập
  -> nhập mã 6 số -> nhận access token
```

Mã sai được tính vào bộ đếm khoá tài khoản như mật khẩu sai. Tắt 2FA cần cả mật khẩu và mã hiện tại.

---

## 17. Xuất / nhập dữ liệu và hoá đơn

- **Xuất**: mỗi danh sách quản trị (tài khoản, giao dịch, ra vào, sản phẩm, doanh thu, tăng trưởng hội viên, nhật ký) có nút "Xuất file" ra Excel, CSV hoặc PDF theo đúng bộ lọc và thứ tự đang xem. File được tạo trong hàng đợi tác vụ; giao diện hỏi trạng thái rồi tự tải về.
- **Nhập**: tab Cửa hàng nhận file `.xlsx`/`.csv` theo file mẫu; SKU đã có thì cập nhật, chưa có thì tạo mới; dòng lỗi được báo lại kèm số dòng.
- **Hoá đơn**: mọi giao dịch đã thu tiền có hoá đơn PDF (số `HDyyyymm-nnnnn`). Hội viên nhận hoá đơn đính kèm email khi thanh toán xong và tải lại được ở màn hình thanh toán; quản trị tải ở tab Thanh toán.
