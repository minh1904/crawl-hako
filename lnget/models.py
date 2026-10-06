"""Mô hình dữ liệu dùng chung cho mọi source, engine và exporter."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Kind = Literal["translation", "machine", "original"]


@dataclass
class Element:
    """Một khối nội dung trong chương: đoạn văn hoặc ảnh."""

    type: Literal["text", "image"]
    text: str = ""
    url: str = ""

    @staticmethod
    def p(text: str) -> "Element":
        return Element("text", text=text)

    @staticmethod
    def img(url: str) -> "Element":
        return Element("image", url=url)


@dataclass
class ChapterRef:
    id: str
    title: str
    url: str
    locked: bool = False  # site đánh dấu cần đăng nhập / trả phí


@dataclass
class Volume:
    id: str
    title: str
    cover_url: str = ""
    chapters: list[ChapterRef] = field(default_factory=list)


@dataclass
class Novel:
    source: str
    id: str
    url: str
    title: str
    author: str = ""
    status: str = ""
    completed: bool = False
    kind: Kind = "translation"
    translator: str = ""
    description: str = ""
    genres: list[str] = field(default_factory=list)
    cover_url: str = ""
    volumes: list[Volume] = field(default_factory=list)

    @property
    def chapter_count(self) -> int:
        return sum(len(v.chapters) for v in self.volumes)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Novel":
        d = dict(d)
        vols = [
            Volume(**{**v, "chapters": [ChapterRef(**c) for c in v.get("chapters", [])]})
            for v in d.pop("volumes", [])
        ]
        return Novel(**d, volumes=vols)


@dataclass
class Chapter:
    id: str
    title: str
    url: str
    elements: list[Element] = field(default_factory=list)

    @property
    def image_urls(self) -> list[str]:
        return [e.url for e in self.elements if e.type == "image" and e.url]

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Chapter":
        return Chapter(
            id=d["id"], title=d["title"], url=d["url"],
            elements=[Element(**e) for e in d.get("elements", [])],
        )


FORMATS = ("epub", "docx", "pdf", "images")
