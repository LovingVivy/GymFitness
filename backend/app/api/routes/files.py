"""File download endpoint.

Uploaded files are private by default, so a file is only served to its owner.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUserDep, DbDep
from app.core import storage
from app.repositories import profile as profile_repository

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}", summary="Tải nội dung tệp đã lưu")
def read_file(file_id: str, user: CurrentUserDep, db: DbDep) -> Response:
    record = profile_repository.get_file(db, file_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "FILE_NOT_FOUND", "message": "Không tìm thấy tệp.", "details": {}}
            },
        )

    if record["visibility"] != "PUBLIC" and record["owner_user_id"] != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Bạn không có quyền xem tệp này.",
                    "details": {},
                }
            },
        )

    content = storage.read_file(record["storage_key"])
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "FILE_MISSING",
                    "message": "Tệp không còn trên storage.",
                    "details": {},
                }
            },
        )

    return Response(
        content=content,
        media_type=record["content_type"],
        headers={
            "Cache-Control": "private, max-age=300",
            # Không cho trình duyệt đoán lại kiểu nội dung (chặn ảnh giả chứa HTML/JS).
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
