"""Interface chung cho mọi site. Thêm site mới = 1 file kế thừa `Source`."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from lnget.http import HttpClient, LngetError
from lnget.models import Chapter, ChapterRef, Novel


class Source(ABC):
    id: str = ""                # khoá ngắn: "hako"
    name: str = ""              # tên hiển thị
    domains: tuple[str, ...] = ()  # domain đã biết (domain đầu tiên là mặc định)
    supports_login: bool = False
    supports_listing: bool = False
    login_path: str = "/login"

    def __init__(self, domain: str | None = None):
        self.domain = (domain or self.domains[0]).removeprefix("https://").removeprefix("http://").strip("/")

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}"

    @property
    def login_url(self) -> str:
        return self.base_url + self.login_path

    def matches(self, url: str) -> bool:
        host = urlparse(url if "//" in url else "https://" + url).netloc.lower().removeprefix("www.")
        return host == self.domain or host in self.domains

    def normalize_url(self, url: str) -> str:
        """Đổi mọi domain cũ/mirror về domain đang dùng."""
        p = urlparse(url if "//" in url else "https://" + url)
        return f"{self.base_url}{p.path}" + (f"?{p.query}" if p.query else "")

    def abs(self, href: str) -> str:
        return urljoin(self.base_url + "/", href)

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    # ── Bắt buộc ──────────────────────────────────────────────────────────────

    @abstractmethod
    def fetch_novel(self, http: HttpClient, url: str) -> Novel: ...

    @abstractmethod
    def fetch_chapter(self, http: HttpClient, ref: ChapterRef,
                      cancel: threading.Event | None = None) -> Chapter: ...

    # ── Tuỳ chọn ──────────────────────────────────────────────────────────────

    def image_referer(self, image_url: str, page_url: str) -> str | None:
        return page_url

    def is_own_image(self, image_url: str) -> bool:
        """Ảnh do chính site lưu trữ (lỗi 401/403 có thể do chưa đăng nhập)."""
        return urlparse(image_url).netloc.lower().endswith(self.domain)

    def login(self, http: HttpClient, username: str, password: str) -> str:
        raise LngetError(f"{self.name} không hỗ trợ đăng nhập")

    def whoami(self, http: HttpClient) -> str | None:
        """Tên tài khoản đang đăng nhập, None nếu chưa đăng nhập."""
        return None

    def is_login_cookie(self, cookies: list[dict]) -> bool:
        """Dùng cho đăng nhập bằng trình duyệt: cookie nào cho biết đã đăng nhập xong."""
        return False

    def list_novels(self, http: HttpClient, page: int, list_url: str | None = None) -> list[str]:
        raise LngetError(f"{self.name} không hỗ trợ quét danh sách")
