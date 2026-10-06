"""Cài đặt người dùng + thư mục dữ liệu (session, font, config)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from lnget.models import FORMATS


def data_dir() -> Path:
    """Thư mục lưu config, session đăng nhập, font.

    Ưu tiên biến môi trường LNGET_HOME; bản exe portable dùng thư mục `data/` cạnh file exe.
    """
    env = os.environ.get("LNGET_HOME")
    if env:
        d = Path(env)
    elif getattr(sys, "frozen", False):
        d = Path(sys.executable).parent / "data"
    elif os.name == "nt":
        d = Path(os.environ.get("APPDATA", Path.home())) / "lnget"
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "lnget"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_output() -> str:
    return str(Path.home() / "Downloads" / "lnget")


@dataclass
class Settings:
    output: str = field(default_factory=default_output)
    formats: list[str] = field(default_factory=lambda: ["epub"])
    delay: float = 1.0           # giây tối thiểu giữa 2 request tới trang của site (ảnh CDN ngoài nhanh hơn)
    chapter_workers: int = 3
    image_workers: int = 4
    split_by_status: bool = False  # chia "Đã hoàn thành" / "Chưa hoàn thành"
    keep_image_cache: bool = True  # giữ ảnh đã tải để build lại không phải tải lại
    domains: dict[str, str] = field(default_factory=dict)  # source id -> domain thay thế

    def validate(self) -> "Settings":
        self.formats = [f for f in dict.fromkeys(self.formats) if f in FORMATS] or ["epub"]
        self.delay = max(0.0, min(float(self.delay), 30.0))
        self.chapter_workers = max(1, min(int(self.chapter_workers), 8))
        self.image_workers = max(1, min(int(self.image_workers), 16))
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def config_path() -> Path:
    return data_dir() / "config.json"


def load_settings() -> Settings:
    p = config_path()
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            known = {f.name for f in fields(Settings)}
            return Settings(**{k: v for k, v in raw.items() if k in known}).validate()
        except (ValueError, TypeError):
            pass
    return Settings()


def save_settings(s: Settings) -> None:
    s.validate()
    config_path().write_text(json.dumps(s.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def update_settings(**changes) -> Settings:
    s = load_settings()
    for k, v in changes.items():
        if v is not None and hasattr(s, k):
            setattr(s, k, v)
    save_settings(s)
    return s
