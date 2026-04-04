"""
fetcher.py — HTTP client với cloudscraper (bypass CDN anti-bot) + httpx + Playwright fallback
"""
import atexit
import json
import logging
import time
from urllib.parse import urlparse

import cloudscraper
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://docln.sbs"


def set_base_url(domain: str) -> None:
    """Đổi domain runtime — dùng khi site chuyển domain mới."""
    global BASE_URL
    if not domain.startswith("http"):
        domain = "https://" + domain
    BASE_URL = domain.rstrip("/")


_BROWSER_HEADERS = {
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_IMG_ACCEPT = "image/webp,image/apng,image/*,*/*;q=0.8"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_scraper: cloudscraper.CloudScraper | None = None
def get_scraper() -> cloudscraper.CloudScraper:
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        _scraper.headers.update(_BROWSER_HEADERS)
    return _scraper


def fetch(url: str, delay: float = 1.5, retries: int = 3) -> BeautifulSoup:
    """Fetch URL và trả về BeautifulSoup. Retry tối đa `retries` lần."""
    scraper = get_scraper()
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            time.sleep(delay)
            resp = scraper.get(url, timeout=20)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            last_error = e
            logger.warning(f"[Attempt {attempt}/{retries}] Lỗi fetch {url}: {e}")
            if attempt < retries:
                time.sleep(delay * 2)
    raise RuntimeError(f"Không thể fetch {url} sau {retries} lần: {last_error}")


def _referer_for(url: str) -> str:
    """Xác định Referer phù hợp theo domain của URL ảnh."""
    domain = urlparse(url).netloc.lower()
    if "postimg" in domain:
        return "https://postimg.cc/"
    if "imgur" in domain:
        return "https://imgur.com/"
    if "hako" in domain:
        return BASE_URL + "/"   # docln.sbs được CDN chấp nhận làm Referer
    return BASE_URL + "/"


def download_image(url: str, delay: float = 1.0, retries: int = 2,
                   page_url: str = "") -> bytes | None:
    """Tải ảnh, trả về bytes hoặc None nếu thất bại.

    Args:
        page_url: URL chapter chứa ảnh — dùng làm Referer (mimics browser chính xác nhất).
                  Nếu để trống, fallback về _referer_for().

    Chiến lược:
      1. cloudscraper — xử lý Cloudflare JS challenge, CDN anti-bot
      2. httpx HTTP/2 — fallback cho CDN còn lại
      3. Playwright — browser thật, có CF cookies (chỉ khi page_url có)
    """
    if not url or not url.startswith("http"):
        return None

    referer = page_url or _referer_for(url)
    scraper = get_scraper()
    last_error = None

    # ── Strategy 1: cloudscraper ──────────────────────────────────────────────
    for attempt in range(1, retries + 1):
        try:
            time.sleep(delay)
            resp = scraper.get(url, timeout=15, headers={"Referer": referer, "Accept": _IMG_ACCEPT})
            if resp.status_code == 403:
                # CDN block (hotlink protection, Cloudflare) — retry cùng Referer vô ích
                logger.warning(f"403 Forbidden (CDN block) — bỏ qua retry: {url}")
                last_error = f"HTTP 403"
                break
            if resp.status_code >= 500:
                # Server error (522, 502, 503...) — không retry, bỏ qua luôn
                logger.warning(f"Server error {resp.status_code}, bỏ qua ảnh: {url}")
                return None
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and "octet" not in content_type:
                logger.warning(f"URL không phải ảnh ({content_type}): {url}")
                return None
            return resp.content
        except Exception as e:
            last_error = e
            logger.warning(f"[cloudscraper {attempt}/{retries}] Lỗi tải ảnh {url}: {e}")
            if attempt < retries:
                time.sleep(delay * 2)

    # ── Strategy 2: httpx HTTP/2 (chỉ cho lỗi mạng, không dùng khi 4xx/5xx) ──
    logger.info(f"Thử httpx fallback: {url}")
    try:
        with httpx.Client(http2=True, timeout=10, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": _UA,
                "Referer": referer,
                "Accept": _IMG_ACCEPT,
            })
            if resp.status_code == 403:
                logger.warning(f"httpx: 403 Forbidden, bỏ qua: {url}")
            elif resp.status_code >= 500:
                logger.warning(f"httpx: server error {resp.status_code}, bỏ qua: {url}")
            else:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "image" in content_type or "octet" in content_type:
                    return resp.content
                logger.warning(f"httpx: không phải ảnh ({content_type}): {url}")
    except Exception as e:
        logger.warning(f"httpx fallback thất bại {url}: {e}")

    # ── Strategy 3: Playwright (browser thật, có CF cookies) ─────────────────
    if page_url:
        logger.info(f"Thử Playwright fallback: {url}")
        data = _playwright_download(url, page_url)
        if data:
            return data

    logger.error(f"Không thể tải ảnh {url}: {last_error}")
    return None


def download_images_batch(
    urls: list[str],
    delay: float = 0.5,
    page_url: str = "",
) -> dict[str, bytes]:
    """Tải nhiều ảnh dùng scraper chính, truyền page_url làm Referer."""
    valid = [u for u in urls if u and u.startswith("http")]
    if not valid:
        return {}

    results: dict[str, bytes] = {}
    for url in valid:
        data = download_image(url, delay=delay, page_url=page_url)
        if data:
            results[url] = data
    return results


# ─── Playwright fallback (lazy init) ─────────────────────────────────────────

_pw_instance = None
_pw_browser  = None
_pw_context  = None
_pw_warmed: set[str] = set()   # page_url đã navigate để lấy CF cookies


def _cleanup_playwright() -> None:
    global _pw_browser, _pw_instance, _pw_context
    try:
        if _pw_browser:
            _pw_browser.close()
        if _pw_instance:
            _pw_instance.stop()
    except Exception:
        pass
    _pw_browser = _pw_instance = _pw_context = None


def _get_pw_context():
    global _pw_instance, _pw_browser, _pw_context
    if _pw_context is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("playwright chưa được cài. Chạy: py -m pip install playwright && playwright install chromium")
        _pw_instance = sync_playwright().start()
        _pw_browser  = _pw_instance.chromium.launch(headless=True)
        _pw_context  = _pw_browser.new_context(
            user_agent=_UA,
            extra_http_headers={"Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8"},
        )
        atexit.register(_cleanup_playwright)
        logger.info("Playwright browser đã khởi động (headless Chromium).")
    return _pw_context


def _playwright_download(url: str, page_url: str) -> bytes | None:
    """Tải ảnh bằng Playwright — dùng JS fetch() trong browser để bypass CF JS challenge.

    ctx.request.get() là HTTP call thuần — không execute JS → CF challenge timeout.
    page.evaluate(fetch()) chạy trong browser engine đầy đủ → CF clearance cookie được dùng.
    """
    try:
        ctx = _get_pw_context()
    except RuntimeError as e:
        logger.warning(str(e))
        return None

    referer = page_url or _referer_for(url)

    # Navigate chapter page 1 lần để browser lấy CF clearance cookie cho image CDN.
    # Mark attempted TRƯỚC try/except để tránh retry storm (navigate lại cho mỗi ảnh).
    if page_url and page_url not in _pw_warmed:
        _pw_warmed.add(page_url)
        page = ctx.new_page()
        try:
            page.goto(page_url, timeout=45_000, wait_until="networkidle")
            page.wait_for_timeout(2000)   # buffer cho CF set-cookie
            logger.info(f"Playwright: đã warm-up {page_url}")
        except Exception as e:
            logger.warning(f"Playwright: không navigate được {page_url}: {e}")
        finally:
            page.close()

        # Inject cookies vào cloudscraper để tái sử dụng không cần Playwright
        try:
            scraper = get_scraper()
            for ck in ctx.cookies():
                scraper.cookies.set(ck["name"], ck["value"], domain=ck.get("domain", ""))
            logger.info("Playwright: đã inject cookies vào cloudscraper session.")
        except Exception as e:
            logger.warning(f"Playwright: inject cookies thất bại: {e}")

    # Dùng page.evaluate(fetch()) — chạy trong JS engine với full cookie jar,
    # tự handle CF challenge, không bị timeout như ctx.request.get()
    dl_page = ctx.new_page()
    try:
        img_data = dl_page.evaluate(f"""async () => {{
            try {{
                const resp = await fetch({json.dumps(url)}, {{
                    headers: {{
                        "Referer": {json.dumps(referer)},
                        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
                    }}
                }});
                if (!resp.ok) return null;
                const buf = await resp.arrayBuffer();
                return Array.from(new Uint8Array(buf));
            }} catch(e) {{
                return null;
            }}
        }}""")
        if img_data:
            return bytes(img_data)
        logger.warning(f"Playwright: fetch trả về null cho {url}")
    except Exception as e:
        logger.warning(f"Playwright download thất bại {url}: {e}")
    finally:
        dl_page.close()
    return None


def absolute_url(href: str) -> str:
    """Chuyển relative URL thành absolute."""
    if href.startswith("http"):
        return href
    return BASE_URL + href
