"""Admin area: overview, accounts, plans, check-ins, reports, payments, shop, exports, audit.

Every route declares the permission it needs (RBAC, ADR-019). ADMIN has all of
them; MANAGER runs daily operations (members, check-ins, payments, shop,
reports) but cannot manage staff accounts, membership plans, voids or audit logs.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import DbDep, PermissionDep
from app.core.permissions import Permission
from app.schemas.admin import (
    AccountStatus,
    AdminOverview,
    AdminPasswordReset,
    AdminPayment,
    AdminPaymentPage,
    AdminPlan,
    AdminPlanSave,
    AdminUser,
    AdminUserCreate,
    AdminUserPage,
    AdminUserUpdate,
    AuditLogPage,
    CheckinCreate,
    CheckinCreated,
    CheckinPage,
    CheckinSort,
    MemberGrowthReport,
    PaymentConfirm,
    PaymentPurpose,
    PaymentSort,
    PaymentStatus,
    PaymentVoid,
    RevenuePeriod,
    RevenueReport,
    Role,
    UserSort,
)
from app.schemas.jobs import ExportRequest, JobResponse
from app.schemas.shop import (
    ActivityType,
    AdminProduct,
    AdminProductPage,
    AdminProductSave,
    ProductImportResult,
    ProductSort,
    ProductStatus,
)
from app.services import admin as admin_service
from app.services import exports as exports_service
from app.services import jobs as jobs_service
from app.services import shop as shop_service

router = APIRouter(prefix="/admin", tags=["admin"])

PageQuery = Annotated[int, Query(ge=1, le=10_000)]
PageSizeQuery = Annotated[int, Query(ge=1, le=200)]

DashboardView = PermissionDep(Permission.DASHBOARD_VIEW)
ReportsView = PermissionDep(Permission.REPORTS_VIEW)
ReportsExport = PermissionDep(Permission.REPORTS_EXPORT)
UsersView = PermissionDep(Permission.USERS_VIEW)
UsersManage = PermissionDep(Permission.USERS_MANAGE_MEMBERS)
UsersDelete = PermissionDep(Permission.USERS_DELETE)
PlansView = PermissionDep(Permission.PLANS_VIEW)
PlansManage = PermissionDep(Permission.PLANS_MANAGE)
CheckinsView = PermissionDep(Permission.CHECKINS_VIEW)
CheckinsManage = PermissionDep(Permission.CHECKINS_MANAGE)
PaymentsView = PermissionDep(Permission.PAYMENTS_VIEW)
PaymentsConfirm = PermissionDep(Permission.PAYMENTS_CONFIRM)
PaymentsVoid = PermissionDep(Permission.PAYMENTS_VOID)
ProductsView = PermissionDep(Permission.PRODUCTS_VIEW)
ProductsManage = PermissionDep(Permission.PRODUCTS_MANAGE)
AuditView = PermissionDep(Permission.AUDIT_VIEW)


@router.get("/overview", response_model=AdminOverview, summary="Số liệu tổng quan")
def read_overview(staff: DashboardView, db: DbDep) -> AdminOverview:
    return admin_service.overview(db)


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


@router.get("/users", response_model=AdminUserPage, summary="Danh sách tài khoản")
def list_users(
    staff: UsersView,
    db: DbDep,
    search: Annotated[str | None, Query(max_length=150)] = None,
    role: Role | None = None,
    account_status: Annotated[AccountStatus | None, Query(alias="status")] = None,
    sort: Annotated[UserSort | None, Query(description="Tiền tố '-' = giảm dần")] = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
) -> AdminUserPage:
    return admin_service.list_users(
        db,
        search=search,
        role=role,
        account_status=account_status,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/users",
    response_model=AdminUser,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản hội viên / PT / quản lý / quản trị",
)
def create_user(payload: AdminUserCreate, staff: UsersManage, db: DbDep) -> AdminUser:
    """Quản lý (MANAGER) chỉ tạo được tài khoản hội viên."""
    return admin_service.create_user(db, staff["id"], payload, staff["role"])


@router.patch("/users/{user_id}", response_model=AdminUser, summary="Sửa tài khoản")
def update_user(user_id: str, payload: AdminUserUpdate, staff: UsersManage, db: DbDep) -> AdminUser:
    return admin_service.update_user(db, staff["id"], user_id, payload, staff["role"])


@router.post(
    "/users/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đặt lại mật khẩu và mở khoá đăng nhập",
)
def reset_password(
    user_id: str, payload: AdminPasswordReset, staff: UsersManage, db: DbDep
) -> None:
    admin_service.reset_password(db, staff["id"], user_id, payload, staff["role"])


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá tài khoản")
def delete_user(user_id: str, admin: UsersDelete, db: DbDep) -> None:
    """Xoá mềm: giữ lịch sử thanh toán/gói tập, giải phóng email và số điện thoại."""
    admin_service.delete_user(db, admin["id"], user_id)


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


@router.get("/plans", response_model=list[AdminPlan], summary="Tất cả gói tập (kể cả đang ẩn)")
def list_plans(staff: PlansView, db: DbDep) -> list[AdminPlan]:
    return admin_service.list_plans(db)


@router.post(
    "/plans", response_model=AdminPlan, status_code=status.HTTP_201_CREATED, summary="Thêm gói"
)
def create_plan(payload: AdminPlanSave, admin: PlansManage, db: DbDep) -> AdminPlan:
    return admin_service.save_plan(db, admin["id"], payload)


@router.put("/plans/{plan_id}", response_model=AdminPlan, summary="Sửa gói tập")
def update_plan(plan_id: str, payload: AdminPlanSave, admin: PlansManage, db: DbDep) -> AdminPlan:
    """Đổi giá chỉ áp dụng cho lượt mua mới. Gửi ``row_version`` để không ghi đè người khác."""
    return admin_service.save_plan(db, admin["id"], payload, plan_id)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá gói")
def delete_plan(plan_id: str, admin: PlansManage, db: DbDep) -> None:
    admin_service.delete_plan(db, admin["id"], plan_id)


# --------------------------------------------------------------------------
# Check-in logs
# --------------------------------------------------------------------------


@router.get("/checkins", response_model=CheckinPage, summary="Lịch sử ra vào")
def list_checkins(
    staff: CheckinsView,
    db: DbDep,
    date_from: Annotated[date | None, Query(description="Ngày bắt đầu (giờ phòng tập)")] = None,
    date_to: Annotated[date | None, Query(description="Ngày kết thúc (giờ phòng tập)")] = None,
    search: Annotated[str | None, Query(max_length=150)] = None,
    inside_only: bool = False,
    sort: Annotated[CheckinSort | None, Query(description="Tiền tố '-' = giảm dần")] = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 30,
) -> CheckinPage:
    return admin_service.list_checkins(
        db,
        date_from=date_from,
        date_to=date_to,
        search=search,
        inside_only=inside_only,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/checkins",
    response_model=CheckinCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Check-in thủ công tại quầy",
)
def create_checkin(payload: CheckinCreate, staff: CheckinsManage, db: DbDep) -> CheckinCreated:
    return admin_service.create_checkin(db, staff["id"], payload)


@router.post(
    "/checkins/{checkin_id}/checkout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Check-out",
)
def checkout(checkin_id: str, staff: CheckinsManage, db: DbDep) -> None:
    admin_service.checkout(db, staff["id"], checkin_id)


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


@router.get("/revenue", response_model=RevenueReport, summary="Báo cáo doanh thu")
def revenue(
    staff: ReportsView,
    db: DbDep,
    period: RevenuePeriod = "MONTH",
    count: Annotated[int | None, Query(ge=1, le=60, description="Số kỳ gần nhất")] = None,
) -> RevenueReport:
    """Doanh thu từ payment đã PAID, gom theo tuần/tháng/quý/năm (giờ phòng tập). Có cache."""
    return admin_service.revenue_report(db, period, count)


@router.get("/members/growth", response_model=MemberGrowthReport, summary="Tăng trưởng hội viên")
def member_growth(
    staff: ReportsView,
    db: DbDep,
    period: RevenuePeriod = "MONTH",
    count: Annotated[int | None, Query(ge=1, le=60, description="Số kỳ gần nhất")] = None,
) -> MemberGrowthReport:
    """Hội viên mới theo tuần/tháng/quý/năm và tổng hội viên cộng dồn. Có cache."""
    return admin_service.member_growth(db, period, count)


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


@router.get("/payments", response_model=AdminPaymentPage, summary="Danh sách giao dịch")
def list_payments(
    staff: PaymentsView,
    db: DbDep,
    search: Annotated[str | None, Query(max_length=150)] = None,
    payment_status: Annotated[PaymentStatus | None, Query(alias="status")] = None,
    purpose: PaymentPurpose | None = None,
    date_from: Annotated[date | None, Query(description="Ngày tạo từ (giờ phòng tập)")] = None,
    date_to: Annotated[date | None, Query(description="Ngày tạo đến (giờ phòng tập)")] = None,
    sort: Annotated[PaymentSort | None, Query(description="Tiền tố '-' = giảm dần")] = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
) -> AdminPaymentPage:
    return admin_service.list_payments(
        db,
        search=search,
        payment_status=payment_status,
        purpose=purpose,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/payments/{payment_id}/confirm",
    response_model=AdminPayment,
    summary="Xác nhận đã thu tiền và kích hoạt quyền lợi",
)
def confirm_payment(
    payment_id: str, staff: PaymentsConfirm, db: DbDep, payload: PaymentConfirm | None = None
) -> AdminPayment:
    """Dùng khi thu tiền mặt tại quầy hoặc đối soát khoản chuyển mà webhook không khớp."""
    return admin_service.confirm_payment(db, staff["id"], payment_id, payload or PaymentConfirm())


@router.post(
    "/payments/{payment_id}/void",
    response_model=AdminPayment,
    summary="Huỷ giao dịch đang chờ thanh toán",
)
def void_payment(
    payment_id: str, admin: PaymentsVoid, db: DbDep, payload: PaymentVoid | None = None
) -> AdminPayment:
    return admin_service.void_payment(db, admin["id"], payment_id, payload or PaymentVoid())


# --------------------------------------------------------------------------
# Shop
# --------------------------------------------------------------------------


@router.get("/products", response_model=AdminProductPage, summary="Sản phẩm (kể cả đang ẩn)")
def list_products(
    staff: ProductsView,
    db: DbDep,
    search: Annotated[str | None, Query(max_length=150)] = None,
    activity_type: ActivityType | None = None,
    product_status: Annotated[ProductStatus | None, Query(alias="status")] = None,
    sort: Annotated[ProductSort | None, Query(description="Tiền tố '-' = giảm dần")] = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
) -> AdminProductPage:
    return shop_service.list_admin_products(
        db,
        search=search,
        activity_type=activity_type,
        product_status=product_status,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/products",
    response_model=AdminProduct,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm sản phẩm",
)
def create_product(payload: AdminProductSave, staff: ProductsManage, db: DbDep) -> AdminProduct:
    return shop_service.save_product(db, staff["id"], payload)


@router.get(
    "/products/import-template",
    summary="Tải file mẫu để nhập sản phẩm",
    response_class=Response,
)
def product_import_template(
    staff: ProductsManage,
    file_format: Annotated[Literal["xlsx", "csv"], Query(alias="format")] = "xlsx",
) -> Response:
    filename, content_type, content = shop_service.import_template(file_format)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/products/import",
    response_model=ProductImportResult,
    summary="Nhập sản phẩm từ Excel (.xlsx) hoặc CSV",
)
async def import_products(
    staff: ProductsManage, db: DbDep, file: Annotated[UploadFile, File()]
) -> ProductImportResult:
    """SKU đã có thì cập nhật, chưa có thì tạo mới. Dòng lỗi được trả về, các dòng khác vẫn lưu."""
    content = await file.read(shop_service.MAX_IMPORT_BYTES + 1)
    return shop_service.import_products(db, staff["id"], file.filename or "", content)


@router.put("/products/{product_id}", response_model=AdminProduct, summary="Sửa sản phẩm")
def update_product(
    product_id: str, payload: AdminProductSave, staff: ProductsManage, db: DbDep
) -> AdminProduct:
    """Thay đổi tồn kho được ghi vào sổ kho. Gửi ``row_version`` để không ghi đè người khác."""
    return shop_service.save_product(db, staff["id"], payload, product_id)


@router.delete(
    "/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá sản phẩm"
)
def delete_product(product_id: str, staff: ProductsManage, db: DbDep) -> None:
    shop_service.delete_product(db, staff["id"], product_id)


# --------------------------------------------------------------------------
# Exports and background jobs
# --------------------------------------------------------------------------


@router.post(
    "/exports",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Xuất dữ liệu ra CSV / Excel / PDF (chạy nền)",
)
def start_export(payload: ExportRequest, staff: ReportsExport, db: DbDep) -> JobResponse:
    """Trả tác vụ PENDING; gọi ``GET /admin/jobs/{id}`` tới khi ``SUCCESS`` rồi tải file."""
    return exports_service.start(db, staff, payload)


@router.get("/jobs", response_model=list[JobResponse], summary="Tác vụ nền gần đây của tôi")
def list_jobs(
    staff: DashboardView,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[JobResponse]:
    return jobs_service.list_jobs(db, staff, "export.", limit)


@router.get("/jobs/{job_id}", response_model=JobResponse, summary="Trạng thái một tác vụ nền")
def read_job(job_id: str, staff: DashboardView, db: DbDep) -> JobResponse:
    return jobs_service.get_job(db, staff, job_id)


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------


@router.get("/audit-logs", response_model=AuditLogPage, summary="Nhật ký thao tác")
def list_audit_logs(
    admin: AuditView,
    db: DbDep,
    entity_type: Annotated[str | None, Query(max_length=80)] = None,
    entity_id: Annotated[str | None, Query(max_length=36)] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    search: Annotated[str | None, Query(max_length=150)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 30,
) -> AuditLogPage:
    """Ai làm gì, lúc nào; ``before_data``/``after_data`` là lịch sử phiên bản của bản ghi."""
    return admin_service.list_audit_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        search=search,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
