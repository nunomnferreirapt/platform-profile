"""HTML to clean markdown text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

STRIP_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe", "svg", "button", "template"]
STRIP_ROLES = {"navigation", "banner", "contentinfo", "complementary", "search"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
CONTAINERS = {"div", "section", "article", "main", "body", "html", "figure", "details", "dl", "dd", "dt", "summary", "figcaption", "span", "li", "td", "th", "tr", "tbody", "thead"}
BLOCKS = HEADINGS | {"p", "ul", "ol", "table", "pre", "blockquote", "hr"} | CONTAINERS
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")


@dataclass
class Page:
    title: str
    text: str
    links: list[str] = field(default_factory=list)


def extract(html: str, base_url: str) -> Page:
    """Return the page title, its body as markdown, and every absolute link it carries."""
    soup = BeautifulSoup(html, "html.parser")
    links = _links(soup, base_url)
    title = _title(soup, base_url)
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(STRIP_TAGS):
        if not getattr(tag, "decomposed", False):
            tag.decompose()
    for tag in soup.find_all(attrs={"role": True}):
        if not getattr(tag, "decomposed", False) and tag.get("role") in STRIP_ROLES:
            tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    blocks: list[str] = []
    _walk(root, blocks)
    return Page(title=title, text=_tidy(blocks), links=links)


def _title(soup: BeautifulSoup, base_url: str) -> str:
    if soup.title and soup.title.string:
        return _squash(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        return _squash(h1.get_text())
    return base_url


def _links(soup: BeautifulSoup, base_url: str) -> list[str]:
    seen: dict[str, None] = {}
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith("#") or href.lower().startswith(SKIP_SCHEMES):
            continue
        url, _ = urldefrag(urljoin(base_url, href))
        seen.setdefault(url, None)
    return list(seen)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _text(tag: Tag) -> str:
    return _squash(tag.get_text())


def _walk(node: Tag, out: list[str]) -> None:
    inline: list[str] = []

    def flush() -> None:
        if inline:
            paragraph = _squash(" ".join(inline))
            if paragraph:
                out.append(paragraph)
            inline.clear()

    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            inline.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name or ""
        if name not in BLOCKS:
            inline.append(child.get_text())
            continue
        flush()
        if name in HEADINGS:
            text = _text(child)
            if text:
                out.append("#" * int(name[1]) + " " + text)
        elif name == "p":
            text = _text(child)
            if text:
                out.append(text)
        elif name in ("ul", "ol"):
            out.extend(_list(child, 0))
        elif name == "table":
            out.extend(_table(child))
        elif name == "pre":
            code = child.get_text().strip("\n")
            if code.strip():
                out.append("```\n" + code + "\n```")
        elif name == "blockquote":
            text = _text(child)
            if text:
                out.append("> " + text)
        elif name == "hr":
            continue
        else:
            _walk(child, out)
    flush()


def _list(tag: Tag, level: int) -> list[str]:
    lines: list[str] = []
    ordered = tag.name == "ol"
    for index, item in enumerate(tag.find_all("li", recursive=False), start=1):
        nested = item.find_all(["ul", "ol"], recursive=False)
        for sub in nested:
            sub.extract()
        marker = f"{index}." if ordered else "-"
        text = _text(item)
        if text:
            lines.append("  " * level + f"{marker} {text}")
        for sub in nested:
            lines.extend(_list(sub, level + 1))
    return lines


def _table(tag: Tag) -> list[str]:
    rows: list[list[str]] = []
    for tr in tag.find_all("tr"):
        cells = [_text(cell).replace("|", "\\|") for cell in tr.find_all(["th", "td"], recursive=False)]
        if any(cells):
            rows.append(cells)
    if not rows:
        return []
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return ["\n".join(lines)]


def _tidy(blocks: list[str]) -> str:
    text = "\n\n".join(block for block in blocks if block)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
