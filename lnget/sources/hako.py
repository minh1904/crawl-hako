"""Hako / Cổng Light Novel (docln.sbs và các domain cũ)."""
from __future__ import annotations

import base64
import json
import re
import threading
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from lnget.http import HttpClient, LngetError, LoginRequired
from lnget.models import Chapter, ChapterRef, Element, Novel, Volume
from lnget.sources._html import extract_elements
from lnget.sources.base import Source

_NOVEL_PATH = re.compile(r"^/(truyen|ai-dich|sang-tac)/(\d+)[^/]*")
_CHAPTER_ID = re.compile(r"/c(\d+)(?:-|$)")
_NOTE_MARK = re.compile(r"\[note\d+\]", re.I)
_BG_URL = re.compile(r"url\(['\"]?([^'\")\s]+)['\"]?\)")
_LOGIN_HINT = re.compile(r"(cần|phải|vui lòng)\s+đăng nhập", re.I)


class HakoSource(Source):
    id = "hako"
    name = "Hako (Cổng Light Novel)"
    domains = ("docln.sbs", "docln.net", "ln.hako.vn", "hako.vn")
    supports_login = True
    supports_listing = True

    # ── Truyện ────────────────────────────────────────────────────────────────

    def novel_url(self, url: str) -> str:
        path = urlparse(self.normalize_url(url)).path
        m = _NOVEL_PATH.match(path)
        if not m:
            raise LngetError("Link không phải trang truyện Hako (dạng /truyen/123-ten-truyen)")
        return self.base_url + m.group(0)

    def fetch_novel(self, http: HttpClient, url: str) -> Novel:
        url = self.novel_url(url)
        r = http.get(url)
        self._raise_if_login_page(r.url, r.text)
        return self.parse_novel(r.text, url)

    def parse_novel(self, html: str, url: str) -> Novel:
        soup = self.soup(html)
        path_m = _NOVEL_PATH.match(urlparse(url).path)
        prefix, novel_id = (path_m.group(1), path_m.group(2)) if path_m else ("truyen", "")

        title_el = soup.select_one(".series-name a") or soup.select_one(".series-name")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title and soup.title:
            title = soup.title.get_text(strip=True).split(" - ")[0].strip()

        info: dict[str, str] = {}
        for item in soup.select(".info-item"):
            k, v = item.select_one(".info-name"), item.select_one(".info-value")
            if k and v:
                info[k.get_text(strip=True).rstrip(":")] = v.get_text(" ", strip=True)
        status = info.get("Tình trạng", "")

        translator_el = soup.select_one(".fantrans-value a") or soup.select_one(".series-owner_name a")
        cover = ""
        cover_el = soup.select_one(".series-cover .img-in-ratio")
        if cover_el and (m := _BG_URL.search(cover_el.get("style", ""))):
            cover = m.group(1)
        if not cover and (og := soup.find("meta", property="og:image")):
            cover = og.get("content", "")

        kind = {"ai-dich": "machine", "sang-tac": "original"}.get(prefix, "translation")
        genres = list(dict.fromkeys(a.get_text(strip=True) for a in soup.select(".series-gernes a")))
        if any(g.lower() in ("machine translation", "mtl", "ai dịch") for g in genres):
            kind = "machine"

        summary = soup.select_one(".summary-content")
        return Novel(
            source=self.id,
            id=novel_id,
            url=url,
            title=title or f"hako-{novel_id}",
            author=info.get("Tác giả", ""),
            status=status,
            completed="hoàn thành" in status.lower(),
            kind=kind,
            translator=translator_el.get_text(strip=True) if translator_el else "",
            description=summary.get_text("\n", strip=True) if summary else "",
            genres=genres,
            cover_url=cover if "nocover" not in cover else "",
            volumes=self._parse_volumes(soup),
        )

    def _parse_volumes(self, soup: BeautifulSoup) -> list[Volume]:
        volumes: list[Volume] = []
        for section in soup.select("section.volume-list"):
            header = section.find("header")
            if not header:
                continue
            vid = (header.get("id") or "").removeprefix("volume_") or str(len(volumes) + 1)
            title_el = header.select_one(".sect-title")
            title = title_el.get_text(" ", strip=True) if title_el else f"Tập {len(volumes) + 1}"

            cover = ""
            cov = section.select_one(".volume-cover .img-in-ratio")
            if cov and (m := _BG_URL.search(cov.get("style", ""))) and "nocover" not in m.group(1):
                cover = self.abs(m.group(1))

            chapters = []
            for li in section.select("ul.list-chapters li"):
                a = li.select_one(".chapter-name a")
                if not a or not a.get("href"):
                    continue
                href = self.normalize_url(self.abs(a["href"]))
                cm = _CHAPTER_ID.search(href)
                locked = bool(li.select_one(".fa-lock, .fa-user-lock, .chapter-locked"))
                chapters.append(ChapterRef(
                    id=cm.group(1) if cm else href.rsplit("/", 1)[-1],
                    title=a.get("title") or a.get_text(strip=True),
                    url=href,
                    locked=locked,
                ))
            if chapters:
                volumes.append(Volume(id=vid, title=title, cover_url=cover, chapters=chapters))
        return volumes

    # ── Chương ────────────────────────────────────────────────────────────────

    def fetch_chapter(self, http: HttpClient, ref: ChapterRef,
                      cancel: threading.Event | None = None) -> Chapter:
        r = http.get(self.normalize_url(ref.url), cancel=cancel)
        self._raise_if_login_page(r.url, r.text)
        chapter = self.parse_chapter(r.text, ref)
        if not chapter.elements:
            if _LOGIN_HINT.search(r.text) and not http.has_cookies:
                raise LoginRequired("Chương này cần đăng nhập Hako")
            raise LngetError("Chương không có nội dung (có thể site đổi cấu trúc)")
        return chapter

    def parse_chapter(self, html: str, ref: ChapterRef) -> Chapter:
        soup = self.soup(html)
        title_el = soup.select_one("h4.title-item")
        title = title_el.get_text(strip=True) if title_el else ref.title

        root = None
        protected = soup.select_one("#chapter-c-protected")
        if protected is not None:
            decoded = decrypt_protected(protected.get("data-s", ""), protected.get("data-k", ""),
                                        protected.get("data-c", ""))
            if decoded:
                root = BeautifulSoup(decoded, "lxml").body
        if root is None:
            root = soup.select_one("#chapter-content")
        if root is None:
            return Chapter(id=ref.id, title=title, url=ref.url)

        elements = extract_elements(
            root, self.abs,
            clean=lambda t: _NOTE_MARK.sub("", t).strip(),
            skip=lambda tag: tag.get("id") == "chapter-c-protected",
        )
        return Chapter(id=ref.id, title=title or ref.title, url=ref.url, elements=elements)

    def image_referer(self, image_url: str, page_url: str) -> str | None:
        host = urlparse(image_url).netloc
        # CDN của Hako chặn request không có Referer của site (403)
        if "hako" in host or "docln" in host:
            return self.base_url + "/"
        if "imgur" in host or "discordapp" in host or "blogspot" in host:
            return None
        return page_url

    def is_own_image(self, image_url: str) -> bool:
        host = urlparse(image_url).netloc.lower()
        return "hako" in host or "docln" in host

    # ── Đăng nhập ─────────────────────────────────────────────────────────────

    def login(self, http: HttpClient, username: str, password: str) -> str:
        http.clear_cookies()
        r = http.get(self.login_url)
        token_el = self.soup(r.text).select_one('form input[name="_token"]')
        if not token_el:
            raise LngetError("Không đọc được form đăng nhập Hako (site có thể đã đổi)")
        r = http.post(self.login_url, data={
            "_token": token_el.get("value", ""),
            "name": username,
            "password": password,
            "remember": "on",
        }, referer=self.login_url)
        if urlparse(r.url).path.rstrip("/").endswith("/login"):
            err = self.soup(r.text).select_one(".invalid-feedback, .alert-danger, .text-danger")
            raise LngetError("Đăng nhập thất bại: " + (err.get_text(" ", strip=True) if err
                                                         else "sai tên đăng nhập hoặc mật khẩu"))
        http.capture_cookies()
        return self.whoami(http) or username

    def whoami(self, http: HttpClient) -> str | None:
        if not http.has_cookies:
            return None
        r = http.get(self.base_url + "/", retries=2)
        return self.parse_username(r.text)

    @staticmethod
    def parse_username(html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        logout = soup.select_one('form[action*="logout"], a[href*="logout"]')
        if not logout and soup.select_one('a[href$="/login"]'):
            return None
        for sel in (".nav-user_name", ".user-name", ".navbar-user .username", 'a[href*="/thanh-vien/"] span'):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return "tài khoản Hako" if logout else None

    def is_login_cookie(self, cookies: list[dict]) -> bool:
        return any(c["name"].startswith("remember_web") for c in cookies)

    # ── Danh sách ─────────────────────────────────────────────────────────────

    def list_novels(self, http: HttpClient, page: int, list_url: str | None = None) -> list[str]:
        base = self.normalize_url(list_url) if list_url else self.base_url + "/danh-sach"
        sep = "&" if "?" in base else "?"
        r = http.get(f"{base}{sep}page={page}")
        return self.parse_listing(r.text)

    def parse_listing(self, html: str) -> list[str]:
        urls: list[str] = []
        for a in self.soup(html).select(".thumb_attr.series-title a[href], .series-title a[href]"):
            path = urlparse(self.abs(a["href"])).path
            m = _NOVEL_PATH.match(path)
            if m:
                u = self.base_url + m.group(0)
                if u not in urls:
                    urls.append(u)
        return urls

    def _raise_if_login_page(self, final_url: str, html: str) -> None:
        if urlparse(final_url).path.rstrip("/").endswith("/login"):
            raise LoginRequired("Nội dung này cần đăng nhập Hako")


def decrypt_protected(scheme: str, key: str, data: str) -> str:
    """Giải mã nội dung chương Hako (`xor_shuffle`: các chunk base64 XOR với key, có số thứ tự 4 chữ số)."""
    if scheme != "xor_shuffle" or not key or not data:
        return ""
    try:
        chunks = json.loads(data)
    except ValueError:
        return ""
    kb = key.encode("utf-8")
    parts = []
    for chunk in sorted(chunks, key=lambda c: int(c[:4])):
        try:
            raw = base64.b64decode(chunk[4:])
        except ValueError:
            continue
        parts.append(bytes(b ^ kb[i % len(kb)] for i, b in enumerate(raw)))
    return b"".join(parts).decode("utf-8", errors="replace")
