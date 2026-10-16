"""Reading and writing sources/<slug>.md files with a YAML front matter header."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slug_for(url: str) -> str:
    """Turn a URL path into a file slug. The site root becomes `index`."""
    path = urlsplit(url).path.strip("/")
    path = re.sub(r"\.(html?|php|aspx?)$", "", path, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return slug or "index"


def render_source(meta: dict[str, str], text: str) -> str:
    header = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
    return f"---\n{header}---\n\n{text}\n"


def split_source(content: str) -> tuple[dict, str]:
    """Return (front matter, body) for a sources file. Front matter is {} when absent."""
    match = FRONT_MATTER.match(content)
    if not match:
        return {}, content
    meta = yaml.safe_load(match.group(1)) or {}
    return meta, content[match.end() :].lstrip("\n")


def read_source(path: Path) -> tuple[dict, str]:
    return split_source(path.read_text(encoding="utf-8"))
