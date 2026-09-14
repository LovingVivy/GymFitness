-- GymFitness PostgreSQL 16 schema
-- Source of truth: CODEX_IMPLEMENTATION_SPEC_GYM_MANAGEMENT.md + docs/USER_FLOWS.md

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Organization, authentication and profiles
-- ============================================================

CREATE TABLE branches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(30) NOT NULL UNIQUE,
  name VARCHAR(150) NOT NULL,
  address_line TEXT NOT NULL,
  phone VARCHAR(30),
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Bangkok',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email CITEXT NOT NULL UNIQUE,
  phone VARCHAR(30),
  password_hash TEXT NOT NULL,
  role VARCHAR(16) NOT NULL CHECK (role IN ('ADMIN', 'USER', 'PT')),
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'INACTIVE')),
  email_verified_at TIMESTAMPTZ,
  phone_verified_at TIMESTAMPTZ,
  last_login_at TIMESTAMPTZ,
  failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
  locked_until TIMESTAMPTZ,
  two_factor_secret_encrypted TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0)
);

CREATE UNIQUE INDEX uq_users_phone_active
  ON users (phone) WHERE phone IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_users_role_status ON users (role, status) WHERE deleted_at IS NULL;

CREATE TABLE file_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  storage_key TEXT NOT NULL UNIQUE,
  original_name TEXT NOT NULL,
  content_type VARCHAR(120) NOT NULL,
  size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
  visibility VARCHAR(12) NOT NULL DEFAULT 'PRIVATE'
    CHECK (visibility IN ('PRIVATE', 'PUBLIC')),
  checksum_sha256 CHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ
);

CREATE TABLE user_profiles (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  full_name VARCHAR(150) NOT NULL,
  avatar_file_id UUID REFERENCES file_assets(id) ON DELETE SET NULL,
  date_of_birth DATE,
  gender VARCHAR(16) CHECK (gender IS NULL OR gender IN ('MALE', 'FEMALE', 'OTHER')),
  height_cm NUMERIC(5,2) CHECK (height_cm IS NULL OR height_cm BETWEEN 50 AND 300),
  weight_kg NUMERIC(5,2) CHECK (weight_kg IS NULL OR weight_kg BETWEEN 15 AND 500),
  experience_level VARCHAR(20)
    CHECK (experience_level IS NULL OR experience_level IN ('BEGINNER', 'BASIC', 'INTERMEDIATE', 'ADVANCED')),
  fitness_goal VARCHAR(24)
    CHECK (fitness_goal IS NULL OR fitness_goal IN ('WEIGHT_LOSS', 'MUSCLE_GAIN', 'GENERAL_HEALTH', 'FLEXIBILITY')),
  weekly_training_sessions SMALLINT CHECK (weekly_training_sessions IS NULL OR weekly_training_sessions BETWEEN 1 AND 14),
  emergency_contact_name VARCHAR(150),
  emergency_contact_phone VARCHAR(30),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0)
);

CREATE TABLE user_addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label VARCHAR(60),
  recipient_name VARCHAR(150) NOT NULL,
  recipient_phone VARCHAR(30) NOT NULL,
  province VARCHAR(100) NOT NULL,
  district VARCHAR(100) NOT NULL,
  ward VARCHAR(100) NOT NULL,
  address_line TEXT NOT NULL,
  delivery_note TEXT,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0)
);

CREATE UNIQUE INDEX uq_user_addresses_one_default
  ON user_addresses (user_id) WHERE is_default = TRUE AND deleted_at IS NULL;
CREATE INDEX idx_user_addresses_user ON user_addresses (user_id) WHERE deleted_at IS NULL;

CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_digest CHAR(64) NOT NULL UNIQUE,
  jwt_id UUID NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  replaced_by_token_id UUID REFERENCES refresh_tokens(id) ON DELETE SET NULL,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (expires_at > created_at)
);

CREATE INDEX idx_refresh_tokens_user_active
  ON refresh_tokens (user_id, expires_at) WHERE revoked_at IS NULL;

CREATE TABLE password_reset_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_digest CHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (expires_at > created_at)
);

CREATE INDEX idx_password_reset_user_active
  ON password_reset_tokens (user_id, expires_at) WHERE used_at IS NULL;

CREATE TABLE members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_code VARCHAR(30) NOT NULL UNIQUE,
  user_id UUID UNIQUE REFERENCES users(id) ON DELETE SET NULL,
  home_branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
  full_name VARCHAR(150) NOT NULL,
  email CITEXT,
  phone VARCHAR(30),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0)
);

CREATE INDEX idx_members_name ON members (full_name) WHERE deleted_at IS NULL;
CREATE INDEX idx_members_status ON members (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_members_branch ON members (home_branch_id) WHERE deleted_at IS NULL;

CREATE TABLE trainer_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
  employee_code VARCHAR(30) NOT NULL UNIQUE,
  branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
  bio TEXT,
  certifications TEXT,
  hourly_rate NUMERIC(14,2) NOT NULL DEFAULT 200000 CHECK (hourly_rate >= 0),
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'ON_LEAVE', 'INACTIVE')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0)
);

CREATE TABLE trainer_specialties (
  trainer_id UUID NOT NULL REFERENCES trainer_profiles(id) ON DELETE CASCADE,
  specialty VARCHAR(24) NOT NULL
    CHECK (specialty IN ('GYM', 'YOGA', 'WEIGHT_LOSS', 'MUSCLE_GAIN', 'REHABILITATION', 'FLEXIBILITY')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (trainer_id, specialty)
);

-- ============================================================
-- Payments, membership plans and subscriptions
-- ============================================================

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_number VARCHAR(40) NOT NULL UNIQUE,
  member_id UUID REFERENCES members(id) ON DELETE SET NULL,
  purpose VARCHAR(24) NOT NULL
    CHECK (purpose IN ('MEMBERSHIP', 'PT_CREDIT', 'PRODUCT_ORDER')),
  amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'VND',
  method VARCHAR(20) NOT NULL DEFAULT 'QR'
    CHECK (method IN ('QR', 'CASH', 'BANK_TRANSFER', 'CARD')),
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED', 'VOID')),
  provider VARCHAR(50),
  external_reference VARCHAR(150),
  idempotency_key VARCHAR(100) NOT NULL UNIQUE,
  qr_payload TEXT,
  qr_expires_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  failure_reason TEXT,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK ((status = 'PAID' AND paid_at IS NOT NULL) OR status <> 'PAID')
);

CREATE UNIQUE INDEX uq_payments_provider_reference
  ON payments (provider, external_reference)
  WHERE provider IS NOT NULL AND external_reference IS NOT NULL;
CREATE INDEX idx_payments_member_created ON payments (member_id, created_at DESC);
CREATE INDEX idx_payments_status_created ON payments (status, created_at DESC);

CREATE TABLE payment_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id UUID REFERENCES payments(id) ON DELETE SET NULL,
  provider VARCHAR(50) NOT NULL,
  provider_event_id VARCHAR(150) NOT NULL,
  event_type VARCHAR(80) NOT NULL,
  signature_valid BOOLEAN NOT NULL DEFAULT FALSE,
  payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (provider, provider_event_id)
);

CREATE TABLE membership_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(150) NOT NULL,
  activity_type VARCHAR(12) NOT NULL CHECK (activity_type IN ('GYM', 'YOGA')),
  description TEXT,
  duration_months SMALLINT CHECK (duration_months IS NULL OR duration_months > 0),
  duration_days SMALLINT CHECK (duration_days IS NULL OR duration_days > 0),
  price NUMERIC(14,2) NOT NULL CHECK (price >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'VND',
  max_visits INTEGER CHECK (max_visits IS NULL OR max_visits > 0),
  freeze_days_allowed SMALLINT NOT NULL DEFAULT 0 CHECK (freeze_days_allowed >= 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK ((duration_months IS NOT NULL)::INTEGER + (duration_days IS NOT NULL)::INTEGER = 1)
);

CREATE INDEX idx_membership_plans_activity_active
  ON membership_plans (activity_type, is_active) WHERE deleted_at IS NULL;

CREATE TABLE membership_subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
  plan_id UUID NOT NULL REFERENCES membership_plans(id) ON DELETE RESTRICT,
  payment_id UUID UNIQUE REFERENCES payments(id) ON DELETE RESTRICT,
  renewed_from_id UUID REFERENCES membership_subscriptions(id) ON DELETE SET NULL,
  start_at TIMESTAMPTZ,
  end_at TIMESTAMPTZ,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'ACTIVE', 'FROZEN', 'EXPIRED', 'CANCELLED')),
  remaining_visits INTEGER CHECK (remaining_visits IS NULL OR remaining_visits >= 0),
  frozen_from TIMESTAMPTZ,
  frozen_until TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (end_at IS NULL OR start_at IS NOT NULL),
  CHECK (end_at IS NULL OR end_at > start_at),
  CHECK (frozen_until IS NULL OR (frozen_from IS NOT NULL AND frozen_until > frozen_from)),
  CHECK (cancelled_at IS NULL OR status = 'CANCELLED')
);

CREATE INDEX idx_subscriptions_member_status
  ON membership_subscriptions (member_id, status, end_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_subscriptions_expiry
  ON membership_subscriptions (end_at) WHERE status IN ('ACTIVE', 'FROZEN') AND deleted_at IS NULL;

CREATE TABLE subscription_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  from_status VARCHAR(16),
  to_status VARCHAR(16) NOT NULL
    CHECK (to_status IN ('PENDING', 'ACTIVE', 'FROZEN', 'EXPIRED', 'CANCELLED')),
  reason TEXT,
  changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscription_history_subscription
  ON subscription_status_history (subscription_id, created_at DESC);

CREATE TABLE subscription_freeze_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  frozen_from TIMESTAMPTZ NOT NULL,
  frozen_until TIMESTAMPTZ NOT NULL,
  days_granted SMALLINT NOT NULL CHECK (days_granted > 0),
  reason TEXT,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (frozen_until > frozen_from)
);

-- ============================================================
-- Training schedules and facility check-in
-- ============================================================

CREATE TABLE workout_schedule_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  activity_type VARCHAR(12) NOT NULL CHECK (activity_type IN ('GYM', 'YOGA')),
  scheduled_date DATE NOT NULL,
  start_time TIME,
  end_time TIME,
  entry_type VARCHAR(20) NOT NULL
    CHECK (entry_type IN ('WORKOUT', 'REST', 'CLASS', 'PT_SESSION')),
  title VARCHAR(160) NOT NULL,
  description TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'PLANNED'
    CHECK (status IN ('PLANNED', 'COMPLETED', 'SKIPPED', 'CANCELLED')),
  source VARCHAR(16) NOT NULL DEFAULT 'SYSTEM'
    CHECK (source IN ('SYSTEM', 'USER', 'PT', 'ADMIN')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (end_time IS NULL OR start_time IS NOT NULL),
  CHECK (end_time IS NULL OR end_time > start_time)
);

CREATE INDEX idx_workout_schedule_member_date
  ON workout_schedule_entries (member_id, scheduled_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_workout_schedule_subscription
  ON workout_schedule_entries (subscription_id, scheduled_date) WHERE deleted_at IS NULL;

CREATE TABLE qr_nonces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nonce_hash CHAR(64) NOT NULL UNIQUE,
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  CHECK (expires_at > issued_at)
);

CREATE INDEX idx_qr_nonces_expiry ON qr_nonces (expires_at) WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE TABLE check_ins (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
  qr_nonce_id UUID UNIQUE REFERENCES qr_nonces(id) ON DELETE RESTRICT,
  check_in_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  check_out_at TIMESTAMPTZ,
  method VARCHAR(12) NOT NULL CHECK (method IN ('QR', 'MANUAL')),
  location TEXT,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (check_out_at IS NULL OR check_out_at > check_in_at),
  CHECK ((method = 'QR' AND qr_nonce_id IS NOT NULL) OR method = 'MANUAL')
);

CREATE UNIQUE INDEX uq_check_ins_one_open_per_member
  ON check_ins (member_id) WHERE check_out_at IS NULL AND deleted_at IS NULL;
CREATE INDEX idx_check_ins_member_time ON check_ins (member_id, check_in_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_check_ins_branch_time ON check_ins (branch_id, check_in_at DESC) WHERE deleted_at IS NULL;

-- ============================================================
-- PT credit wallet, availability and bookings
-- ============================================================

CREATE TABLE pt_credit_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL UNIQUE REFERENCES members(id) ON DELETE RESTRICT,
  purchased_sessions INTEGER NOT NULL DEFAULT 0 CHECK (purchased_sessions >= 0),
  reserved_sessions INTEGER NOT NULL DEFAULT 0 CHECK (reserved_sessions >= 0),
  used_sessions INTEGER NOT NULL DEFAULT 0 CHECK (used_sessions >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (purchased_sessions >= reserved_sessions + used_sessions)
);

CREATE TABLE pt_credit_purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  credit_account_id UUID NOT NULL REFERENCES pt_credit_accounts(id) ON DELETE RESTRICT,
  payment_id UUID NOT NULL UNIQUE REFERENCES payments(id) ON DELETE RESTRICT,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'CREDITED', 'REFUNDED', 'VOID')),
  credited_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK ((status = 'CREDITED' AND credited_at IS NOT NULL) OR status <> 'CREDITED')
);

CREATE TABLE trainer_availability (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trainer_id UUID NOT NULL REFERENCES trainer_profiles(id) ON DELETE RESTRICT,
  branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
  start_at TIMESTAMPTZ NOT NULL,
  end_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(16) NOT NULL CHECK (status IN ('AVAILABLE', 'BUSY')),
  recurrence_rule TEXT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (end_at > start_at),
  EXCLUDE USING gist (
    trainer_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  ) WHERE (deleted_at IS NULL)
);

CREATE INDEX idx_trainer_availability_search
  ON trainer_availability (trainer_id, start_at, end_at, status) WHERE deleted_at IS NULL;

CREATE TABLE pt_bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_number VARCHAR(40) NOT NULL UNIQUE,
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
  trainer_id UUID NOT NULL REFERENCES trainer_profiles(id) ON DELETE RESTRICT,
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  credit_account_id UUID NOT NULL REFERENCES pt_credit_accounts(id) ON DELETE RESTRICT,
  availability_id UUID REFERENCES trainer_availability(id) ON DELETE SET NULL,
  schedule_entry_id UUID REFERENCES workout_schedule_entries(id) ON DELETE SET NULL,
  activity_type VARCHAR(12) NOT NULL CHECK (activity_type IN ('GYM', 'YOGA')),
  start_at TIMESTAMPTZ NOT NULL,
  end_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'REQUESTED'
    CHECK (status IN ('REQUESTED', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'COMPLETED', 'NO_SHOW')),
  rejection_reason TEXT,
  cancellation_reason TEXT,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  response_due_at TIMESTAMPTZ,
  responded_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (end_at > start_at),
  CHECK (response_due_at IS NULL OR response_due_at > requested_at),
  CHECK (status <> 'REJECTED' OR NULLIF(BTRIM(rejection_reason), '') IS NOT NULL),
  CHECK (status <> 'COMPLETED' OR completed_at IS NOT NULL),
  EXCLUDE USING gist (
    trainer_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  ) WHERE (status IN ('REQUESTED', 'ACCEPTED') AND deleted_at IS NULL),
  EXCLUDE USING gist (
    member_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  ) WHERE (status IN ('REQUESTED', 'ACCEPTED') AND deleted_at IS NULL)
);

CREATE INDEX idx_pt_bookings_trainer_status_time
  ON pt_bookings (trainer_id, status, start_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_pt_bookings_member_status_time
  ON pt_bookings (member_id, status, start_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_pt_bookings_pending_expiry
  ON pt_bookings (response_due_at) WHERE status = 'REQUESTED' AND deleted_at IS NULL;

CREATE TABLE pt_credit_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  credit_account_id UUID NOT NULL REFERENCES pt_credit_accounts(id) ON DELETE RESTRICT,
  purchase_id UUID REFERENCES pt_credit_purchases(id) ON DELETE RESTRICT,
  booking_id UUID REFERENCES pt_bookings(id) ON DELETE RESTRICT,
  transaction_type VARCHAR(16) NOT NULL
    CHECK (transaction_type IN ('PURCHASE', 'RESERVE', 'RELEASE', 'CONSUME', 'REFUND', 'ADJUST')),
  purchased_delta INTEGER NOT NULL DEFAULT 0,
  reserved_delta INTEGER NOT NULL DEFAULT 0,
  used_delta INTEGER NOT NULL DEFAULT 0,
  purchased_balance INTEGER NOT NULL CHECK (purchased_balance >= 0),
  reserved_balance INTEGER NOT NULL CHECK (reserved_balance >= 0),
  used_balance INTEGER NOT NULL CHECK (used_balance >= 0),
  idempotency_key VARCHAR(100) NOT NULL UNIQUE,
  reason TEXT,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (purchased_delta <> 0 OR reserved_delta <> 0 OR used_delta <> 0),
  CHECK (purchased_balance >= reserved_balance + used_balance)
);

CREATE INDEX idx_pt_credit_ledger_account_time
  ON pt_credit_ledger (credit_account_id, created_at DESC);
CREATE INDEX idx_pt_credit_ledger_booking ON pt_credit_ledger (booking_id) WHERE booking_id IS NOT NULL;

-- ============================================================
-- Group classes
-- ============================================================

CREATE TABLE rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL,
  name VARCHAR(100) NOT NULL,
  capacity INTEGER NOT NULL CHECK (capacity > 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  UNIQUE (branch_id, code)
);

CREATE TABLE class_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  activity_type VARCHAR(12) NOT NULL CHECK (activity_type IN ('GYM', 'YOGA')),
  description TEXT,
  duration_minutes SMALLINT NOT NULL CHECK (duration_minutes > 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ
);

CREATE TABLE class_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  class_type_id UUID NOT NULL REFERENCES class_types(id) ON DELETE RESTRICT,
  trainer_id UUID NOT NULL REFERENCES trainer_profiles(id) ON DELETE RESTRICT,
  room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
  start_at TIMESTAMPTZ NOT NULL,
  end_at TIMESTAMPTZ NOT NULL,
  capacity INTEGER NOT NULL CHECK (capacity > 0),
  cancellation_deadline_at TIMESTAMPTZ,
  status VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED'
    CHECK (status IN ('SCHEDULED', 'CANCELLED', 'COMPLETED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (end_at > start_at),
  CHECK (cancellation_deadline_at IS NULL OR cancellation_deadline_at < start_at),
  EXCLUDE USING gist (
    trainer_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  ) WHERE (status = 'SCHEDULED' AND deleted_at IS NULL),
  EXCLUDE USING gist (
    room_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  ) WHERE (status = 'SCHEDULED' AND deleted_at IS NULL)
);

CREATE INDEX idx_class_sessions_start_status ON class_sessions (start_at, status) WHERE deleted_at IS NULL;

CREATE TABLE class_bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES class_sessions(id) ON DELETE RESTRICT,
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
  subscription_id UUID NOT NULL REFERENCES membership_subscriptions(id) ON DELETE RESTRICT,
  status VARCHAR(16) NOT NULL DEFAULT 'BOOKED'
    CHECK (status IN ('BOOKED', 'WAITLISTED', 'CANCELLED', 'ATTENDED', 'NO_SHOW')),
  waitlist_position INTEGER CHECK (waitlist_position IS NULL OR waitlist_position > 0),
  booked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  cancelled_at TIMESTAMPTZ,
  check_in_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  UNIQUE (session_id, member_id),
  CHECK ((status = 'WAITLISTED' AND waitlist_position IS NOT NULL) OR status <> 'WAITLISTED'),
  CHECK (cancelled_at IS NULL OR status = 'CANCELLED')
);

CREATE INDEX idx_class_bookings_session_status
  ON class_bookings (session_id, status, waitlist_position);
CREATE INDEX idx_class_bookings_member ON class_bookings (member_id, booked_at DESC);

-- ============================================================
-- Product catalog, inventory, cart and orders
-- ============================================================

CREATE TABLE product_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id UUID REFERENCES product_categories(id) ON DELETE SET NULL,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  activity_type VARCHAR(12) CHECK (activity_type IS NULL OR activity_type IN ('GYM', 'YOGA')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES product_categories(id) ON DELETE SET NULL,
  slug VARCHAR(180) NOT NULL UNIQUE,
  name VARCHAR(180) NOT NULL,
  description TEXT,
  brand VARCHAR(100),
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0)
);

CREATE INDEX idx_products_category_status ON products (category_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_name ON products (name) WHERE deleted_at IS NULL;

CREATE TABLE product_variants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
  sku VARCHAR(60) NOT NULL UNIQUE,
  name VARCHAR(120),
  attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  price NUMERIC(14,2) NOT NULL CHECK (price >= 0),
  compare_at_price NUMERIC(14,2) CHECK (compare_at_price IS NULL OR compare_at_price >= price),
  currency CHAR(3) NOT NULL DEFAULT 'VND',
  stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
  reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (stock_quantity >= reserved_quantity)
);

CREATE INDEX idx_product_variants_product ON product_variants (product_id) WHERE deleted_at IS NULL;

CREATE TABLE product_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  file_asset_id UUID NOT NULL REFERENCES file_assets(id) ON DELETE RESTRICT,
  alt_text VARCHAR(200),
  sort_order SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (product_id, file_asset_id)
);

CREATE TABLE carts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cart_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
  variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (cart_id, variant_id)
);

CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number VARCHAR(40) NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  member_id UUID REFERENCES members(id) ON DELETE SET NULL,
  payment_id UUID UNIQUE REFERENCES payments(id) ON DELETE RESTRICT,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING_PAYMENT'
    CHECK (status IN ('PENDING_PAYMENT', 'PAID', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED')),
  subtotal NUMERIC(14,2) NOT NULL CHECK (subtotal >= 0),
  discount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
  shipping_fee NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
  total NUMERIC(14,2) NOT NULL CHECK (total >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'VND',
  placed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (total = subtotal - discount + shipping_fee),
  CHECK (cancelled_at IS NULL OR status = 'CANCELLED')
);

CREATE INDEX idx_orders_user_created ON orders (user_id, created_at DESC);
CREATE INDEX idx_orders_status_created ON orders (status, created_at DESC);

CREATE TABLE order_addresses (
  order_id UUID PRIMARY KEY REFERENCES orders(id) ON DELETE RESTRICT,
  source_address_id UUID REFERENCES user_addresses(id) ON DELETE SET NULL,
  recipient_name VARCHAR(150) NOT NULL,
  recipient_phone VARCHAR(30) NOT NULL,
  province VARCHAR(100) NOT NULL,
  district VARCHAR(100) NOT NULL,
  ward VARCHAR(100) NOT NULL,
  address_line TEXT NOT NULL,
  delivery_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
  variant_id UUID REFERENCES product_variants(id) ON DELETE SET NULL,
  sku_snapshot VARCHAR(60) NOT NULL,
  product_name_snapshot VARCHAR(180) NOT NULL,
  variant_snapshot JSONB NOT NULL DEFAULT '{}'::JSONB,
  unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  line_total NUMERIC(14,2) GENERATED ALWAYS AS (unit_price * quantity) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_order_items_order ON order_items (order_id);

CREATE TABLE inventory_movements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
  movement_type VARCHAR(16) NOT NULL
    CHECK (movement_type IN ('IMPORT', 'RESERVE', 'RELEASE', 'SALE', 'RETURN', 'ADJUST')),
  quantity_delta INTEGER NOT NULL CHECK (quantity_delta <> 0),
  stock_balance INTEGER NOT NULL CHECK (stock_balance >= 0),
  reserved_balance INTEGER NOT NULL CHECK (reserved_balance >= 0 AND stock_balance >= reserved_balance),
  reason TEXT,
  idempotency_key VARCHAR(100) NOT NULL UNIQUE,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_inventory_movements_variant_time
  ON inventory_movements (variant_id, created_at DESC);

-- ============================================================
-- Invoices, equipment, notifications, jobs and audit
-- ============================================================

CREATE TABLE invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number VARCHAR(40) NOT NULL UNIQUE,
  member_id UUID REFERENCES members(id) ON DELETE SET NULL,
  payment_id UUID NOT NULL UNIQUE REFERENCES payments(id) ON DELETE RESTRICT,
  subtotal NUMERIC(14,2) NOT NULL CHECK (subtotal >= 0),
  tax NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax >= 0),
  discount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
  total NUMERIC(14,2) GENERATED ALWAYS AS (subtotal + tax - discount) STORED,
  currency CHAR(3) NOT NULL DEFAULT 'VND',
  status VARCHAR(12) NOT NULL DEFAULT 'DRAFT'
    CHECK (status IN ('DRAFT', 'ISSUED', 'PAID', 'VOID')),
  issued_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  pdf_file_id UUID REFERENCES file_assets(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (total >= 0),
  CHECK (issued_at IS NULL OR status IN ('ISSUED', 'PAID', 'VOID'))
);

CREATE TABLE equipment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
  asset_code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(150) NOT NULL,
  category VARCHAR(80) NOT NULL,
  location VARCHAR(150),
  purchase_date DATE,
  warranty_until DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'MAINTENANCE', 'OUT_OF_SERVICE', 'RETIRED')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMPTZ,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (warranty_until IS NULL OR purchase_date IS NULL OR warranty_until >= purchase_date)
);

CREATE INDEX idx_equipment_branch_status ON equipment (branch_id, status) WHERE deleted_at IS NULL;

CREATE TABLE maintenance_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
  scheduled_at TIMESTAMPTZ NOT NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  maintenance_type VARCHAR(80) NOT NULL,
  cost NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (cost >= 0),
  vendor VARCHAR(150),
  description TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED'
    CHECK (status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version > 0),
  CHECK (completed_at IS NULL OR started_at IS NOT NULL),
  CHECK (completed_at IS NULL OR completed_at >= started_at)
);

CREATE INDEX idx_maintenance_equipment_status
  ON maintenance_records (equipment_id, status, scheduled_at);

CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_type VARCHAR(50) NOT NULL,
  title VARCHAR(180) NOT NULL,
  body TEXT NOT NULL,
  data JSONB NOT NULL DEFAULT '{}'::JSONB,
  action_url TEXT,
  read_at TIMESTAMPTZ,
  email_status VARCHAR(16) NOT NULL DEFAULT 'NOT_REQUESTED'
    CHECK (email_status IN ('NOT_REQUESTED', 'PENDING', 'SENT', 'FAILED')),
  idempotency_key VARCHAR(120),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_notifications_idempotency
  ON notifications (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_notifications_user_unread
  ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;

CREATE TABLE background_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_job_id VARCHAR(100) UNIQUE,
  job_type VARCHAR(60) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')),
  progress SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
  parameters JSONB NOT NULL DEFAULT '{}'::JSONB,
  result_file_id UUID REFERENCES file_assets(id) ON DELETE SET NULL,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (finished_at IS NULL OR started_at IS NOT NULL),
  CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE INDEX idx_background_jobs_status_created ON background_jobs (status, created_at);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(80) NOT NULL,
  entity_id UUID,
  before_data JSONB,
  after_data JSONB,
  request_id UUID,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_logs_actor ON audit_logs (actor_user_id, created_at DESC);
CREATE INDEX idx_audit_logs_created ON audit_logs (created_at DESC);

-- Apply updated_at automatically. row_version is intentionally changed by
-- application updates using optimistic locking, never by this trigger.
DO $$
DECLARE
  table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'branches', 'users', 'user_profiles', 'user_addresses', 'members',
    'trainer_profiles', 'payments', 'membership_plans', 'membership_subscriptions',
    'workout_schedule_entries', 'check_ins', 'pt_credit_accounts',
    'pt_credit_purchases', 'trainer_availability', 'pt_bookings', 'rooms',
    'class_types', 'class_sessions', 'class_bookings', 'product_categories',
    'products', 'product_variants', 'carts', 'cart_items', 'orders', 'invoices',
    'equipment', 'maintenance_records', 'background_jobs'
  ]
  LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
      table_name,
      table_name
    );
  END LOOP;
END;
$$;

COMMIT;
