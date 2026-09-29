from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.files import router as files_router
from app.api.routes.health import router as health_router
from app.api.routes.membership import router as membership_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.payments import router as payments_router
from app.api.routes.profile import router as profile_router
from app.api.routes.pt import router as pt_router
from app.api.routes.trainers import router as trainers_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profile_router, prefix="/api/v1")
api_router.include_router(membership_router, prefix="/api/v1")
api_router.include_router(payments_router, prefix="/api/v1")
api_router.include_router(files_router, prefix="/api/v1")
api_router.include_router(trainers_router, prefix="/api/v1")
api_router.include_router(pt_router, prefix="/api/v1")
api_router.include_router(notifications_router, prefix="/api/v1")
