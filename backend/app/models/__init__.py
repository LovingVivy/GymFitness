"""Import ORM models here so Alembic and the ORM can discover every table."""

from app.models.accounts import (
    PasswordResetToken,
    RefreshToken,
    User,
    UserAddress,
    UserProfile,
)
from app.models.billing import Invoice, Payment, PaymentEvent
from app.models.checkin import CheckIn, QrNonce
from app.models.classes import ClassBooking, ClassSession, ClassType, Room
from app.models.commerce import (
    Cart,
    CartItem,
    InventoryMovement,
    Order,
    OrderAddress,
    OrderItem,
    Product,
    ProductCategory,
    ProductImage,
    ProductVariant,
)
from app.models.member import Member
from app.models.membership import (
    MembershipPlan,
    MembershipSubscription,
    SubscriptionFreezeHistory,
    SubscriptionStatusHistory,
    WorkoutScheduleEntry,
)
from app.models.operations import (
    AuditLog,
    BackgroundJob,
    Equipment,
    MaintenanceRecord,
    Notification,
)
from app.models.organization import Branch, FileAsset
from app.models.pt import (
    PtBooking,
    PtCreditAccount,
    PtCreditLedger,
    PtCreditPurchase,
    TrainerAvailability,
    TrainerTimeOff,
    TrainerWeeklySchedule,
)
from app.models.trainer import TrainerProfile, TrainerSpecialty

__all__ = [
    "AuditLog",
    "BackgroundJob",
    "Branch",
    "Cart",
    "CartItem",
    "CheckIn",
    "ClassBooking",
    "ClassSession",
    "ClassType",
    "Equipment",
    "FileAsset",
    "InventoryMovement",
    "Invoice",
    "MaintenanceRecord",
    "Member",
    "MembershipPlan",
    "MembershipSubscription",
    "Notification",
    "Order",
    "OrderAddress",
    "OrderItem",
    "PasswordResetToken",
    "Payment",
    "PaymentEvent",
    "Product",
    "ProductCategory",
    "ProductImage",
    "ProductVariant",
    "PtBooking",
    "PtCreditAccount",
    "PtCreditLedger",
    "PtCreditPurchase",
    "QrNonce",
    "RefreshToken",
    "Room",
    "SubscriptionFreezeHistory",
    "SubscriptionStatusHistory",
    "TrainerAvailability",
    "TrainerTimeOff",
    "TrainerWeeklySchedule",
    "TrainerProfile",
    "TrainerSpecialty",
    "User",
    "UserAddress",
    "UserProfile",
    "WorkoutScheduleEntry",
]
