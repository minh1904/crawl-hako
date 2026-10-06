"""Xuất 1 tập truyện ra các định dạng. Mọi exporter cùng chữ ký:

    export(path, novel, volume, chapters, cover, get_image)

`get_image(url) -> bytes | None` đọc ảnh đã tải (từ cache trên đĩa).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Callable, Protocol

from PIL import Image

from lnget.models import Chapter, Novel, Volume

GetImage = Callable[[str], "bytes | None"]


class Exporter(Protocol):
    def __call__(self, path: Path, novel: Novel, volume: Volume, chapters: list[Chapter],
                 cover: bytes | None, get_image: GetImage) -> None: ...


def get_exporter(fmt: str) -> Exporter:
    if fmt == "epub":
        from lnget.exporters.epub import export
    elif fmt == "docx":
        from lnget.exporters.docx import export
    elif fmt == "pdf":
        from lnget.exporters.pdf import export
    elif fmt == "images":
        from lnget.exporters.images import export
    else:
        raise ValueError(f"Định dạng không hỗ trợ: {fmt}")
    return export


def normalize_image(data: bytes, allow_png: bool = True,
                    reencode: bool = False) -> tuple[bytes, str, tuple[int, int]] | None:
    """Chuyển ảnh về JPEG (hoặc PNG nếu có nền trong suốt) để mọi trình đọc mở được.

    Trả về (bytes, mime, (w, h)) hoặc None nếu ảnh hỏng.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    fmt = img.format or ""
    if fmt == "JPEG" and img.mode in ("RGB", "L") and not reencode:
        return data, "image/jpeg", img.size
    if fmt == "PNG" and allow_png and not reencode:
        return data, "image/png", img.size
    buf = io.BytesIO()
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if allow_png and has_alpha:
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png", img.size
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue(), "image/jpeg", img.size


def book_title(novel: Novel, volume: Volume) -> str:
    return f"{novel.title} — {volume.title}" if volume.title else novel.title
