from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def ensure_utf8_stdio() -> None:
    """Tiếng Việt trên cmd/PowerShell cũ hoặc khi output bị pipe (mặc định cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def open_path(path: str | Path) -> None:
    """Mở thư mục / file bằng trình quản lý file của hệ điều hành."""
    path = str(path)
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 — đường dẫn do lnget tạo ra
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
