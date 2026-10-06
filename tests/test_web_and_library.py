import pytest
from fastapi.testclient import TestClient

from lnget.engine import parse_volume_spec
from lnget.http import LngetError
from lnget.library import Library, safe_name
from lnget.models import Chapter, ChapterRef, Element, Novel, Volume


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LNGET_HOME", str(tmp_path / "home"))
    from lnget.config import Settings, save_settings
    save_settings(Settings(output=str(tmp_path / "out")))
    return tmp_path


@pytest.fixture
def client():
    from lnget.web.server import create_app
    return TestClient(create_app(), base_url="http://127.0.0.1:8765")


def test_volume_spec():
    assert parse_volume_spec(None, 5) is None
    assert parse_volume_spec("1,3-4", 5) == [1, 3, 4]
    assert parse_volume_spec("4-", 6) == [4, 5, 6]
    assert parse_volume_spec("0,9", 3) == []
    with pytest.raises(LngetError):
        parse_volume_spec("abc", 3)


def test_safe_name():
    assert safe_name('"A: B?" <C>') == "A - B C"
    assert len(safe_name("x" * 300, 50)) == 50


def _novel(title="Truyện A", completed=False):
    return Novel(source="hako", id="1", url="https://docln.sbs/truyen/1-a", title=title, completed=completed,
                 volumes=[Volume("10", "Tập 1", chapters=[ChapterRef("100", "C1", "u")])])


def test_library_moves_dir_when_title_or_status_changes(tmp_path):
    lib = Library(tmp_path / "out", split_by_status=True)
    nd = lib.open(_novel())
    nd.save_chapter(Chapter("100", "C1", "u", [Element.p("xin chào")]))
    assert "Chưa hoàn thành" in str(nd.path)

    nd2 = lib.open(_novel(title="Truyện A (đổi tên)", completed=True))
    assert "Đã hoàn thành" in str(nd2.path) and "đổi tên" in nd2.path.name
    assert nd2.load_chapter("100").elements[0].text == "xin chào"
    assert len(lib.scan()) == 1


def test_image_cache_roundtrip(tmp_path):
    nd = Library(tmp_path / "out").open(_novel())
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    nd.save_image("https://x/y.png", png)
    assert nd.load_image("https://x/y.png") == png
    assert nd.image_path("https://x/y.png").suffix == ".png"


def test_guard_rejects_foreign_host_and_missing_header(client):
    assert TestClient(client.app, base_url="http://evil.example").get("/api/status").status_code == 403
    assert client.post("/api/preview", json={"url": "x"}).status_code == 403
    assert client.get("/api/status").status_code == 200


def test_unsupported_url_is_friendly_error(client):
    r = client.post("/api/preview", json={"url": "https://example.com/abc"}, headers={"X-Lnget": "1"})
    assert r.status_code == 400 and "Chưa hỗ trợ" in r.json()["detail"]


def test_open_outside_output_refused(client, tmp_path):
    r = client.post("/api/open", json={"path": str(tmp_path / "home")}, headers={"X-Lnget": "1"})
    assert r.status_code == 400


def test_settings_update_validates(client):
    r = client.put("/api/settings", json={"chapter_workers": 99, "formats": ["pdf", "bad"]},
                   headers={"X-Lnget": "1"})
    assert r.status_code == 200
    assert r.json()["chapter_workers"] == 8 and r.json()["formats"] == ["pdf"]
