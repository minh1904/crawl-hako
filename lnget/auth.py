"""Đăng nhập: bằng tài khoản/mật khẩu (source tự làm) hoặc mở trình duyệt thật cho người dùng tự đăng nhập."""
from __future__ import annotations

import time
from typing import Callable
from urllib.parse import urlparse

from lnget.http import HttpClient, LngetError
from lnget.sources.base import Source


def login_password(source: Source, http: HttpClient, username: str, password: str) -> str:
    if not source.supports_login:
        raise LngetError(f"{source.name} không cần/không hỗ trợ đăng nhập")
    if not username or not password:
        raise LngetError("Cần nhập tên đăng nhập và mật khẩu")
    return source.login(http, username, password)


def login_browser(source: Source, http: HttpClient, timeout: float = 300,
                  on_status: Callable[[str], None] | None = None) -> str:
    """Mở cửa sổ trình duyệt ở trang đăng nhập; khi người dùng đăng nhập xong thì lưu session.

    Ưu tiên Edge / Chrome có sẵn trên máy, chỉ dùng Chromium của Playwright nếu không có.
    Mật khẩu không đi qua lnget.
    """
    try:
        from playwright.sync_api import Error as PwError
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LngetError("Cần cài Playwright để đăng nhập bằng trình duyệt: pip install playwright")

    say = on_status or (lambda _m: None)
    with sync_playwright() as p:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = p.chromium.launch(headless=False, channel=channel) if channel \
                    else p.chromium.launch(headless=False)
                break
            except PwError:
                continue
        if browser is None:
            raise LngetError("Không mở được trình duyệt. Cài Edge/Chrome, hoặc chạy: playwright install chromium")

        ctx = browser.new_context(locale="vi-VN")
        page = ctx.new_page()
        page.goto(source.login_url)
        say("Đã mở trình duyệt — hãy đăng nhập trong cửa sổ đó (tick 'Ghi nhớ' nếu có).")
        login_path = urlparse(source.login_url).path.rstrip("/")
        deadline = time.monotonic() + timeout
        cookies: list[dict] = []
        try:
            while time.monotonic() < deadline:
                if page.is_closed() or not browser.is_connected():
                    break
                cookies = ctx.cookies()
                left_login = urlparse(page.url).path.rstrip("/") != login_path
                if source.is_login_cookie(cookies) or (left_login and page.url.startswith(source.base_url)):
                    break
                page.wait_for_timeout(800)
            else:
                raise LngetError("Hết thời gian chờ đăng nhập (5 phút)")
            cookies = ctx.cookies()
        except PwError:
            pass  # người dùng đóng cửa sổ: dùng cookie lấy được lần cuối
        finally:
            try:
                browser.close()
            except PwError:
                pass

    site_cookies = [c for c in cookies if source.domain.endswith(c.get("domain", "").lstrip("."))]
    if not site_cookies:
        raise LngetError("Chưa đăng nhập (không nhận được cookie từ trình duyệt)")
    http.set_cookies(site_cookies)
    who = source.whoami(http)
    if not who:
        http.clear_cookies()
        raise LngetError("Chưa đăng nhập thành công — thử lại và đăng nhập trong cửa sổ trình duyệt")
    return who


def logout(http: HttpClient) -> None:
    http.clear_cookies()
