"""HTTP client cho từng source: giả lập Chrome (curl_cffi), throttle, retry, cookie đăng nhập.

Mỗi thread có 1 curl session riêng (curl_cffi Session không thread-safe), nhưng mọi thread
dùng chung cookie đăng nhập và chung 1 bộ throttle → tôn trọng giới hạn của site.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from curl_cffi import requests as cr

log = logging.getLogger(__name__)

IMAGE_ACCEPT = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"


class LngetError(Exception):
    """Lỗi có thông điệp thân thiện để hiển thị cho người dùng."""


class LoginRequired(LngetError):
    pass


class NotFound(LngetError):
    pass


class HttpError(LngetError):
    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status}: {url}")
        self.status = status


class Cancelled(LngetError):
    pass


class Throttle:
    """Giãn cách request tới 1 site + tạm dừng toàn bộ khi gặp 429."""

    def __init__(self, delay: float):
        self.delay = delay
        self._lock = threading.Lock()
        self._next_at = 0.0
        self._pause_until = 0.0

    def wait(self, cancel: threading.Event | None = None) -> None:
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_at, self._pause_until)
            self._next_at = start + self.delay
        remaining = start - time.monotonic()
        if remaining > 0:
            if cancel is not None:
                if cancel.wait(remaining):
                    raise Cancelled("Đã huỷ")
            else:
                time.sleep(remaining)

    def backoff(self, seconds: float) -> None:
        with self._lock:
            self._pause_until = max(self._pause_until, time.monotonic() + seconds)


class HttpClient:
    def __init__(self, source_id: str, delay: float, cookie_file: Path, site_host: str = ""):
        self.source_id = source_id
        self.site_host = site_host
        self.throttle = Throttle(delay)          # trang của site: đi chậm, tôn trọng giới hạn
        self._host_throttles: dict[str, Throttle] = {}
        self.cookie_file = cookie_file
        self._tls = threading.local()
        self._cookies: list[dict] = self._read_cookie_file()
        self._version = 0
        self._lock = threading.Lock()

    # ── Cookie / session ──────────────────────────────────────────────────────

    def _read_cookie_file(self) -> list[dict]:
        if self.cookie_file.exists():
            try:
                return json.loads(self.cookie_file.read_text(encoding="utf-8"))
            except ValueError:
                log.warning("File session hỏng, bỏ qua: %s", self.cookie_file)
        return []

    def session(self) -> cr.Session:
        tls = self._tls
        if getattr(tls, "version", None) != self._version or not hasattr(tls, "s"):
            s = cr.Session(impersonate="chrome")
            s.headers.update({"Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"})
            for c in self._cookies:
                s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
            tls.s, tls.version = s, self._version
        return tls.s

    def set_cookies(self, cookies: list[dict], persist: bool = True) -> None:
        with self._lock:
            self._cookies = [
                {k: c.get(k, "") for k in ("name", "value", "domain", "path")} for c in cookies
            ]
            self._version += 1
            if persist:
                self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
                self.cookie_file.write_text(json.dumps(self._cookies, indent=2), encoding="utf-8")

    def capture_cookies(self) -> None:
        """Lưu cookie hiện có trong session của thread này (sau khi đăng nhập)."""
        jar = self.session().cookies.jar
        self.set_cookies([
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in jar
        ])

    def clear_cookies(self) -> None:
        with self._lock:
            self._cookies = []
            self._version += 1
            if self.cookie_file.exists():
                self.cookie_file.unlink()

    @property
    def has_cookies(self) -> bool:
        return bool(self._cookies)

    # ── Request ───────────────────────────────────────────────────────────────

    def throttle_for(self, url: str) -> Throttle:
        host = urlparse(url).netloc.lower()
        if not self.site_host or host == self.site_host or host.endswith("." + self.site_host):
            return self.throttle
        with self._lock:
            t = self._host_throttles.get(host)
            if t is None:
                t = self._host_throttles[host] = Throttle(min(self.throttle.delay, 0.25))
            return t

    def request(self, method: str, url: str, *, referer: str | None = None,
                accept: str | None = None, data: dict | None = None, timeout: float = 30,
                retries: int = 3, cancel: threading.Event | None = None) -> cr.Response:
        headers = {}
        if referer:
            headers["Referer"] = referer
        if accept:
            headers["Accept"] = accept
        last: Exception | None = None
        throttle = self.throttle_for(url)
        attempt = 0
        while attempt < retries:
            attempt += 1
            if cancel is not None and cancel.is_set():
                raise Cancelled("Đã huỷ")
            throttle.wait(cancel)
            try:
                r = self.session().request(method, url, headers=headers, data=data,
                                           timeout=timeout, allow_redirects=True)
            except Exception as e:  # lỗi mạng / timeout
                last = e
                log.debug("Lỗi mạng %s (%d/%d): %s", url, attempt, retries, e)
                self._sleep(2 ** attempt, cancel)
                continue
            if r.status_code == 429:
                wait = _retry_after(r.headers.get("Retry-After"), default=30)
                log.warning("Site giới hạn tốc độ (429) — tạm dừng %ds", wait)
                throttle.backoff(wait)
                retries += 1 if attempt < 6 else 0  # 429 không tính là lỗi thật, tối đa ~6 lần
                last = HttpError(429, url)
                continue
            if r.status_code == 404:
                raise NotFound(f"Không tìm thấy (404): {url}")
            if r.status_code >= 500:
                last = HttpError(r.status_code, url)
                self._sleep(2 ** attempt, cancel)
                continue
            return r
        if isinstance(last, LngetError):
            raise last
        raise LngetError(f"Không kết nối được {url}: {last}")

    def get(self, url: str, **kw) -> cr.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, data: dict, **kw) -> cr.Response:
        return self.request("POST", url, data=data, retries=1, **kw)

    def get_image(self, url: str, referer: str | None,
                  cancel: threading.Event | None = None) -> bytes:
        r = self.get(url, referer=referer, accept=IMAGE_ACCEPT, retries=2, timeout=40, cancel=cancel)
        if r.status_code in (401, 403):
            raise HttpError(r.status_code, url)
        if r.status_code >= 400:
            raise HttpError(r.status_code, url)
        ctype = r.headers.get("content-type", "")
        if "image" not in ctype and "octet" not in ctype:
            raise LngetError(f"Không phải ảnh ({ctype or 'không rõ'}): {url}")
        return r.content

    @staticmethod
    def _sleep(seconds: float, cancel: threading.Event | None) -> None:
        if cancel is not None:
            if cancel.wait(seconds):
                raise Cancelled("Đã huỷ")
        else:
            time.sleep(seconds)


def _retry_after(value: str | None, default: int) -> int:
    try:
        return max(5, min(int(value or default), 300))
    except ValueError:
        return default
