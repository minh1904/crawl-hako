"""Danh sách site được hỗ trợ + HttpClient dùng chung cho từng site."""
from __future__ import annotations

import threading

from lnget.config import Settings, data_dir, load_settings
from lnget.http import HttpClient, LngetError
from lnget.sources.base import Source
from lnget.sources.hako import HakoSource

SOURCE_CLASSES: list[type[Source]] = [HakoSource]

_clients: dict[str, HttpClient] = {}
_lock = threading.Lock()


def all_sources(settings: Settings | None = None) -> list[Source]:
    settings = settings or load_settings()
    return [cls(settings.domains.get(cls.id)) for cls in SOURCE_CLASSES]


def get_source(source_id: str, settings: Settings | None = None) -> Source:
    for s in all_sources(settings):
        if s.id == source_id:
            return s
    raise LngetError(f"Không có source '{source_id}'")


def find_source(url: str, settings: Settings | None = None) -> Source:
    url = url.strip()
    for s in all_sources(settings):
        if s.matches(url):
            return s
    names = ", ".join(f"{s.name} ({s.domain})" for s in all_sources(settings))
    raise LngetError(f"Chưa hỗ trợ trang này. Các site hỗ trợ: {names}")


def client_for(source: Source, settings: Settings | None = None) -> HttpClient:
    settings = settings or load_settings()
    with _lock:
        c = _clients.get(source.id)
        if c is None:
            c = HttpClient(source.id, settings.delay, data_dir() / "sessions" / f"{source.id}.json",
                           site_host=source.domain)
            _clients[source.id] = c
        c.throttle.delay = settings.delay
        return c
