"""
pdf_builder.py — Tạo file PDF với hỗ trợ tiếng Việt (Unicode)
Dùng reportlab + font DejaVuSans.
"""
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Font cho PDF tiếng Việt
# Primary: Noto Serif (serif đẹp, phù hợp đọc truyện, hỗ trợ đầy đủ tiếng Việt)
# Fallback: DejaVu Sans
FONT_DIR = Path(__file__).parent / "fonts"

_FONT_SOURCES = [
    # (regular_name, bold_name, regular_url, bold_url)
    (
        "NotoSerif-Regular.ttf",
        "NotoSerif-Bold.ttf",
        "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/NotoSerif/unhinted/ttf/NotoSerif-Regular.ttf",
        "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/NotoSerif/unhinted/ttf/NotoSerif-Bold.ttf",
    ),
    (
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf",
        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37/ttf/DejaVuSans.ttf",
        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37/ttf/DejaVuSans-Bold.ttf",
    ),
]

FONT_REGULAR: Path | None = None
FONT_BOLD: Path | None = None

_fonts_registered = False


def _try_download_font_set(reg_name, bold_name, reg_url, bold_url) -> bool:
    """Thử tải 1 bộ font (regular + bold). Trả về True nếu thành công."""
    from fetcher import get_scraper
    scraper = get_scraper()
    for fname, url in ((reg_name, reg_url), (bold_name, bold_url)):
        fpath = FONT_DIR / fname
        if not fpath.exists():
            logger.info(f"Đang tải font {fname} ...")
            try:
                resp = scraper.get(url, timeout=30)
                resp.raise_for_status()
                if len(resp.content) < 10_000:
                    raise ValueError(f"File quá nhỏ ({len(resp.content)} bytes), có thể lỗi")
                fpath.write_bytes(resp.content)
                logger.info(f"Đã tải {fname} ({len(resp.content) // 1024} KB)")
            except Exception as e:
                logger.warning(f"Không tải được {fname} từ {url}: {e}")
                if fpath.exists():
                    fpath.unlink()
                return False
    return True


def _ensure_fonts() -> bool:
    """Tải và đăng ký font tiếng Việt. Thử từng bộ theo thứ tự ưu tiên."""
    global _fonts_registered, FONT_REGULAR, FONT_BOLD
    if _fonts_registered:
        return True

    FONT_DIR.mkdir(exist_ok=True)

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for reg_name, bold_name, reg_url, bold_url in _FONT_SOURCES:
        reg_path = FONT_DIR / reg_name
        bold_path = FONT_DIR / bold_name

        # Tải nếu chưa có
        if not reg_path.exists() or not bold_path.exists():
            ok = _try_download_font_set(reg_name, bold_name, reg_url, bold_url)
            if not ok:
                continue

        # Đăng ký với reportlab
        try:
            font_id = reg_name.replace(".ttf", "")
            bold_id = bold_name.replace(".ttf", "")
            pdfmetrics.registerFont(TTFont(font_id, str(reg_path)))
            pdfmetrics.registerFont(TTFont(bold_id, str(bold_path)))
            FONT_REGULAR = reg_path
            FONT_BOLD = bold_path
            _fonts_registered = True
            logger.info(f"Dùng font: {font_id}")
            return True
        except Exception as e:
            logger.warning(f"Không đăng ký được font {reg_name}: {e}")

    logger.error("Không tải được bất kỳ font nào, PDF sẽ dùng Helvetica (không hỗ trợ tiếng Việt)")
    return False


def build_pdf(
    output_path: Path,
    novel_info: dict,
    volume_title: str,
    chapters_data: list[dict],
    cover_bytes: bytes | None,
    image_cache: dict[str, bytes],
) -> None:
    """
    Tạo file PDF.

    chapters_data: list of {title, elements: [{type, content|url}]}
    image_cache: {url: bytes}
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
        PageBreak, HRFlowable
    )
    from reportlab.platypus.tableofcontents import TableOfContents

    fonts_ok = _ensure_fonts()
    if fonts_ok and FONT_REGULAR:
        font_name = FONT_REGULAR.stem   # e.g. "NotoSerif-Regular" hoặc "DejaVuSans"
        font_bold = FONT_BOLD.stem
    else:
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"

    styles = _build_styles(font_name, font_bold)
    story = []

    # Trang bìa
    _add_pdf_cover(story, novel_info, volume_title, cover_bytes, styles)

    # Các chương
    for chap_idx, chap in enumerate(chapters_data):
        chap_title = chap.get("title", f"Chương {chap_idx + 1}")
        elements = chap.get("elements", [])

        story.append(PageBreak())
        story.append(Paragraph(chap_title, styles["ChapterTitle"]))
        story.append(Spacer(1, 0.3 * cm))

        for elem in elements:
            if elem["type"] == "text":
                text = elem["content"]
                if text:
                    # Escape HTML chars cho reportlab
                    text = (text.replace("&", "&amp;")
                               .replace("<", "&lt;")
                               .replace(">", "&gt;"))
                    story.append(Paragraph(text, styles["BodyText"]))
                else:
                    story.append(Spacer(1, 0.2 * cm))
            elif elem["type"] == "image":
                url = elem["url"]
                img_bytes = image_cache.get(url)
                if img_bytes:
                    rl_img = _make_rl_image(img_bytes, max_width=14 * cm)
                    if rl_img:
                        story.append(Spacer(1, 0.3 * cm))
                        story.append(rl_img)
                        story.append(Spacer(1, 0.3 * cm))
                else:
                    story.append(Paragraph(f"[Ảnh: {url}]", styles["BodyText"]))

    # Build PDF
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    doc.build(story)
    logger.info(f"Đã xuất PDF: {output_path}")


def _add_pdf_cover(story, novel_info, volume_title, cover_bytes, styles):
    from reportlab.platypus import Spacer, Paragraph, PageBreak
    from reportlab.lib.units import cm

    title = novel_info.get("title", "Unknown")
    author = novel_info.get("author", "")

    if cover_bytes:
        img = _make_rl_image(cover_bytes, max_width=12 * cm, max_height=16 * cm)
        if img:
            story.append(Spacer(1, 1 * cm))
            story.append(img)
            story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(title, styles["Title"]))
    if volume_title:
        story.append(Paragraph(volume_title, styles["SubTitle"]))
    if author:
        story.append(Paragraph(f"Tác giả: {author}", styles["SubTitle"]))
    story.append(PageBreak())


def _build_styles(font_name: str, font_bold: str) -> dict:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    return {
        "Title": ParagraphStyle(
            "Title",
            fontName=font_bold,
            fontSize=20,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=0.5 * cm,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "SubTitle": ParagraphStyle(
            "SubTitle",
            fontName=font_name,
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=0.3 * cm,
        ),
        "ChapterTitle": ParagraphStyle(
            "ChapterTitle",
            fontName=font_bold,
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=0.4 * cm,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "BodyText": ParagraphStyle(
            "BodyText",
            fontName=font_name,
            fontSize=11,
            leading=17,
            alignment=TA_JUSTIFY,
            firstLineIndent=0.5 * cm,
            spaceAfter=0.15 * cm,
        ),
    }


def _make_rl_image(img_bytes: bytes, max_width: float, max_height: float = None):
    """Tạo reportlab Image từ bytes, scale theo max_width."""
    try:
        from reportlab.platypus import Image as RLImage
        from reportlab.lib.units import cm

        pil_img = Image.open(io.BytesIO(img_bytes))
        # Convert non-RGB formats
        if pil_img.mode not in ("RGB", "L"):
            pil_img = pil_img.convert("RGB")
        if pil_img.format == "WEBP" or pil_img.format is None:
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=90)
            img_bytes = buf.getvalue()

        w, h = pil_img.size
        ratio = h / w if w > 0 else 1
        display_w = min(max_width, w)
        display_h = display_w * ratio
        if max_height and display_h > max_height:
            display_h = max_height
            display_w = display_h / ratio

        return RLImage(io.BytesIO(img_bytes), width=display_w, height=display_h)
    except Exception as e:
        logger.warning(f"Không tạo được ảnh PDF: {e}")
        return None
