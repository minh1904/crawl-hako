"""Thư viện truyện trên đĩa.

    <output>/[Truyện dịch] Tên truyện/
        novel.json                 thông tin truyện + danh sách tập/chương
        cover.jpg
        EPUB/ DOCX/ PDF/ IMAGES/   file xuất theo tập
        lnget.log
        .cache/chapters/<id>.json  nội dung chương (resume, build lại không cần mạng)
        .cache/images/<hash>.<ext> ảnh đã tải
        .cache/state.json          chương / ảnh lỗi lần trước

Cache khoá theo ID chương của site nên chọn tập khác nhau giữa các lần chạy không bị lệch.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from lnget.models import Chapter, Novel, Volume

_KIND_TAG = {"translation": "[Truyện dịch]", "machine": "[AI dịch]", "original": "[Sáng tác]"}
_STATUS_DIRS = ("Đã hoàn thành", "Chưa hoàn thành")
_REPLACE = {":": " -", "/": "-", "\\": "-", "|": "-", '"': "", "?": "", "*": "", "<": "", ">": ""}
_IMG_EXT = {b"\xff\xd8": "jpg", b"\x89P": "png", b"GI": "gif", b"RI": "webp", b"BM": "bmp"}


def safe_name(name: str, limit: int = 120) -> str:
    name = "".join(_REPLACE.get(c, c) for c in name if ord(c) >= 32)
    name = " ".join(name.split()).strip(" .")
    return name[:limit].rstrip(" .") or "untitled"


def _write_atomic(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_bytes(data)
    os.replace(tmp, path)


def image_ext(data: bytes) -> str:
    return _IMG_EXT.get(data[:2], "jpg")


class NovelDir:
    def __init__(self, path: Path, novel: Novel):
        self.path = path
        self.novel = novel
        self._lock = threading.Lock()

    # ── Metadata ──────────────────────────────────────────────────────────────

    @property
    def cache(self) -> Path:
        return self.path / ".cache"

    def save_novel(self, novel: Novel | None = None) -> None:
        if novel is not None:
            self.novel = novel
        _write_atomic(self.path / "novel.json",
                      json.dumps(self.novel.to_dict(), ensure_ascii=False, indent=2))

    def cover(self) -> bytes | None:
        for p in self.path.glob("cover.*"):
            return p.read_bytes()
        return None

    def save_cover(self, data: bytes) -> None:
        for old in self.path.glob("cover.*"):
            old.unlink()
        _write_atomic(self.path / f"cover.{image_ext(data)}", data)

    def log(self, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, open(self.path / "lnget.log", "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")

    # ── Chương ────────────────────────────────────────────────────────────────

    def _chapter_file(self, chapter_id: str) -> Path:
        return self.cache / "chapters" / f"{safe_name(chapter_id)}.json"

    def has_chapter(self, chapter_id: str) -> bool:
        return self._chapter_file(chapter_id).exists()

    def load_chapter(self, chapter_id: str) -> Chapter | None:
        f = self._chapter_file(chapter_id)
        if not f.exists():
            return None
        try:
            return Chapter.from_dict(json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, KeyError, TypeError):
            return None

    def save_chapter(self, chapter: Chapter) -> None:
        _write_atomic(self._chapter_file(chapter.id), json.dumps(chapter.to_dict(), ensure_ascii=False))

    # ── Ảnh ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _img_key(url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]

    def image_path(self, url: str) -> Path | None:
        for p in (self.cache / "images").glob(self._img_key(url) + ".*"):
            if not p.name.endswith(".tmp"):
                return p
        return None

    def load_image(self, url: str) -> bytes | None:
        p = self.image_path(url)
        return p.read_bytes() if p else None

    def save_image(self, url: str, data: bytes) -> None:
        _write_atomic(self.cache / "images" / f"{self._img_key(url)}.{image_ext(data)}", data)

    def clear_images(self) -> None:
        shutil.rmtree(self.cache / "images", ignore_errors=True)

    # ── Trạng thái lỗi ────────────────────────────────────────────────────────

    def load_state(self) -> dict:
        f = self.cache / "state.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                pass
        return {"chapter_errors": {}, "image_errors": {}}

    def save_state(self, state: dict) -> None:
        with self._lock:
            _write_atomic(self.cache / "state.json", json.dumps(state, ensure_ascii=False, indent=1))

    # ── File xuất ─────────────────────────────────────────────────────────────

    def output_path(self, volume: Volume, fmt: str) -> Path:
        title = safe_name(self.novel.title, 50)
        name = f"{title} - {safe_name(volume.title, 50)}" if volume.title else title
        if fmt == "images":
            return self.path / "IMAGES" / name
        return self.path / fmt.upper() / f"{name}.{fmt}"

    def has_output(self, volume: Volume, fmt: str) -> bool:
        p = self.output_path(volume, fmt)
        return (p.is_dir() and any(p.iterdir())) if fmt == "images" else p.exists()

    def summary(self) -> dict:
        """Thông tin gọn cho màn Thư viện."""
        vols = []
        for v in self.novel.volumes:
            cached = sum(1 for c in v.chapters if self.has_chapter(c.id))
            vols.append({
                "id": v.id, "title": v.title, "chapters": len(v.chapters), "cached": cached,
                "formats": [f for f in ("epub", "docx", "pdf", "images") if self.has_output(v, f)],
            })
        return {
            "path": str(self.path), "source": self.novel.source, "id": self.novel.id,
            "title": self.novel.title, "url": self.novel.url, "status": self.novel.status,
            "completed": self.novel.completed, "kind": self.novel.kind,
            "has_cover": any(self.path.glob("cover.*")), "volumes": vols,
            "updated": (self.path / "novel.json").stat().st_mtime if (self.path / "novel.json").exists() else 0,
        }


class Library:
    def __init__(self, root: str | Path, split_by_status: bool = False):
        self.root = Path(root).expanduser()
        self.split = split_by_status

    def _dir_name(self, novel: Novel) -> str:
        return f"{_KIND_TAG.get(novel.kind, '')} {safe_name(novel.title, 80)}".strip()

    def target_path(self, novel: Novel) -> Path:
        base = self.root
        if self.split:
            base = base / _STATUS_DIRS[0 if novel.completed else 1]
        return base / self._dir_name(novel)

    def _candidate_dirs(self):
        for base in (self.root, *(self.root / d for d in _STATUS_DIRS)):
            if base.is_dir():
                for d in base.iterdir():
                    if d.is_dir() and (d / "novel.json").exists():
                        yield d

    def find(self, source: str, novel_id: str) -> Path | None:
        for d in self._candidate_dirs():
            try:
                meta = json.loads((d / "novel.json").read_text(encoding="utf-8"))
            except ValueError:
                continue
            if meta.get("source") == source and str(meta.get("id")) == str(novel_id):
                return d
        return None

    def open(self, novel: Novel) -> NovelDir:
        """Tìm thư mục cũ của truyện (theo source + id); đổi tên/di chuyển nếu tên hoặc tình trạng đổi."""
        target = self.target_path(novel)
        existing = self.find(novel.source, novel.id)
        if existing and existing.resolve() != target.resolve():
            if target.exists():
                target = existing  # tránh ghi đè thư mục trùng tên
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(existing), str(target))
        target.mkdir(parents=True, exist_ok=True)
        nd = NovelDir(target, novel)
        nd.save_novel()
        return nd

    def load(self, path: str | Path) -> NovelDir:
        path = Path(path)
        meta = json.loads((path / "novel.json").read_text(encoding="utf-8"))
        return NovelDir(path, Novel.from_dict(meta))

    def scan(self) -> list[NovelDir]:
        out = []
        for d in self._candidate_dirs():
            try:
                out.append(self.load(d))
            except (ValueError, KeyError, TypeError):
                continue
        return sorted(out, key=lambda nd: nd.novel.title.lower())
