# ARCHITECTURE DECISIONS

## ADR-001 — PostgreSQL 16 là database chính

- **Trạng thái:** Accepted
- **Quyết định:** Dùng PostgreSQL 16, UUID primary key và `TIMESTAMPTZ`.
- **Lý do:** Cần transaction, JSONB, partial index và exclusion constraint cho lịch không chồng lấn.

## ADR-002 — Ba vai trò hệ thống

- **Trạng thái:** Accepted
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

- **Trạng thái:** Accepted
- **Quyết định:** Khi tạo booking `REQUESTED`, giữ một lượt PT. Từ chối hoặc hết hạn sẽ hoàn lượt; hoàn thành chuyển lượt sang used.
- **Lý do:** Ngăn user gửi nhiều yêu cầu vượt quá số lượt đã thanh toán.

## ADR-007 — Ngăn lịch chồng lấn ở database

- **Trạng thái:** Accepted
- **Quyết định:** Dùng PostgreSQL `EXCLUDE USING gist` với khoảng thời gian dạng `[start, end)` cho availability, PT booking và class session.
- **Lý do:** Validation phía ứng dụng không đủ an toàn khi có request đồng thời.

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
