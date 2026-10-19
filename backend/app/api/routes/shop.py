"""Public shop catalogue. Product management lives in :mod:`app.api.routes.admin`."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbDep
from app.schemas.shop import ShopProduct
from app.services import shop as shop_service

router = APIRouter(tags=["shop"])


@router.get("/products", response_model=list[ShopProduct], summary="Sản phẩm đang bán")
def list_products(db: DbDep) -> list[ShopProduct]:
    return shop_service.list_products(db)
