"""标签 PDF 生成服务。

按标签尺寸生成单页 PDF，内容与前端标签预览一致：二维码、辅料中文名、生成时间。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import qrcode
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_NAME = "LabelCJK"
_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)
_font_registered = False


class LabelPdfError(RuntimeError):
    pass


@dataclass(frozen=True)
class LabelPdfRequest:
    label_id: str
    material_name: str
    material_code: str
    printed_at: datetime
    width_mm: int
    height_mm: int


def _ensure_font() -> str:
    global _font_registered
    if _font_registered:
        return FONT_NAME
    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(path)))
                _font_registered = True
                return FONT_NAME
            except Exception:
                continue
    raise LabelPdfError("未找到可用的中文字体，无法生成标签 PDF")


def parse_label_size(value: str | None) -> tuple[int, int]:
    text = (value or "60x40").strip().lower().replace("×", "x")
    try:
        width_text, height_text = text.split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError):
        return 60, 40
    if not 10 <= width <= 300 or not 10 <= height <= 300:
        return 60, 40
    return width, height


def _qr_image(payload: str) -> ImageReader:
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def render_label_pdf(request: LabelPdfRequest) -> bytes:
    """Render a single label as a one-page PDF sized to the label dimensions."""
    return _render_pages([request])


def render_labels_pdf(requests: list[LabelPdfRequest]) -> bytes:
    """Render multiple labels into a single multi-page PDF."""
    if not requests:
        raise LabelPdfError("没有可导出的标签")
    return _render_pages(requests)


def _render_pages(requests: list[LabelPdfRequest]) -> bytes:
    font = _ensure_font()
    first = requests[0]
    width = first.width_mm * mm
    height = first.height_mm * mm
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setTitle(f"{first.material_name}-标签")

    for request in requests:
        page_width = request.width_mm * mm
        page_height = request.height_mm * mm
        pdf.setPageSize((page_width, page_height))
        margin = 2 * mm
        qr_size = min(page_height - 2 * margin, page_width * 0.42)
        qr = _qr_image(request.label_id)
        pdf.drawImage(
            qr,
            margin,
            (page_height - qr_size) / 2,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )

        text_x = margin + qr_size + 2 * mm
        text_width = page_width - text_x - margin
        name_size = max(7, min(14, page_height / mm * 0.28))
        pdf.setFont(font, name_size)
        pdf.drawString(
            text_x,
            page_height - margin - name_size,
            _fit_text(pdf, request.material_name, font, name_size, text_width),
        )

        pdf.setFont(font, max(5, name_size * 0.55))
        pdf.drawString(text_x, page_height - margin - name_size * 2.1, request.material_code)

        pdf.setFont(font, max(4.5, name_size * 0.45))
        stamp = request.printed_at.astimezone().strftime("%Y-%m-%d %H:%M")
        pdf.drawString(text_x, margin, stamp)

        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _fit_text(pdf: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> str:
    if pdf.stringWidth(text, font, size) <= max_width:
        return text
    trimmed = text
    while trimmed and pdf.stringWidth(trimmed + "…", font, size) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else text[:1]
