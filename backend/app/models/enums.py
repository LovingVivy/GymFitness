"""Shared string enum constants mirroring the MySQL CHECK constraints.

Column types stay as ``VARCHAR`` in the ORM so the models reflect the existing
bootstrap schema exactly; these enums are the single source of truth for the
allowed values used by services and validation logic.
"""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    USER = "USER"
    PT = "PT"


class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class ExperienceLevel(StrEnum):
    BEGINNER = "BEGINNER"
    BASIC = "BASIC"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class FitnessGoal(StrEnum):
    WEIGHT_LOSS = "WEIGHT_LOSS"
    MUSCLE_GAIN = "MUSCLE_GAIN"
    GENERAL_HEALTH = "GENERAL_HEALTH"
    FLEXIBILITY = "FLEXIBILITY"


class FileVisibility(StrEnum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class MemberStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class TrainerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    INACTIVE = "INACTIVE"


class Specialty(StrEnum):
    GYM = "GYM"
    YOGA = "YOGA"
    WEIGHT_LOSS = "WEIGHT_LOSS"
    MUSCLE_GAIN = "MUSCLE_GAIN"
    REHABILITATION = "REHABILITATION"
    FLEXIBILITY = "FLEXIBILITY"


class PaymentPurpose(StrEnum):
    MEMBERSHIP = "MEMBERSHIP"
    PT_CREDIT = "PT_CREDIT"
    PRODUCT_ORDER = "PRODUCT_ORDER"


class PaymentMethod(StrEnum):
    QR = "QR"
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    VOID = "VOID"


class ActivityType(StrEnum):
    GYM = "GYM"
    YOGA = "YOGA"


class SubscriptionStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class WorkoutEntryType(StrEnum):
    WORKOUT = "WORKOUT"
    REST = "REST"
    CLASS = "CLASS"
    PT_SESSION = "PT_SESSION"


class WorkoutEntryStatus(StrEnum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class WorkoutSource(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    PT = "PT"
    ADMIN = "ADMIN"


class CheckInMethod(StrEnum):
    QR = "QR"
    MANUAL = "MANUAL"


class PtPurchaseStatus(StrEnum):
    PENDING = "PENDING"
    CREDITED = "CREDITED"
    REFUNDED = "REFUNDED"
    VOID = "VOID"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"


class PtBookingStatus(StrEnum):
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class LedgerTransactionType(StrEnum):
    PURCHASE = "PURCHASE"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    CONSUME = "CONSUME"
    REFUND = "REFUND"
    ADJUST = "ADJUST"


class ClassSessionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ClassBookingStatus(StrEnum):
    BOOKED = "BOOKED"
    WAITLISTED = "WAITLISTED"
    CANCELLED = "CANCELLED"
    ATTENDED = "ATTENDED"
    NO_SHOW = "NO_SHOW"


class ProductStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class InventoryMovementType(StrEnum):
    IMPORT = "IMPORT"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    SALE = "SALE"
    RETURN = "RETURN"
    ADJUST = "ADJUST"


class InvoiceStatus(StrEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PAID = "PAID"
    VOID = "VOID"


class EquipmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    RETIRED = "RETIRED"


class MaintenanceStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EmailStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
