"""Trích đoạn văn + ảnh từ HTML nội dung chương (dùng chung cho các source)."""
from __future__ import annotations

import re
from typing import Callable

from bs4 import NavigableString, Tag

from lnget.models import Element

BLOCK_TAGS = {
    "p", "div", "section", "article", "blockquote", "li", "ul", "ol", "center",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "tr", "figure", "figcaption", "hr",
}
SKIP_TAGS = {"script", "style", "noscript", "iframe", "button", "svg", "form", "ins"}
_WS = re.compile(r"[ \t\r\n ]+")


def extract_elements(root: Tag, to_abs: Callable[[str], str],
                     clean: Callable[[str], str] | None = None,
                     skip: Callable[[Tag], bool] | None = None) -> list[Element]:
    out: list[Element] = []
    buf: list[str] = []

    def flush() -> None:
        text = _WS.sub(" ", "".join(buf)).strip()
        buf.clear()
        if clean:
            text = clean(text)
        if text:
            out.append(Element.p(text))

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                if type(child) is NavigableString:  # bỏ comment / CDATA
                    buf.append(str(child))
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            if name in SKIP_TAGS or (skip and skip(child)):
                continue
            if _hidden(child):
                continue
            if name == "img":
                src = _img_src(child)
                if src and not src.startswith("data:"):
                    flush()
                    out.append(Element.img(to_abs(src)))
                continue
            if name == "br":
                flush()
                continue
            if name in BLOCK_TAGS:
                flush()
                walk(child)
                flush()
            else:
                walk(child)

    walk(root)
    flush()
    return out


def _img_src(img: Tag) -> str:
    for attr in ("data-src", "data-original", "data-lazy-src", "src"):
        v = (img.get(attr) or "").strip()
        if v and not v.endswith("loading.svg"):
            return v
    return ""


def _hidden(tag: Tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    return "display:none" in style
