import logging
import secrets
from decimal import Decimal
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

logger = logging.getLogger(__name__)

# Môi trường được phép chạy với cấu hình "cho dev" (secret yếu, giả lập thanh toán).
DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test"})

JWT_SECRET_MIN_LENGTH = 32

# Các giá trị mẫu từng xuất hiện trong repo: ai đọc được repo là giả mạo được token.
_KNOWN_WEAK_JWT_SECRETS = frozenset(
    {
        "",
        "dev-secret-change-me",
        "change-me-to-a-long-random-secret",
        "secret",
        "changeme",
        "change_me",
    }
)


class Settings(BaseSettings):
    app_name: str = "GymFitness API"
    app_env: str = "development"
    docs_enabled: bool = True
    frontend_origins: list[str] = ["http://localhost:5173"]
    database_url: str | None = None
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "gymfitness_app"
    mysql_password: str = ""
    mysql_database: str = "gymfitness"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret_key: str = ""
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    login_max_failed_attempts: int = 5
    login_lock_minutes: int = 15
    storage_root: str = "storage"

    # --- Thanh toán chuyển khoản QR (VietQR + webhook SePay) -----------------
    # Mã ngân hàng theo VietQR (vd. "MB", "VCB", "970422") và tài khoản nhận tiền.
    payment_bank_code: str = ""
    payment_account_no: str = ""
    payment_account_name: str = ""
    # Tiền tố mã thanh toán in trong nội dung chuyển khoản, vd. IRX260928A1B2C3.
    payment_code_prefix: str = "IRX"
    # API key cấu hình ở SePay (Webhook → Chứng thực "API Key").
    sepay_webhook_api_key: str = ""
    # None = tự bật ở môi trường dev, tắt ở production.
    payment_simulation_enabled: bool | None = None

    # --- Lịch PT ------------------------------------------------------------
    # Giờ địa phương của phòng tập so với UTC (Việt Nam UTC+7, không đổi giờ mùa hè).
    gym_utc_offset_minutes: int = 420
    pt_session_price: int = 200_000
    pt_session_minutes: int = 60
    # Hội viên chỉ đặt được buổi bắt đầu sau ít nhất N phút và trong vòng N ngày tới.
    pt_booking_min_lead_minutes: int = 120
    pt_booking_horizon_days: int = 14
    # Huỷ trước giờ tập tối thiểu N giờ thì được hoàn lượt.
    pt_cancel_refund_hours: int = 12

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Biến để trống (vd. PAYMENT_SIMULATION_ENABLED=) dùng giá trị mặc định.
        env_ignore_empty=True,
        extra="ignore",
    )

    @property
    def is_development(self) -> bool:
        return self.app_env.strip().lower() in DEV_ENVIRONMENTS

    @property
    def allow_payment_simulation(self) -> bool:
        if self.payment_simulation_enabled is None:
            return self.is_development
        return self.payment_simulation_enabled

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "Settings":
        secret = self.jwt_secret_key.strip()
        weak = secret.lower() in _KNOWN_WEAK_JWT_SECRETS or len(secret) < JWT_SECRET_MIN_LENGTH

        if not weak:
            return self

        if not self.is_development:
            raise ValueError(
                "JWT_SECRET_KEY chưa được cấu hình an toàn: cần chuỗi ngẫu nhiên tối thiểu "
                f"{JWT_SECRET_MIN_LENGTH} ký tự khi APP_ENV={self.app_env}. "
                'Tạo bằng: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )

        if not secret:
            # Dev chưa đặt secret: dùng khoá ngẫu nhiên theo tiến trình để không bao giờ
            # ký bằng khoá rỗng. Token sẽ mất hiệu lực mỗi lần khởi động lại.
            self.jwt_secret_key = secrets.token_urlsafe(64)
            logger.warning("JWT_SECRET_KEY trống — đang dùng khoá tạm thời cho phiên dev này.")
        else:
            logger.warning("JWT_SECRET_KEY yếu hoặc là giá trị mẫu — chỉ chấp nhận ở dev.")
        return self

    @property
    def sqlalchemy_database_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def pt_session_price() -> Decimal:
    return Decimal(get_settings().pt_session_price)
