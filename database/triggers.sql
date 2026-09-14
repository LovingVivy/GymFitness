-- MySQL 8.0+ integrity triggers for non-overlapping calendars.
-- The service layer must also use transactions and SELECT ... FOR UPDATE
-- because triggers alone do not replace concurrency control.

DELIMITER $$


CREATE TRIGGER trg_user_addresses_one_default_insert
BEFORE INSERT ON user_addresses
FOR EACH ROW
BEGIN
  IF NEW.is_default = TRUE AND NEW.deleted_at IS NULL AND EXISTS (
    SELECT 1 FROM user_addresses AS a
    WHERE a.user_id = NEW.user_id AND a.is_default = TRUE AND a.deleted_at IS NULL
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'User already has a default address';
  END IF;
END$$

CREATE TRIGGER trg_user_addresses_one_default_update
BEFORE UPDATE ON user_addresses
FOR EACH ROW
BEGIN
  IF NEW.is_default = TRUE AND NEW.deleted_at IS NULL AND EXISTS (
    SELECT 1 FROM user_addresses AS a
    WHERE a.user_id = NEW.user_id AND a.id <> NEW.id
      AND a.is_default = TRUE AND a.deleted_at IS NULL
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'User already has a default address';
  END IF;
END$$

CREATE TRIGGER trg_check_ins_one_open_insert
BEFORE INSERT ON check_ins
FOR EACH ROW
BEGIN
  IF NEW.check_out_at IS NULL AND NEW.deleted_at IS NULL AND EXISTS (
    SELECT 1 FROM check_ins AS c
    WHERE c.member_id = NEW.member_id AND c.check_out_at IS NULL AND c.deleted_at IS NULL
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member already has an open check-in';
  END IF;
END$$

CREATE TRIGGER trg_check_ins_one_open_update
BEFORE UPDATE ON check_ins
FOR EACH ROW
BEGIN
  IF NEW.check_out_at IS NULL AND NEW.deleted_at IS NULL AND EXISTS (
    SELECT 1 FROM check_ins AS c
    WHERE c.member_id = NEW.member_id AND c.id <> NEW.id
      AND c.check_out_at IS NULL AND c.deleted_at IS NULL
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member already has an open check-in';
  END IF;
END$$

CREATE TRIGGER trg_trainer_availability_no_overlap_insert
BEFORE INSERT ON trainer_availability
FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1
    FROM trainer_availability AS a
    WHERE a.trainer_id = NEW.trainer_id
      AND a.deleted_at IS NULL
      AND NEW.start_at < a.end_at
      AND NEW.end_at > a.start_at
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Trainer availability overlaps an existing slot';
  END IF;
END$$

CREATE TRIGGER trg_trainer_availability_no_overlap_update
BEFORE UPDATE ON trainer_availability
FOR EACH ROW
BEGIN
  IF NEW.deleted_at IS NULL AND EXISTS (
    SELECT 1
    FROM trainer_availability AS a
    WHERE a.trainer_id = NEW.trainer_id
      AND a.id <> NEW.id
      AND a.deleted_at IS NULL
      AND NEW.start_at < a.end_at
      AND NEW.end_at > a.start_at
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Trainer availability overlaps an existing slot';
  END IF;
END$$

CREATE TRIGGER trg_pt_bookings_validate_insert
BEFORE INSERT ON pt_bookings
FOR EACH ROW
BEGIN
  IF NEW.status IN ('REQUESTED', 'ACCEPTED') THEN
    IF NOT EXISTS (
      SELECT 1
      FROM trainer_availability AS a
      WHERE a.id = NEW.availability_id
        AND a.trainer_id = NEW.trainer_id
        AND a.status = 'AVAILABLE'
        AND a.deleted_at IS NULL
        AND a.start_at <= NEW.start_at
        AND a.end_at >= NEW.end_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'PT booking is outside trainer availability';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.trainer_id = NEW.trainer_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainer already has an overlapping PT booking';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.member_id = NEW.member_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Member already has an overlapping PT booking';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_pt_bookings_validate_update
BEFORE UPDATE ON pt_bookings
FOR EACH ROW
BEGIN
  IF NEW.status IN ('REQUESTED', 'ACCEPTED') AND NEW.deleted_at IS NULL THEN
    IF NOT EXISTS (
      SELECT 1
      FROM trainer_availability AS a
      WHERE a.id = NEW.availability_id
        AND a.trainer_id = NEW.trainer_id
        AND a.status = 'AVAILABLE'
        AND a.deleted_at IS NULL
        AND a.start_at <= NEW.start_at
        AND a.end_at >= NEW.end_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'PT booking is outside trainer availability';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.id <> NEW.id
        AND b.trainer_id = NEW.trainer_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainer already has an overlapping PT booking';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pt_bookings AS b
      WHERE b.id <> NEW.id
        AND b.member_id = NEW.member_id
        AND b.status IN ('REQUESTED', 'ACCEPTED')
        AND b.deleted_at IS NULL
        AND NEW.start_at < b.end_at
        AND NEW.end_at > b.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Member already has an overlapping PT booking';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_class_sessions_no_overlap_insert
BEFORE INSERT ON class_sessions
FOR EACH ROW
BEGIN
  IF NEW.status = 'SCHEDULED' THEN
    IF EXISTS (
      SELECT 1
      FROM class_sessions AS s
      WHERE s.trainer_id = NEW.trainer_id
        AND s.status = 'SCHEDULED'
        AND s.deleted_at IS NULL
        AND NEW.start_at < s.end_at
        AND NEW.end_at > s.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainer already has an overlapping class';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM class_sessions AS s
      WHERE s.room_id = NEW.room_id
        AND s.status = 'SCHEDULED'
        AND s.deleted_at IS NULL
        AND NEW.start_at < s.end_at
        AND NEW.end_at > s.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Room already has an overlapping class';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_class_sessions_no_overlap_update
BEFORE UPDATE ON class_sessions
FOR EACH ROW
BEGIN
  IF NEW.status = 'SCHEDULED' AND NEW.deleted_at IS NULL THEN
    IF EXISTS (
      SELECT 1
      FROM class_sessions AS s
      WHERE s.id <> NEW.id
        AND s.trainer_id = NEW.trainer_id
        AND s.status = 'SCHEDULED'
        AND s.deleted_at IS NULL
        AND NEW.start_at < s.end_at
        AND NEW.end_at > s.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainer already has an overlapping class';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM class_sessions AS s
      WHERE s.id <> NEW.id
        AND s.room_id = NEW.room_id
        AND s.status = 'SCHEDULED'
        AND s.deleted_at IS NULL
        AND NEW.start_at < s.end_at
        AND NEW.end_at > s.start_at
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Room already has an overlapping class';
    END IF;
  END IF;
END$$

DELIMITER ;
