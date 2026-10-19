"""Turn a list of rows into CSV, Excel or PDF bytes.

Every export (users, payments, check-ins, reports) describes its columns once
with :class:`Column`; the three writers below render the same data so the
files always agree with each other.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core import pdf
from app.core.gym_time import to_local

Kind = Literal["text", "money", "int", "datetime", "date"]
ExportFormat = Literal["csv", "xlsx", "pdf"]

CONTENT_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@dataclass(frozen=True)
class Column:
    key: str
    header: str
    kind: Kind = "text"
    width: float = 1.0
    value: Callable[[Mapping[str, Any]], Any] | None = None

    def raw(self, row: Mapping[str, Any]) -> Any:
        return self.value(row) if self.value else row.get(self.key)

    @property
    def numeric(self) -> bool:
        return self.kind in ("money", "int")


def _local(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return to_local(value).replace(tzinfo=None)


def display(column: Column, value: Any) -> str:
    """Human-readable text used by CSV and PDF."""
    if value is None or value == "":
        return ""
    if column.kind == "money":
        return pdf.money(value)
    if column.kind == "int":
        return str(int(value))
    if column.kind == "datetime":
        moment = _local(value)
        return f"{moment:%d/%m/%Y %H:%M}" if moment else ""
    if column.kind == "date":
        return value.strftime("%d/%m/%Y") if isinstance(value, date) else str(value)
    return str(value)


def to_csv(columns: Sequence[Column], rows: Sequence[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([column.header for column in columns])
    for row in rows:
        writer.writerow(
            [
                # Số tiền để dạng số thô cho Excel/Sheets tính toán được.
                str(Decimal(column.raw(row) or 0))
                if column.kind == "money"
                else display(column, column.raw(row))
                for column in columns
            ]
        )
    # BOM để Excel trên Windows nhận đúng UTF-8 (tiếng Việt có dấu).
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def to_xlsx(
    title: str, subtitle: str, columns: Sequence[Column], rows: Sequence[Mapping[str, Any]]
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]

    sheet.append([title])
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([subtitle])
    sheet["A2"].font = Font(italic=True, color="6B6B6B")
    sheet.append([])

    header_row = 4
    sheet.append([column.header for column in columns])
    for index in range(1, len(columns) + 1):
        cell = sheet.cell(row=header_row, column=index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="111111")
        cell.alignment = Alignment(vertical="center")

    for row in rows:
        values: list[Any] = []
        for column in columns:
            value = column.raw(row)
            if column.kind == "money":
                values.append(float(value) if value is not None else None)
            elif column.kind == "int":
                values.append(int(value) if value is not None else None)
            elif column.kind == "datetime":
                values.append(_local(value))
            else:
                values.append(value)
        sheet.append(values)

    for index, column in enumerate(columns, start=1):
        letter = get_column_letter(index)
        sheet.column_dimensions[letter].width = max(12, min(48, 14 * column.width))
        number_format = {
            "money": '#,##0 "đ"',
            "int": "0",
            "datetime": "dd/mm/yyyy hh:mm",
            "date": "dd/mm/yyyy",
        }.get(column.kind)
        if number_format:
            for (cell,) in sheet.iter_rows(min_row=header_row + 1, min_col=index, max_col=index):
                cell.number_format = number_format

    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    if rows:
        sheet.auto_filter.ref = (
            f"A{header_row}:{get_column_letter(len(columns))}{header_row + len(rows)}"
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def to_pdf(
    title: str, subtitle: str, columns: Sequence[Column], rows: Sequence[Mapping[str, Any]]
) -> bytes:
    return pdf.table_pdf(
        title,
        subtitle,
        [column.header for column in columns],
        [[display(column, column.raw(row)) for column in columns] for row in rows],
        [column.numeric for column in columns],
        [column.width for column in columns],
    )


def render(
    fmt: ExportFormat,
    title: str,
    subtitle: str,
    columns: Sequence[Column],
    rows: Sequence[Mapping[str, Any]],
) -> bytes:
    if fmt == "csv":
        return to_csv(columns, rows)
    if fmt == "xlsx":
        return to_xlsx(title, subtitle, columns, rows)
    return to_pdf(title, subtitle, columns, rows)
