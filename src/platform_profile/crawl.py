"""Fetch seed URLs and same-domain links, write sources/, update the manifest."""

from __future__ import annotations

import shutil
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from . import __version__
from .config import Layout, Profile
from .extract import extract
from .manifest import Entry, Manifest
from .sources import render_source, sha256_text, slug_for

USER_AGENT = f"platform-profile/{__version__} (+https://github.com/nunomnferreirapt/platform-profile)"
SKIP_SUFFIXES = (
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".zip", ".gz", ".tar",
    ".css", ".js", ".json", ".xml", ".rss", ".atom", ".mp4", ".mp3", ".woff", ".woff2", ".ttf",
)


@dataclass
class CrawlResult:
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"crawl: {len(self.new)} new, {len(self.changed)} changed, "
            f"{len(self.unchanged)} unchanged, {len(self.failed)} failed, {len(self.removed)} removed"
        )


def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True)


def host_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize_url(url: str) -> str | None:
    """Drop fragments and trailing slashes; return None for anything we never fetch."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    path = parts.path or "/"
    if path.lower().endswith(SKIP_SUFFIXES):
        return None
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Crawler:
    def __init__(
        self,
        profile_dir: Path,
        client: httpx.Client | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.layout = Layout(profile_dir)
        self.profile = Profile.load(profile_dir)
        self.client = client or make_client()
        self.now = now or utc_now
        self._robots: dict[str, RobotFileParser] = {}

    def run(self) -> CrawlResult:
        layout, rules = self.layout, self.profile.crawl
        old = Manifest.load(layout.manifest)
        stamp = self.now().isoformat(timespec="seconds")
        new = Manifest(crawled_at=stamp)
        result = CrawlResult()

        if layout.prev_dir.exists():
            shutil.rmtree(layout.prev_dir)
        layout.sources_dir.mkdir(parents=True, exist_ok=True)

        hosts = {host_of(seed.url) for seed in self.profile.seeds}
        queue: deque[tuple[str, int, str]] = deque()
        seen: set[str] = set()
        for seed in self.profile.seeds:
            url = normalize_url(seed.url)
            if url and url not in seen:
                seen.add(url)
                queue.append((url, 0, seed.kind))

        taken_paths = {entry.path for entry in old.pages.values()}
        attempts = 0
        while queue and attempts < rules.max_pages:
            url, depth, kind = queue.popleft()
            if not self._robots_allow(url):
                continue
            attempts += 1
            status, html = self._fetch(url)
            if status == "skip":
                continue
            if status == "error":
                result.failed.append(url)
                if url in old.pages:
                    new.pages[url] = old.pages[url]
                continue

            page = extract(html, url)
            digest = sha256_text(page.text)
            previous = old.pages.get(url)
            rel_path = previous.path if previous else self._unique_path(url, taken_paths)
            taken_paths.add(rel_path)

            if previous and previous.sha256 == digest and (layout.root / rel_path).is_file():
                result.unchanged.append(url)
                new.pages[url] = previous
            else:
                if previous:
                    self._snapshot(previous.path)
                    result.changed.append(url)
                else:
                    result.new.append(url)
                meta = {"url": url, "title": page.title, "fetched_at": stamp, "sha256": digest, "kind": kind}
                (layout.root / rel_path).write_text(render_source(meta, page.text), encoding="utf-8")
                new.pages[url] = Entry(url, digest, stamp, rel_path, page.title, kind)

            if depth >= rules.max_depth:
                continue
            for link in page.links:
                candidate = normalize_url(link)
                if not candidate or candidate in seen:
                    continue
                if rules.same_domain_only and host_of(candidate) not in hosts:
                    continue
                seen.add(candidate)
                queue.append((candidate, depth + 1, kind))

        for url, entry in old.pages.items():
            if url not in new.pages:
                result.removed.append(url)
                self._snapshot(entry.path)
                (layout.root / entry.path).unlink(missing_ok=True)

        if old.crawled_at is not None:
            # Only a real previous crawl becomes history; the empty manifest from `init` does not.
            shutil.copyfile(layout.manifest, layout.manifest_prev)
        new.save(layout.manifest)
        return result

    def _unique_path(self, url: str, taken: set[str]) -> str:
        slug = slug_for(url)
        rel = f"sources/{slug}.md"
        if rel in taken:
            rel = f"sources/{slug}-{sha256_text(url)[:6]}.md"
        return rel

    def _snapshot(self, rel_path: str) -> None:
        source = self.layout.root / rel_path
        if source.is_file():
            target = self.layout.prev_dir / Path(rel_path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def _fetch(self, url: str) -> tuple[str, str]:
        try:
            response = self.client.get(url)
        except httpx.HTTPError:
            return "error", ""
        if response.status_code >= 400:
            return "error", ""
        content_type = response.headers.get("content-type", "")
        if content_type and "html" not in content_type.lower():
            return "skip", ""
        return "ok", response.text

    def _robots_allow(self, url: str) -> bool:
        if not self.profile.crawl.respect_robots:
            return True
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(base)
        if parser is None:
            parser = RobotFileParser()
            try:
                response = self.client.get(f"{base}/robots.txt")
            except httpx.HTTPError:
                response = None
            if response is not None and response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                parser.allow_all = True
            self._robots[base] = parser
        return parser.can_fetch(USER_AGENT, url)
