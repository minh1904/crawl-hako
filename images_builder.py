"""
images_builder.py — Export toàn bộ ảnh minh họa của một tập ra folder riêng.

Cấu trúc output:
  {novel_dir}/IMAGES/[Vol X] Novel Title/
      000_cover.jpg          ← ảnh bìa tập (nếu có)
      001.jpg, 002.png ...   ← ảnh theo thứ tự xuất hiện trong tập
      manifest.txt           ← danh sách: 001.jpg — Tên chương
"""
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

_FMT_TO_EXT: dict[str, str] = {
    "JPEG": "jpg",
    "PNG":  "png",
    "WEBP": "webp",
    "GIF":  "gif",
    "BMP":  "bmp",
    "TIFF": "tif",
}


def _detect_ext(img_bytes: bytes) -> str:
    """Phát hiện extension từ bytes ảnh qua PIL."""
    try:
        fmt = Image.open(io.BytesIO(img_bytes)).format or "JPEG"
        return _FMT_TO_EXT.get(fmt, "jpg")
    except Exception:
        return "jpg"


def build_images(
    output_path: Path,
    novel_info: dict,
    volume_title: str,
    chapters_data: list[dict],
    cover_bytes: bytes | None,
    image_cache: dict[str, bytes],
) -> None:
    """Export tất cả ảnh của tập ra output_path (folder).

    Args:
        output_path:   Folder đích (đã được tạo bởi storage.volume_output_path).
        novel_info:    Thông tin truyện (không dùng trực tiếp nhưng giữ signature chung).
        volume_title:  Tên tập.
        chapters_data: Danh sách chương với elements.
        cover_bytes:   Bytes ảnh bìa tập (có thể None).
        image_cache:   {url: bytes} — ảnh đã tải thành công.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    manifest_lines: list[str] = []
    counter = 0

    # ── Ảnh bìa tập ──────────────────────────────────────────────────────────
    if cover_bytes:
        ext = _detect_ext(cover_bytes)
        cover_filename = f"000_cover.{ext}"
        (output_path / cover_filename).write_bytes(cover_bytes)
        manifest_lines.append(f"{cover_filename} — [Bìa tập]")
        logger.info(f"  images: lưu bìa → {cover_filename}")

    # ── Ảnh inline theo thứ tự xuất hiện trong tập ───────────────────────────
    for chap in chapters_data:
        chap_title = chap.get("title", "")
        for elem in chap.get("elements", []):
            if elem.get("type") != "image":
                continue
            url = elem.get("url", "")
            img_bytes = image_cache.get(url)
            if not img_bytes:
                continue   # ảnh chưa tải được — bỏ qua

            counter += 1
            ext = _detect_ext(img_bytes)
            filename = f"{counter:03d}.{ext}"
            (output_path / filename).write_bytes(img_bytes)
            manifest_lines.append(f"{filename} — {chap_title}")

    # ── manifest.txt ─────────────────────────────────────────────────────────
    manifest_path = output_path / "manifest.txt"
    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")

    logger.info(f"  images: {counter} ảnh → {output_path}")
