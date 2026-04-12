from __future__ import annotations

from html.parser import HTMLParser


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = " ".join(part for part in self._text_parts if part).strip()
        self.links.append({"href": self._current_href, "text": text})
        self._current_href = None
        self._text_parts = []


def extract_links(html: str) -> list[dict[str, str]]:
    parser = LinkCollector()
    parser.feed(html)
    return parser.links


class AssetCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = dict(attrs)
        if tag.lower() == "script":
            src = attr_map.get("src")
            if src:
                self.assets.append(src)
        if tag.lower() == "link":
            href = attr_map.get("href")
            if href:
                self.assets.append(href)


def extract_assets(html: str) -> list[str]:
    parser = AssetCollector()
    parser.feed(html)
    return parser.assets
