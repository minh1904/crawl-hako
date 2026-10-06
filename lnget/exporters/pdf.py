"""PDF tiếng Việt bằng reportlab + font Noto Serif (tự tải lần đầu vào thư mục dữ liệu)."""
from __future__ import annotations

import io
import logging
import threading
import urllib.request
from html import escape
from pathlib import Path

from lnget.config import data_dir
from lnget.exporters import GetImage, normalize_image
from lnget.models import Chapter, Novel, Volume

log = logging.getLogger(__name__)

_FONT_SETS = [
    ("NotoSerif", "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/NotoSerif/unhinted/ttf/NotoSerif-{w}.ttf",
     {"Regular": "Regular", "Bold": "Bold"}),
    ("DejaVuSans", "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37/ttf/DejaVuSans{w}.ttf",
     {"Regular": "", "Bold": "-Bold"}),
]
_font_lock = threading.Lock()
_fonts: tuple[str, str] | None = None


def _ensure_fonts() -> tuple[str, str]:
    """Trả về (font thường, font đậm) đã đăng ký với reportlab."""
    global _fonts
    with _font_lock:
        if _fonts:
            return _fonts
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_dir = data_dir() / "fonts"
        font_dir.mkdir(exist_ok=True)
        for family, url_tpl, weights in _FONT_SETS:
            try:
                names = []
                for weight, suffix in weights.items():
                    f = font_dir / f"{family}-{weight}.ttf"
                    if not f.exists() or f.stat().st_size < 10_000:
                        log.info("Đang tải font %s-%s ...", family, weight)
                        with urllib.request.urlopen(url_tpl.format(w=suffix), timeout=60) as r:
                            f.write_bytes(r.read())
                    name = f"{family}-{weight}"
                    pdfmetrics.registerFont(TTFont(name, str(f)))
                    names.append(name)
                _fonts = (names[0], names[1])
                return _fonts
            except Exception as e:
                log.warning("Không dùng được font %s: %s", family, e)
        log.error("Không có font tiếng Việt — PDF sẽ lỗi dấu")
        _fonts = ("Helvetica", "Helvetica-Bold")
        return _fonts


def export(path: Path, novel: Novel, volume: Volume, chapters: list[Chapter],
           cover: bytes | None, get_image: GetImage) -> None:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

    regular, bold = _ensure_fonts()
    st = {
        "title": ParagraphStyle("t", fontName=bold, fontSize=18, leading=24, alignment=TA_CENTER, spaceAfter=10),
        "sub": ParagraphStyle("s", fontName=regular, fontSize=12, leading=16, alignment=TA_CENTER, spaceAfter=6),
        "chap": ParagraphStyle("c", fontName=bold, fontSize=14, leading=19, alignment=TA_CENTER, spaceAfter=12),
        "body": ParagraphStyle("b", fontName=regular, fontSize=10.5, leading=16, alignment=TA_JUSTIFY,
                               firstLineIndent=0.5 * cm, spaceAfter=3),
        "missing": ParagraphStyle("m", fontName=regular, fontSize=9, alignment=TA_CENTER, textColor="#888888"),
    }
    page_w, page_h = A5
    margin = 1.6 * cm
    max_w, max_h = page_w - 2 * margin, page_h - 2 * margin - 1 * cm

    def image(data: bytes, mw: float = max_w, mh: float = max_h):
        norm = normalize_image(data, allow_png=True)
        if not norm:
            return None
        w, h = norm[2]
        scale = min(mw / w, mh / h)  # minh hoạ LN: luôn vừa khổ trang
        return Image(io.BytesIO(norm[0]), width=w * scale, height=h * scale)

    story = []
    if cover and (img := image(cover, max_w, max_h * 0.75)):
        story += [img, Spacer(1, 12)]
    story.append(Paragraph(escape(novel.title), st["title"]))
    for line in (volume.title, novel.author and f"Tác giả: {novel.author}",
                 novel.translator and f"Nhóm dịch: {novel.translator}"):
        if line:
            story.append(Paragraph(escape(line), st["sub"]))

    for ch in chapters:
        story += [PageBreak(), Paragraph(escape(ch.title), st["chap"])]
        for el in ch.elements:
            if el.type == "text":
                story.append(Paragraph(escape(el.text), st["body"]))
                continue
            data = get_image(el.url)
            img = image(data) if data else None
            story += [Spacer(1, 6), img, Spacer(1, 6)] if img else [Paragraph("[Ảnh không tải được]", st["missing"])]

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    doc = SimpleDocTemplate(str(tmp), pagesize=A5, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin,
                            title=f"{novel.title} — {volume.title}", author=novel.author or novel.translator)
    doc.build(story)
    tmp.replace(path)
