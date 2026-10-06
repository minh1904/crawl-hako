from __future__ import annotations

import shutil
from pathlib import Path

from lnget.exporters import GetImage
from lnget.library import image_ext
from lnget.models import Chapter, Novel, Volume


def export(path: Path, novel: Novel, volume: Volume, chapters: list[Chapter],
           cover: bytes | None, get_image: GetImage) -> None:
    """Xuất mọi ảnh của tập theo thứ tự xuất hiện + manifest.txt."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    manifest = []
    if cover:
        name = f"000_cover.{image_ext(cover)}"
        (path / name).write_bytes(cover)
        manifest.append(f"{name}\t[Bìa tập]")
    n = 0
    seen: set[str] = set()
    for ch in chapters:
        for url in ch.image_urls:
            if url in seen:
                continue
            seen.add(url)
            data = get_image(url)
            if not data:
                manifest.append(f"(thiếu)\t{ch.title}\t{url}")
                continue
            n += 1
            name = f"{n:03d}.{image_ext(data)}"
            (path / name).write_bytes(data)
            manifest.append(f"{name}\t{ch.title}")
    (path / "manifest.txt").write_text("\n".join(manifest), encoding="utf-8")
