import base64
import json
from pathlib import Path

import pytest

from lnget.models import ChapterRef
from lnget.sources.hako import HakoSource, decrypt_protected

FIX = Path(__file__).parent / "fixtures" / "hako"
NOVEL_URL = "https://docln.sbs/truyen/15056-kisu-nante-dekinai-deshoto-chouhatsu-suru-namaikina-osananajimi-wo-wakarasete-yattara-yosou-ijou-ni-dereta"


@pytest.fixture
def src():
    return HakoSource()


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_matches_old_domains_and_normalizes(src):
    assert src.matches("https://ln.hako.vn/truyen/1-abc")
    assert src.matches("docln.net/truyen/1-abc")
    assert not src.matches("https://valvrareteam.net/truyen/x")
    assert src.novel_url("https://ln.hako.vn/truyen/123-abc/c456-chuong-1") == "https://docln.sbs/truyen/123-abc"


def test_custom_domain():
    s = HakoSource("https://new-hako.example/")
    assert s.base_url == "https://new-hako.example"
    assert s.matches("https://new-hako.example/truyen/1-a")
    assert s.normalize_url("https://docln.sbs/truyen/1-a") == "https://new-hako.example/truyen/1-a"


def test_parse_novel(src):
    n = src.parse_novel(read("novel.html"), NOVEL_URL)
    assert n.id == "15056"
    assert n.title.startswith('"Cậu chẳng thể hôn được đâu ha?"')
    assert n.completed and n.status == "Đã hoàn thành"
    assert n.translator == "Arteria"
    assert n.genres == ["Comedy", "Romance", "School Life"]
    assert n.cover_url.startswith("https://i2.hako.vip/")
    assert [v.title for v in n.volumes][:3] == ["Vol 1", "Vol 2", "Vol 3"]
    assert n.volumes[0].id == "20918"
    assert n.volumes[0].cover_url.startswith("https://i.hako.vip/")
    first = n.volumes[0].chapters[0]
    assert (first.id, first.title) == ("113038", "Minh họa")
    assert n.chapter_count == 42


def test_parse_chapter_decrypts_and_extracts_images(src):
    ref = ChapterRef(id="113038", title="Minh họa", url=NOVEL_URL + "/c113038-minh-hoa")
    ch = src.parse_chapter(read("chapter_illustrations.html"), ref)
    assert ch.title == "Minh họa"
    assert len(ch.image_urls) == 31
    assert ch.image_urls[1] == "https://i.imgur.com/2WwzAOX.jpeg"
    assert "&amp;" not in ch.image_urls[0]


def test_decrypt_roundtrip_handles_multibyte_split():
    key = "abc123"
    raw = "<p>Tiếng Việt có dấu — ổn định</p>".encode()
    kb = key.encode()
    halves = [raw[:7], raw[7:]]  # cắt giữa ký tự nhiều byte
    chunks = []
    for i, part in enumerate(halves):
        enc = bytes(b ^ kb[j % len(kb)] for j, b in enumerate(part))
        chunks.append(f"{i:04d}" + base64.b64encode(enc).decode())
    out = decrypt_protected("xor_shuffle", key, json.dumps(list(reversed(chunks))))
    assert out == raw.decode()


def test_parse_listing(src):
    urls = src.parse_listing(read("listing.html"))
    assert len(urls) > 10
    assert all(u.startswith("https://docln.sbs/truyen/") and "/c" not in u.split("/truyen/")[1] for u in urls)
    assert len(urls) == len(set(urls))


def test_image_referer(src):
    assert src.image_referer("https://i.hako.vip/x.jpg", "https://docln.sbs/truyen/1/c2") == "https://docln.sbs/"
    assert src.image_referer("https://i.imgur.com/x.jpg", "p") is None


def test_parse_username_logged_out(src):
    assert src.parse_username(read("novel.html")) is None
