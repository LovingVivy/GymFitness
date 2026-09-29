"""Trainer endpoints: catalogue and free slots for members, "Lịch của bạn" for trainers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DbDep, TrainerDep
from app.schemas.pt import (
    BookableSlot,
    ScheduleResponse,
    ScheduleUpdateRequest,
    TimeOffCreateRequest,
    TrainerProfileResponse,
    TrainerSummary,
)
from app.services import pt as pt_service
from app.services import pt_schedule as schedule_service

router = APIRouter(prefix="/trainers", tags=["trainers"])

ActivityTypeQuery = Annotated[str | None, Query(description="Lọc theo chuyên môn: GYM hoặc YOGA")]


@router.get("", response_model=list[TrainerSummary], summary="Huấn luyện viên đã có lịch làm việc")
def list_trainers(db: DbDep, activity_type: ActivityTypeQuery = None) -> list[TrainerSummary]:
    return pt_service.list_trainers(db, activity_type)


@router.get("/me", response_model=TrainerProfileResponse, summary="Hồ sơ huấn luyện viên của tôi")
def read_my_trainer_profile(user: TrainerDep, db: DbDep) -> TrainerProfileResponse:
    return pt_service.get_my_trainer_profile(db, user["id"])


@router.get("/me/schedule", response_model=ScheduleResponse, summary="Lịch làm việc của tôi")
def read_my_schedule(user: TrainerDep, db: DbDep) -> ScheduleResponse:
    """Lịch tuần, lịch nghỉ sắp tới và các buổi đã đặt bị lệch khỏi lịch."""
    return schedule_service.get_my_schedule(db, user["id"])


@router.put("/me/schedule", response_model=ScheduleResponse, summary="Lưu lịch làm việc hằng tuần")
def save_my_schedule(
    payload: ScheduleUpdateRequest, user: TrainerDep, db: DbDep
) -> ScheduleResponse:
    """Thay toàn bộ lịch tuần. Buổi đã đặt giữ nguyên và được liệt kê trong ``conflicts``."""
    return schedule_service.save_my_schedule(db, user["id"], payload)


@router.post("/me/time-off", response_model=ScheduleResponse, summary="Thêm lịch nghỉ đột xuất")
def add_time_off(payload: TimeOffCreateRequest, user: TrainerDep, db: DbDep) -> ScheduleResponse:
    return schedule_service.add_time_off(db, user["id"], payload)


@router.delete(
    "/me/time-off/{time_off_id}", response_model=ScheduleResponse, summary="Xoá lịch nghỉ"
)
def remove_time_off(time_off_id: str, user: TrainerDep, db: DbDep) -> ScheduleResponse:
    return schedule_service.remove_time_off(db, user["id"], time_off_id)


@router.get(
    "/{trainer_id}/slots",
    response_model=list[BookableSlot],
    summary="Các ô còn trống của một huấn luyện viên",
)
def list_trainer_slots(trainer_id: str, user: CurrentUserDep, db: DbDep) -> list[BookableSlot]:
    """Ô cố định theo lịch tuần, đã trừ lịch nghỉ và buổi người khác đã đặt."""
    return schedule_service.list_bookable_slots(db, trainer_id)
