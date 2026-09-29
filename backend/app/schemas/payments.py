"""Schemas for QR bank-transfer checkout and the SePay webhook."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import MoneyOut, UtcDateTime


class PaymentBankInfo(BaseModel):
    """Receiving account shown next to the QR for manual transfers."""

    bank_code: str
    account_no: str
    account_name: str


class PaymentCheckoutResponse(BaseModel):
    """Everything the checkout screen needs, re-fetched while polling."""

    id: str
    payment_number: str
    purpose: str
    status: str
    amount: MoneyOut
    currency: str
    method: str
    # Nội dung chuyển khoản bắt buộc — webhook dùng nó để khớp giao dịch.
    transfer_content: str
    qr_image_url: str | None = None
    bank: PaymentBankInfo | None = None
    expires_at: UtcDateTime | None = None
    expired: bool = False
    paid_at: UtcDateTime | None = None
    simulation_enabled: bool = False


class SepayWebhookPayload(BaseModel):
    """Body SePay POSTs for every bank transaction on the linked account.

    Field names follow SePay's documentation; unknown fields are kept so the
    raw event stored in ``payment_events`` stays complete.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int | str
    gateway: str | None = None
    transaction_date: str | None = Field(default=None, alias="transactionDate")
    account_number: str | None = Field(default=None, alias="accountNumber")
    code: str | None = None
    content: str | None = None
    transfer_type: str | None = Field(default=None, alias="transferType")
    transfer_amount: Decimal = Field(default=Decimal("0"), alias="transferAmount")
    accumulated: Decimal | None = None
    sub_account: str | None = Field(default=None, alias="subAccount")
    reference_code: str | None = Field(default=None, alias="referenceCode")
    description: str | None = None


class WebhookAck(BaseModel):
    """SePay treats ``{"success": true}`` with HTTP 200 as delivered."""

    success: bool = True
    message: str | None = None
