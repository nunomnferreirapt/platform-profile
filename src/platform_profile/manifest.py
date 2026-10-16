"""manifest.json: one entry per crawled URL."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Entry:
    url: str
    sha256: str
    fetched_at: str
    path: str
    title: str
    kind: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("url")
        return data

    @classmethod
    def from_dict(cls, url: str, data: dict) -> Entry:
        return cls(
            url=url,
            sha256=str(data.get("sha256", "")),
            fetched_at=str(data.get("fetched_at", "")),
            path=str(data.get("path", "")),
            title=str(data.get("title", "")),
            kind=str(data.get("kind", "website")),
        )


@dataclass
class Manifest:
    crawled_at: str | None = None
    pages: dict[str, Entry] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        pages = {url: Entry.from_dict(url, entry) for url, entry in data.get("pages", {}).items()}
        return cls(crawled_at=data.get("crawled_at"), pages=pages)

    def save(self, path: Path) -> None:
        data = {
            "crawled_at": self.crawled_at,
            "pages": {url: entry.to_dict() for url, entry in sorted(self.pages.items())},
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def by_path(self) -> dict[str, Entry]:
        return {entry.path: entry for entry in self.pages.values()}
