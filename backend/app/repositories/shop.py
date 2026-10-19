"""Data access for the shop catalogue. All SQL lives in ``database/09_admin_shop.sql``."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import ProcedureOutcome, call, outcome_from

LIST_PUBLIC = "sp_product_list_public"
LIST_ADMIN = "sp_admin_product_list"
SAVE_PRODUCT = "sp_admin_product_save"
DELETE_PRODUCT = "sp_admin_product_delete"
FIND_BY_SKU = "sp_admin_product_find_by_sku"


def list_public(db: Session) -> list[dict[str, Any]]:
    return call(db, LIST_PUBLIC, {})


def list_admin(
    db: Session,
    *,
    product_id: str | None = None,
    search: str | None,
    activity_type: str | None,
    status: str | None,
    sort: str | None = None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    return call(
        db,
        LIST_ADMIN,
        {
            "p_product_id": product_id,
            "p_search": search,
            "p_activity_type": activity_type,
            "p_status": status,
            "p_sort": sort,
            "p_limit": limit,
            "p_offset": offset,
        },
    )


def save_product(
    db: Session,
    *,
    product_id: str,
    variant_id: str,
    is_new: bool,
    slug: str,
    name: str,
    sku: str,
    category_name: str,
    activity_type: str,
    description: str | None,
    price: Decimal,
    stock: int,
    status: str,
    badge: str | None,
    art: str | None,
    expected_version: int | None = None,
    actor_id: str,
) -> ProcedureOutcome:
    rows = call(
        db,
        SAVE_PRODUCT,
        {
            "p_product_id": product_id,
            "p_variant_id": variant_id,
            "p_is_new": is_new,
            "p_slug": slug,
            "p_name": name,
            "p_sku": sku,
            "p_category_name": category_name,
            "p_activity_type": activity_type,
            "p_description": description,
            "p_price": price,
            "p_stock": stock,
            "p_status": status,
            "p_badge": badge,
            "p_art": art,
            "p_expected_version": expected_version,
            "p_actor_id": actor_id,
        },
    )
    return outcome_from(rows, "product_id")


def delete_product(db: Session, *, product_id: str, actor_id: str) -> ProcedureOutcome:
    rows = call(db, DELETE_PRODUCT, {"p_product_id": product_id, "p_actor_id": actor_id})
    return outcome_from(rows)


def find_by_sku(db: Session, sku: str) -> dict[str, Any] | None:
    rows = call(db, FIND_BY_SKU, {"p_sku": sku})
    return rows[0] if rows else None
