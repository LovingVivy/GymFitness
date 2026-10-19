"""PDF rendering: invoices and tabular reports, with Vietnamese text.

ReportLab's built-in fonts have no Vietnamese glyphs, so a TTF font is
registered: ``PDF_FONT_PATH`` if set, else DejaVu Sans (Docker image, most
Linux) or Arial (Windows/macOS). Without any of them the text is written
without diacritics rather than as empty boxes.
"""

from __future__ import annotations

import io
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#6b6b6b")
LINE = colors.HexColor("#d9d9d9")
ACCENT = colors.HexColor("#c8102e")
ZEBRA = colors.HexColor("#f6f6f6")

_CANDIDATES = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
)


@dataclass(frozen=True)
class Fonts:
    regular: str
    bold: str
    unicode: bool


@lru_cache
def fonts() -> Fonts:
    configured = get_settings().pdf_font_path.strip()
    candidates = ((configured, configured),) if configured else ()
    for regular, bold in (*candidates, *_CANDIDATES):
        if not Path(regular).is_file():
            continue
        pdfmetrics.registerFont(TTFont("GF-Regular", regular))
        bold_path = bold if Path(bold).is_file() else regular
        pdfmetrics.registerFont(TTFont("GF-Bold", bold_path))
        # Để thẻ <b> trong Paragraph dùng đúng font đậm.
        registerFontFamily(
            "GF-Regular",
            normal="GF-Regular",
            bold="GF-Bold",
            italic="GF-Regular",
            boldItalic="GF-Bold",
        )
        return Fonts("GF-Regular", "GF-Bold", True)
    return Fonts("Helvetica", "Helvetica-Bold", False)


def text(value: object) -> str:
    """Escape for Paragraph markup and drop diacritics if no Unicode font exists."""
    raw = "" if value is None else str(value)
    if not fonts().unicode:
        folded = unicodedata.normalize("NFD", raw.replace("đ", "d").replace("Đ", "D"))
        raw = "".join(char for char in folded if not unicodedata.combining(char))
    return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def money(value: Decimal | float | int | None) -> str:
    amount = Decimal(value or 0)
    return f"{amount:,.0f} đ".replace(",", ".")


def _styles() -> dict[str, ParagraphStyle]:
    font = fonts()
    return {
        "brand": ParagraphStyle(
            "brand", fontName=font.bold, fontSize=20, leading=24, textColor=INK
        ),
        "title": ParagraphStyle(
            "title", fontName=font.bold, fontSize=14, leading=18, textColor=INK
        ),
        "body": ParagraphStyle(
            "body", fontName=font.regular, fontSize=9.5, leading=13, textColor=INK
        ),
        "muted": ParagraphStyle(
            "muted", fontName=font.regular, fontSize=8.5, leading=11, textColor=MUTED
        ),
        "cell": ParagraphStyle("cell", fontName=font.regular, fontSize=8.5, leading=11),
        "cell_right": ParagraphStyle(
            "cell_right", fontName=font.regular, fontSize=8.5, leading=11, alignment=TA_RIGHT
        ),
        "head": ParagraphStyle(
            "head", fontName=font.bold, fontSize=8.5, leading=11, textColor=colors.white
        ),
        "head_right": ParagraphStyle(
            "head_right",
            fontName=font.bold,
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
        "total": ParagraphStyle(
            "total", fontName=font.bold, fontSize=11, leading=14, alignment=TA_RIGHT
        ),
    }


def _footer(label: str):
    def draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(fonts().regular, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, 10 * mm, text(label).replace("&amp;", "&"))
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 10 * mm, f"Trang {doc.page}")
        canvas.restoreState()

    return draw


# --------------------------------------------------------------------------
# Invoice
# --------------------------------------------------------------------------


@dataclass
class InvoiceLine:
    description: str
    quantity: int
    unit_price: Decimal

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class InvoiceData:
    invoice_number: str
    issued_at: datetime
    payment_number: str
    status: str
    method: str
    paid_at: datetime | None
    customer_name: str
    customer_code: str | None
    customer_email: str | None
    customer_phone: str | None
    branch_name: str
    branch_address: str
    lines: list[InvoiceLine] = field(default_factory=list)
    total: Decimal = Decimal(0)


def invoice_pdf(data: InvoiceData) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Hoá đơn {data.invoice_number}",
        author="IRONIX Fitness",
    )
    s = _styles()
    width = doc.width

    header = Table(
        [
            [
                Paragraph("IRONIX <font color='#c8102e'>FITNESS</font>", s["brand"]),
                Paragraph(text("HOÁ ĐƠN THANH TOÁN"), s["title"]),
            ],
            [
                Paragraph(f"{text(data.branch_name)}<br/>{text(data.branch_address)}", s["muted"]),
                Paragraph(
                    text(f"Số: {data.invoice_number}")
                    + "<br/>"
                    + text(f"Ngày lập: {data.issued_at:%d/%m/%Y %H:%M}"),
                    s["body"],
                ),
            ],
        ],
        colWidths=[width * 0.58, width * 0.42],
    )
    header.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])
    )

    customer = [
        f"<b>{text('Khách hàng')}:</b> {text(data.customer_name)}",
        f"<b>{text('Mã hội viên')}:</b> {text(data.customer_code or '—')}",
        f"<b>Email:</b> {text(data.customer_email or '—')}",
        f"<b>{text('Điện thoại')}:</b> {text(data.customer_phone or '—')}",
    ]
    payment = [
        f"<b>{text('Mã giao dịch')}:</b> {text(data.payment_number)}",
        f"<b>{text('Hình thức')}:</b> {text(data.method)}",
        f"<b>{text('Trạng thái')}:</b> {text(data.status)}",
        f"<b>{text('Thanh toán lúc')}:</b> "
        + text(f"{data.paid_at:%d/%m/%Y %H:%M}" if data.paid_at else "—"),
    ]
    parties = Table(
        [
            [
                Paragraph("<br/>".join(customer), s["body"]),
                Paragraph("<br/>".join(payment), s["body"]),
            ]
        ],
        colWidths=[width * 0.5, width * 0.5],
    )
    parties.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    rows = [
        [
            Paragraph("#", s["head"]),
            Paragraph(text("Nội dung"), s["head"]),
            Paragraph("SL", s["head_right"]),
            Paragraph(text("Đơn giá"), s["head_right"]),
            Paragraph(text("Thành tiền"), s["head_right"]),
        ]
    ]
    for index, line in enumerate(data.lines, start=1):
        rows.append(
            [
                Paragraph(str(index), s["cell"]),
                Paragraph(text(line.description), s["cell"]),
                Paragraph(str(line.quantity), s["cell_right"]),
                Paragraph(text(money(line.unit_price)), s["cell_right"]),
                Paragraph(text(money(line.total)), s["cell_right"]),
            ]
        )
    items = Table(
        rows, colWidths=[width * 0.06, width * 0.46, width * 0.1, width * 0.19, width * 0.19]
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    total = Paragraph(text(f"Tổng cộng: {money(data.total)}"), s["total"])
    note = Paragraph(
        text(
            "Hoá đơn được tạo tự động từ hệ thống IRONIX Fitness. Giá đã bao gồm thuế (nếu có). "
            "Vui lòng giữ hoá đơn để đối chiếu khi cần hỗ trợ."
        ),
        s["muted"],
    )
    doc.build(
        [
            header,
            Spacer(1, 8 * mm),
            parties,
            Spacer(1, 7 * mm),
            items,
            Spacer(1, 4 * mm),
            total,
            Spacer(1, 10 * mm),
            note,
        ],
        onFirstPage=_footer(f"IRONIX Fitness · {data.invoice_number}"),
        onLaterPages=_footer(f"IRONIX Fitness · {data.invoice_number}"),
    )
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Tabular report
# --------------------------------------------------------------------------


def table_pdf(
    title: str,
    subtitle: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    numeric: Sequence[bool],
    widths: Sequence[float] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    pagesize = landscape(A4) if len(headers) > 5 else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="IRONIX Fitness",
    )
    s = _styles()
    ratio = widths or [1] * len(headers)
    col_widths = [doc.width * value / sum(ratio) for value in ratio]

    data = [
        [
            Paragraph(text(header), s["head_right" if is_num else "head"])
            for header, is_num in zip(headers, numeric, strict=True)
        ]
    ]
    for row in rows:
        data.append(
            [
                Paragraph(text(cell), s["cell_right" if is_num else "cell"])
                for cell, is_num in zip(row, numeric, strict=True)
            ]
        )
    if len(data) == 1:
        data.append([Paragraph(text("Không có dữ liệu."), s["cell"])] + [""] * (len(headers) - 1))

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    doc.build(
        [
            Paragraph("IRONIX <font color='#c8102e'>FITNESS</font>", s["brand"]),
            Spacer(1, 2 * mm),
            Paragraph(text(title), s["title"]),
            Paragraph(text(subtitle), s["muted"]),
            Spacer(1, 5 * mm),
            table,
        ],
        onFirstPage=_footer(f"IRONIX Fitness · {title}"),
        onLaterPages=_footer(f"IRONIX Fitness · {title}"),
    )
    return buffer.getvalue()
