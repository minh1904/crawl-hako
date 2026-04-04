"""
fetcher.py — HTTP client với cloudscraper (bypass CDN anti-bot) + httpx fallback
"""
import time
import logging
from urllib.parse import urlparse

import cloudscraper
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://docln.sbs"

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
        return "https://ln.hako.vip/"
    if "i2.hako" in domain or "cdn.hako" in domain:
        return "https://ln.hako.vip/"
    return BASE_URL + "/"


def download_image(url: str, delay: float = 1.0, retries: int = 4) -> bytes | None:
    """Tải ảnh, trả về bytes hoặc None nếu thất bại.

    Chiến lược:
      1. cloudscraper — xử lý Cloudflare JS challenge, CDN anti-bot
      2. httpx HTTP/2 — fallback cho CDN còn lại
    """
    if not url or not url.startswith("http"):
        return None

    referer = _referer_for(url)
    scraper = get_scraper()
    last_error = None

    # ── Strategy 1: cloudscraper ──────────────────────────────────────────────
    for attempt in range(1, retries + 1):
        try:
            time.sleep(delay)
            resp = scraper.get(url, timeout=30, headers={"Referer": referer, "Accept": _IMG_ACCEPT})
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

    # ── Strategy 2: httpx HTTP/2 ──────────────────────────────────────────────
    logger.info(f"Thử httpx fallback: {url}")
    try:
        with httpx.Client(http2=True, timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": _UA,
                "Referer": referer,
                "Accept": _IMG_ACCEPT,
            })
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type or "octet" in content_type:
                return resp.content
            logger.warning(f"httpx: không phải ảnh ({content_type}): {url}")
    except Exception as e:
        logger.warning(f"httpx fallback thất bại {url}: {e}")

    logger.error(f"Không thể tải ảnh {url}: {last_error}")
    return None


def absolute_url(href: str) -> str:
    """Chuyển relative URL thành absolute."""
    if href.startswith("http"):
        return href
    return BASE_URL + href
