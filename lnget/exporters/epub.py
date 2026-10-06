from __future__ import annotations

import hashlib
from html import escape
from pathlib import Path

from ebooklib import epub

from lnget.exporters import GetImage, book_title, normalize_image
from lnget.models import Chapter, Novel, Volume

CSS = """
body { font-family: serif; line-height: 1.7; margin: 0 4%; }
h1, h2 { text-align: center; line-height: 1.3; margin: 1.5em 0 1em; }
p { text-indent: 1.5em; margin: 0.35em 0; text-align: justify; }
p.missing { text-indent: 0; font-style: italic; opacity: .7; text-align: center; }
div.img { text-align: center; margin: 1em 0; page-break-inside: avoid; }
div.img img { max-width: 100%; max-height: 95vh; }
.cover-page { text-align: center; }
.meta { text-align: center; text-indent: 0; }
"""


def export(path: Path, novel: Novel, volume: Volume, chapters: list[Chapter],
           cover: bytes | None, get_image: GetImage) -> None:
    book = epub.EpubBook()
    book.set_identifier(f"lnget:{novel.source}:{novel.id}:{volume.id}")
    book.set_title(book_title(novel, volume))
    book.set_language("vi")
    if novel.author:
        book.add_author(novel.author)
    if novel.translator:
        book.add_author(novel.translator, role="trl", uid="translator")
    if novel.description:
        book.add_metadata("DC", "description", novel.description)
    book.add_metadata("DC", "source", novel.url)
    for g in novel.genres:
        book.add_metadata("DC", "subject", g)

    style = epub.EpubItem(uid="style", file_name="style/main.css", media_type="text/css", content=CSS)
    book.add_item(style)

    spine: list = []
    if cover:
        norm = normalize_image(cover)
        if norm:
            ext = "png" if norm[1] == "image/png" else "jpg"
            book.set_cover(f"images/cover.{ext}", norm[0], create_page=False)
            page = epub.EpubHtml(title="Bìa", file_name="cover.xhtml", lang="vi")
            page.content = (f'<div class="cover-page"><img src="images/cover.{ext}" alt="Bìa"/></div>')
            page.add_item(style)
            book.add_item(page)
            spine.append(page)
    spine.append("nav")

    added: dict[str, str] = {}  # url -> file_name trong epub
    toc = []
    for i, ch in enumerate(chapters):
        parts = [f"<h2>{escape(ch.title)}</h2>"]
        for el in ch.elements:
            if el.type == "text":
                parts.append(f"<p>{escape(el.text)}</p>")
                continue
            fname = added.get(el.url)
            if fname is None:
                data = get_image(el.url)
                norm = normalize_image(data) if data else None
                if norm:
                    key = hashlib.sha1(el.url.encode()).hexdigest()[:16]
                    fname = f"images/{key}.{'png' if norm[1] == 'image/png' else 'jpg'}"
                    book.add_item(epub.EpubImage(uid=f"img_{key}", file_name=fname,
                                                 media_type=norm[1], content=norm[0]))
                    added[el.url] = fname
            if fname:
                parts.append(f'<div class="img"><img src="{fname}" alt=""/></div>')
            else:
                parts.append('<p class="missing">[Ảnh không tải được]</p>')
        item = epub.EpubHtml(title=ch.title, file_name=f"chap_{i:04d}.xhtml", lang="vi")
        item.content = "\n".join(parts)
        item.add_item(style)
        book.add_item(item)
        spine.append(item)
        toc.append(item)

    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    epub.write_epub(str(tmp), book)
    tmp.replace(path)
