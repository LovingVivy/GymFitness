# Chạy database MySQL

Yêu cầu: MySQL 8.0 trở lên.

## MySQL Workbench

1. Mở một SQL tab mới.
2. Mở hoặc dán toàn bộ nội dung `01_tables.sql`, sau đó chọn **Execute All**.
3. Mở SQL tab thứ hai.
4. Mở hoặc dán toàn bộ nội dung `02_triggers.sql`, sau đó chọn **Execute All**.

File đầu tiên tự tạo và chọn database `gymfitness`. File thứ hai cũng tự chạy `USE gymfitness` trước khi tạo trigger.

## MySQL Command Line

```bash
mysql -u root -p < database/01_tables.sql
mysql -u root -p < database/02_triggers.sql
```

## Kiểm tra kết quả

```sql
USE gymfitness;

SELECT COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'gymfitness';

SELECT COUNT(*) AS trigger_count
FROM information_schema.triggers
WHERE trigger_schema = 'gymfitness';

SELECT COUNT(*) AS foreign_key_count
FROM information_schema.referential_constraints
WHERE constraint_schema = 'gymfitness';

SHOW TRIGGERS FROM gymfitness;
```

Kết quả thiết kế hiện tại:

```text
table_count       = 44
trigger_count     = 10
foreign_key_count = 83
```

Hai script bootstrap dành cho database trống. Sau khi backend được scaffold, thay đổi schema tiếp theo phải được quản lý bằng migration Alembic thay vì chạy lại toàn bộ file bootstrap.
