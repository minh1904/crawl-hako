"""
epub_builder.py — Tạo file EPUB từ danh sách chapter
"""
import io
import logging
import mimetypes
import uuid
from pathlib import Path

from ebooklib import epub
from PIL import Image

logger = logging.getLogger(__name__)


def _image_bytes_to_epub_item(img_bytes: bytes, img_id: str) -> epub.EpubImage | None:
    """Chuyển bytes ảnh thành EpubImage item, tự detect mime type."""
    if not img_bytes:
        return None
    try:
        pil_img = Image.open(io.BytesIO(img_bytes))
        fmt = pil_img.format or "JPEG"
        mime_map = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif",
                    "WEBP": "image/webp", "BMP": "image/bmp"}
        mime = mime_map.get(fmt, "image/jpeg")
        ext = fmt.lower().replace("jpeg", "jpg")
        # Convert WEBP → JPEG để tương thích rộng hơn
        if fmt == "WEBP":
            buf = io.BytesIO()
            pil_img.convert("RGB").save(buf, format="JPEG", quality=90)
            img_bytes = buf.getvalue()
            mime = "image/jpeg"
            ext = "jpg"
        item = epub.EpubImage()
        item.uid = img_id
        item.file_name = f"images/{img_id}.{ext}"
        item.media_type = mime
        item.content = img_bytes
        return item
    except Exception as e:
        logger.warning(f"Không xử lý được ảnh {img_id}: {e}")
        return None


def build_epub(
    output_path: Path,
    novel_info: dict,
    volume_title: str,
    chapters_data: list[dict],
    cover_bytes: bytes | None,
    image_cache: dict[str, bytes],
) -> None:
    """
    Tạo file EPUB.

    chapters_data: list of {title, elements: [{type, content|url}]}
    image_cache: {url: bytes} — ảnh đã tải sẵn
    """
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(f"{novel_info.get('title', 'Unknown')} — {volume_title}" if volume_title else novel_info.get("title", "Unknown"))
    book.set_language("vi")

    author = novel_info.get("author", "")
    if author:
        book.add_author(author)

    # Ảnh bìa — dùng set_cover() trực tiếp (ebooklib tự thêm item, không add thêm để tránh duplicate)
    if cover_bytes:
        book.set_cover("images/cover.jpg", cover_bytes)

    # CSS
    style = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=_default_css(),
    )
    book.add_item(style)

    spine = ["nav"]
    toc = []
    image_items_added = set()

    for chap_idx, chap in enumerate(chapters_data):
        chap_title = chap.get("title", f"Chương {chap_idx + 1}")
        elements = chap.get("elements", [])

        html_parts = [f"<h2>{chap_title}</h2>"]
        inline_images = []

        for elem in elements:
            if elem["type"] == "text":
                text = elem["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if text:
                    html_parts.append(f"<p>{text}</p>")
                else:
                    html_parts.append("<br/>")
            elif elem["type"] == "image":
                url = elem["url"]
                img_bytes = image_cache.get(url)
                if img_bytes:
                    img_id = f"img_{abs(hash(url))}"
                    if img_id not in image_items_added:
                        img_item = _image_bytes_to_epub_item(img_bytes, img_id)
                        if img_item:
                            book.add_item(img_item)
                            image_items_added.add(img_id)
                            inline_images.append((img_id, img_item.file_name))
                    # Tìm lại file_name từ các item đã thêm
                    fn = f"images/{img_id}.jpg"  # default, sẽ được ghi đè bên dưới
                    for iid, ifn in inline_images:
                        if iid == img_id:
                            fn = ifn
                            break
                    html_parts.append(f'<img src="{fn}" alt=""/>')
                else:
                    html_parts.append(f'<p><em>[Ảnh: {url}]</em></p>')

        # Không dùng XML declaration hay DOCTYPE external — gây lỗi lxml "Document is empty"
        # ebooklib sẽ tự thêm headers đúng khi write
        html_content = (
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<head><title>' + chap_title + '</title>'
            '<link rel="stylesheet" type="text/css" href="../style/main.css"/>'
            '</head><body>' + "\n".join(html_parts) + "</body></html>"
        )

        chap_epub = epub.EpubHtml(
            title=chap_title,
            file_name=f"chapter_{chap_idx:04d}.xhtml",
            lang="vi",
        )
        chap_epub.content = html_content
        chap_epub.add_item(style)
        book.add_item(chap_epub)
        spine.append(chap_epub)
        toc.append(epub.Link(chap_epub.file_name, chap_title, f"chap{chap_idx}"))

    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), book)
    logger.info(f"Đã xuất EPUB: {output_path}")


def _default_css() -> str:
    return """
body {
    font-family: "Times New Roman", Times, serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em 2em;
    color: #1a1a1a;
}
h1, h2, h3 {
    text-align: center;
    font-weight: bold;
    margin: 1.5em 0 0.5em 0;
}
p {
    text-indent: 1.5em;
    margin: 0.4em 0;
}
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}
"""
