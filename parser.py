"""
parser.py — Parse HTML từ docln.sbs
"""
import base64
import json
import re
import logging
from bs4 import BeautifulSoup, Tag
from fetcher import absolute_url

logger = logging.getLogger(__name__)


def parse_novel_info(soup: BeautifulSoup) -> dict:
    """Parse thông tin truyện từ trang /truyen/{id}.
    Trả về: {title, author, status, description, genres, cover_url, url}
    """
    info = {
        "title": "",
        "author": "",
        "status": "",
        "translator": "",
        "translation_type": "human",
        "description": "",
        "genres": [],
        "cover_url": "",
        "url": "",
    }

    # Canonical URL
    canonical = soup.find("link", rel="canonical")
    if canonical:
        info["url"] = canonical.get("href", "")

    # Ảnh bìa từ og:image
    og_image = soup.find("meta", property="og:image")
    if og_image:
        info["cover_url"] = og_image.get("content", "")

    # Tên truyện
    title_tag = soup.find("title")
    if title_tag:
        # Format: "Tên Truyện - Cổng Light Novel - Đọc Light Novel"
        raw = title_tag.get_text(strip=True)
        info["title"] = raw.split(" - ")[0].strip()

    # Tác giả, tình trạng từ .info-item
    for item in soup.select(".info-item"):
        name_el = item.find(class_="info-name")
        value_el = item.find(class_="info-value")
        if not name_el or not value_el:
            continue
        name = name_el.get_text(strip=True).rstrip(":")
        if "Tác giả" in name:
            a = value_el.find("a")
            info["author"] = a.get_text(strip=True) if a else value_el.get_text(strip=True)
        elif "Tình trạng" in name:
            info["status"] = value_el.get_text(strip=True)
        elif any(k in name for k in ("Nhóm dịch", "Người dịch", "Dịch giả", "Nhóm")):
            a = value_el.find("a")
            info["translator"] = a.get_text(strip=True) if a else value_el.get_text(strip=True)

    # Mô tả
    summary = soup.select_one(".summary-content")
    if summary:
        info["description"] = summary.get_text(separator="\n", strip=True)

    # Thể loại (links /the-loai/)
    genres = []
    seen_genres = set()
    for a in soup.select('a[href*="/the-loai/"]'):
        g = a.get_text(strip=True)
        if g and g not in seen_genres:
            genres.append(g)
            seen_genres.add(g)
    info["genres"] = genres

    # Detect machine translation từ genres
    _machine_kw = {"machine translation", "mtl", "máy dịch", "machine-translation"}
    if any(g.lower() in _machine_kw for g in genres):
        info["translation_type"] = "machine"

    return info


def parse_volume_list(soup: BeautifulSoup) -> list[dict]:
    """Parse danh sách tập và chương từ trang truyện.

    Trả về list of:
    {
        volume_id: str,
        volume_title: str,
        volume_cover_url: str,
        chapters: [{title, url, date}]
    }
    """
    volumes = []

    # Sidebar volume titles (ol.list-volume)
    # Note: lxml lowercases HTML attributes, so data-scrollTo → data-scrollto
    volume_title_map = {}
    for li in soup.select("ol.list-volume li"):
        scroll_to = li.get("data-scrollto", "").lstrip("#")  # e.g. "volume_37669"
        title_el = li.find(class_="list_vol-title")
        if title_el and scroll_to:
            volume_title_map[scroll_to] = title_el.get_text(strip=True)

    # Các section volume
    sections = soup.select("section.volume-list.at-series")
    if not sections:
        return volumes

    for section in sections:
        header = section.find("header")
        if not header:
            continue

        volume_id = header.get("id", "")  # e.g. "volume_37669"

        # Tên tập từ sidebar map, fallback từ header text
        volume_title = volume_title_map.get(volume_id, "")
        if not volume_title:
            title_el = header.find(class_="sect-header-title")
            if title_el:
                volume_title = title_el.get_text(strip=True)

        # Ảnh bìa tập
        cover_url = ""
        cover_div = section.select_one(".volume-cover .content")
        if cover_div:
            style = cover_div.get("style", "")
            match = re.search(r"url\(['\"]?([^'\")\s]+)['\"]?\)", style)
            if match:
                cover_url = absolute_url(match.group(1))
                # Nếu là nocover placeholder thì bỏ
                if "nocover" in cover_url:
                    cover_url = ""

        # Chapters
        chapters = []
        for li in section.select("ul.list-chapters.at-series li"):
            a = li.select_one(".chapter-name a")
            if not a:
                continue
            chap_title = a.get_text(strip=True)
            chap_url = absolute_url(a.get("href", ""))
            date_el = li.select_one(".chapter-time")
            chap_date = date_el.get_text(strip=True) if date_el else ""
            chapters.append({"title": chap_title, "url": chap_url, "date": chap_date})

        if chapters:
            volumes.append({
                "volume_id": volume_id,
                "volume_title": volume_title,
                "volume_cover_url": cover_url,
                "chapters": chapters,
            })

    return volumes


def _decrypt_xor_shuffle(data_c: str, data_k: str) -> str:
    """Giải mã nội dung chương được mã hóa bằng xor_shuffle.

    Thuật toán (từ app.js):
      m(t) = base64decode(t) → bytes
      p(t, key) = XOR từng byte với key[i % len(key)]
      f(r) = UTF-8 decode

    data-c là JSON array các chunk, mỗi chunk bắt đầu bằng 4 ký tự index (ví dụ "0001xxx")
    Sắp xếp theo index, bỏ 4 ký tự đầu, giải mã, ghép lại.
    """
    try:
        chunks = json.loads(data_c)
    except Exception:
        return ""
    if not chunks:
        return ""

    key = data_k
    key_bytes = [ord(c) for c in key]
    key_len = len(key_bytes)

    # Sort by first 4 chars as integer
    chunks.sort(key=lambda s: int(s[:4], 10))

    parts = []
    for chunk in chunks:
        encoded = chunk[4:]  # bỏ 4 ký tự index
        try:
            raw = base64.b64decode(encoded)
        except Exception:
            continue
        decrypted = bytes(b ^ key_bytes[i % key_len] for i, b in enumerate(raw))
        try:
            parts.append(decrypted.decode("utf-8"))
        except Exception:
            parts.append(decrypted.decode("utf-8", errors="replace"))

    return "".join(parts)


def _parse_protected_content(soup: BeautifulSoup) -> list[dict]:
    """Parse nội dung chương đã được mã hóa xor_shuffle.
    Trả về list elements giống parse_chapter_content.
    """
    protected = soup.select_one("#chapter-c-protected")
    if not protected:
        return []

    data_s = protected.get("data-s", "")
    data_k = protected.get("data-k", "")
    data_c = protected.get("data-c", "")

    if data_s != "xor_shuffle" or not data_k or not data_c:
        return []

    html_content = _decrypt_xor_shuffle(data_c, data_k)
    if not html_content:
        return []

    # Parse HTML content đã giải mã
    # lxml bọc trong <html><body>, nên cần lấy body
    inner_soup = BeautifulSoup(html_content, "lxml")
    body = inner_soup.find("body") or inner_soup
    return _extract_elements_from_soup(body)


_NOTE_RE = re.compile(r"\[note\d+\]", re.IGNORECASE)


def _clean_text(text: str) -> str:
    """Xóa footnote markers như [note12345]."""
    return _NOTE_RE.sub("", text).strip()


def _extract_elements_from_soup(soup_or_tag) -> list[dict]:
    """Extract elements (text + images) từ soup/tag."""
    elements = []
    for child in soup_or_tag.children:
        if not isinstance(child, Tag):
            text = _clean_text(str(child))
            if text:
                elements.append({"type": "text", "content": text})
            continue

        tag_name = child.name
        if tag_name == "img":
            src = child.get("src", "")
            if src:
                elements.append({"type": "image", "url": absolute_url(src)})
        elif tag_name in ("p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6"):
            imgs = child.find_all("img")
            if imgs:
                for img in imgs:
                    src = img.get("src", "")
                    if src:
                        elements.append({"type": "image", "url": absolute_url(src)})
                for img in imgs:
                    img.decompose()
                text = _clean_text(child.get_text(strip=True))
                if text:
                    elements.append({"type": "text", "content": text})
            else:
                text = _clean_text(child.get_text(strip=True))
                if text:
                    elements.append({"type": "text", "content": text})
        elif tag_name == "br":
            elements.append({"type": "text", "content": ""})
    return elements


def parse_chapter_content(soup: BeautifulSoup) -> dict:
    """Parse nội dung 1 chương.

    Trả về:
    {
        title: str,
        elements: [{"type": "text", "content": str} | {"type": "image", "url": str}]
    }
    """
    # Tiêu đề chương từ <h1> hoặc canonical
    title = ""
    # Thử lấy từ h1 trong reading area
    h1 = soup.select_one(".rd_sidebar-header .series-name, h1.chapter-title, .chapter-name h1")
    if h1:
        title = h1.get_text(strip=True)

    if not title:
        title_tag = soup.find("title")
        if title_tag:
            raw = title_tag.get_text(strip=True)
            # Format: "Chương X - Tên Truyện - ..."
            parts = raw.split(" - ")
            # Lấy phần đầu (tiêu đề chương), bỏ "Đọc " prefix nếu có
            title = parts[0].strip()
            if title.lower().startswith("đọc "):
                # Lấy phần thứ 2 nếu có (thực ra là tên truyện, không phải tiêu đề)
                # Thử lấy từ selector khác
                title = ""

    elements = []

    # Ưu tiên: giải mã nội dung được bảo vệ
    protected_elements = _parse_protected_content(soup)
    if protected_elements:
        elements = protected_elements
    else:
        # Fallback: parse trực tiếp #chapter-content
        content_div = soup.select_one("div#chapter-content")
        if not content_div:
            logger.warning("Không tìm thấy #chapter-content")
            return {"title": title, "elements": elements}
        elements = _extract_elements_from_soup(content_div)

    # Nếu chưa có title, thử lấy từ element đầu tiên (thường là tên chương ẩn)
    if not title:
        # Tìm <p style="display: none"> chứa tên chương
        content_div = soup.select_one("div#chapter-content")
        if content_div:
            hidden_p = content_div.find("p", style=re.compile(r"display\s*:\s*none"))
            if hidden_p:
                title = hidden_p.get_text(strip=True)

    return {"title": title, "elements": elements}




def parse_listing_page(soup: BeautifulSoup) -> list[str]:
    """Parse danh sách URL truyện từ trang /danh-sach?page=N.
    Trả về list absolute URLs của các truyện.
    """
    urls = []
    seen = set()
    for a in soup.select(".thumb_attr.series-title a[href]"):
        href = a.get("href", "")
        if not href or "/truyen/" not in href:
            continue
        url = absolute_url(href)
        # Chỉ lấy URL trang truyện (không phải chapter)
        # /truyen/{id}-{slug} không có /c{id} ở sau
        parts = url.split("/truyen/")
        if len(parts) < 2:
            continue
        tail = parts[1]
        # Bỏ qua nếu là chapter URL (có /c\d+ hoặc thêm path con)
        sub_parts = tail.split("/")
        if len(sub_parts) > 1 and sub_parts[1].startswith("c"):
            # Lấy URL truyện gốc
            novel_url = absolute_url("/truyen/" + sub_parts[0])
        else:
            novel_url = url

        if novel_url not in seen:
            seen.add(novel_url)
            urls.append(novel_url)

    return urls


def has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
    """Kiểm tra có trang tiếp theo không bằng cách xem trang hiện tại có item không.
    Nếu trang trả về 0 item → hết trang.
    """
    items = parse_listing_page(soup)
    return len(items) > 0
