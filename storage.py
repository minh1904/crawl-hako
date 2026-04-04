"""
storage.py — Đọc/ghi index.json, crawl_log.txt, info.json, cover.jpg
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_dirname(name: str) -> str:
    """Chuyển tên truyện thành tên thư mục hợp lệ trên Windows."""
    # Các ký tự không hợp lệ trên Windows
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip(". ")


def get_novel_dir(output_root: str, novel_title: str) -> Path:
    """Trả về Path thư mục output cho truyện, tạo nếu chưa có."""
    folder = _safe_dirname(novel_title) if novel_title else "unknown"
    path = Path(output_root) / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_index(novel_dir: Path) -> dict:
    """Load index.json → {chapter_url: "done" | "error"}"""
    index_file = novel_dir / "index.json"
    if index_file.exists():
        try:
            return json.loads(index_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Không đọc được index.json: {e}")
    return {}


def save_index(novel_dir: Path, index: dict) -> None:
    """Ghi index.json."""
    index_file = novel_dir / "index.json"
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def log(novel_dir: Path, message: str) -> None:
    """Append 1 dòng vào crawl_log.txt, kèm timestamp."""
    log_file = novel_dir / "crawl_log.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)
    logger.info(message)


def save_info(novel_dir: Path, info: dict) -> None:
    """Ghi info.json."""
    info_file = novel_dir / "info.json"
    info_file.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def save_cover(novel_dir: Path, image_bytes: bytes) -> Path:
    """Lưu ảnh bìa cover.jpg, trả về path."""
    cover_path = novel_dir / "cover.jpg"
    cover_path.write_bytes(image_bytes)
    return cover_path


def _fmt_dir(novel_dir: Path, fmt: str) -> Path:
    """Trả về (và tạo) subfolder theo format: EPUB/, DOCX/, PDF/."""
    d = novel_dir / fmt.upper()
    d.mkdir(exist_ok=True)
    return d


def volume_file_exists(novel_dir: Path, volume_title: str, novel_title: str, fmt: str) -> bool:
    """Kiểm tra file (hoặc folder ảnh) output của tập đã tồn tại chưa."""
    if fmt == "images":
        d = _volume_images_dir_path(novel_dir, volume_title, novel_title)
        return d.is_dir() and any(d.iterdir())
    filename = _volume_filename(volume_title, novel_title, fmt)
    return (_fmt_dir(novel_dir, fmt) / filename).exists()


def volume_output_path(novel_dir: Path, volume_title: str, novel_title: str, fmt: str) -> Path:
    """Trả về Path cho file output (hoặc folder ảnh) của tập."""
    if fmt == "images":
        d = _volume_images_dir_path(novel_dir, volume_title, novel_title)
        d.mkdir(parents=True, exist_ok=True)
        return d
    filename = _volume_filename(volume_title, novel_title, fmt)
    return _fmt_dir(novel_dir, fmt) / filename


def _volume_images_dir_path(novel_dir: Path, volume_title: str, novel_title: str) -> Path:
    """Trả về Path folder ảnh của tập: {novel_dir}/IMAGES/[Vol X] Novel Title/"""
    safe_title = _safe_dirname(novel_title)
    if volume_title:
        safe_vol = _safe_dirname(volume_title)
        folder = f"[{safe_vol}] {safe_title}"
    else:
        folder = safe_title
    return novel_dir / "IMAGES" / folder


def _volume_filename(volume_title: str, novel_title: str, fmt: str) -> str:
    """Tạo tên file: '[Tập 1] Tên Truyện.epub'"""
    safe_title = _safe_dirname(novel_title)
    if volume_title:
        safe_vol = _safe_dirname(volume_title)
        name = f"[{safe_vol}] {safe_title}.{fmt}"
    else:
        name = f"{safe_title}.{fmt}"
    return name
