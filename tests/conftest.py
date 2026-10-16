"""Shared fixtures: a fake site served from disk through httpx.MockTransport."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from platform_profile.config import init_profile
from platform_profile.crawl import Crawler

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "northwind.example"
ROOT = f"https://{HOST}"


class FakeSite:
    """Serves tests/fixtures as https://northwind.example. Pages can be overridden per test."""

    def __init__(self) -> None:
        self.overrides: dict[str, str] = {}
        self.requests: list[str] = []
        self.clock = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.clock

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append(path)
        if request.url.host != HOST:
            return httpx.Response(404, text="wrong host")
        if path in self.overrides:
            body = self.overrides[path]
            if body == "":
                return httpx.Response(404, text="gone")
            return httpx.Response(200, text=body, headers={"content-type": "text/html"})
        if path == "/robots.txt":
            return httpx.Response(200, text=(FIXTURES / "robots.txt").read_text(), headers={"content-type": "text/plain"})
        if path == "/broken":
            return httpx.Response(500, text="server error")
        if path == "/brochure.pdf":
            return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})
        file = self._file_for(path)
        if file is None:
            return httpx.Response(404, text="not found")
        return httpx.Response(200, text=file.read_text(encoding="utf-8"), headers={"content-type": "text/html; charset=utf-8"})

    @staticmethod
    def _file_for(path: str) -> Path | None:
        rel = path.strip("/")
        candidates = [FIXTURES / "index.html"] if not rel else [FIXTURES / f"{rel}.html", FIXTURES / rel / "index.html", FIXTURES / rel]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler), follow_redirects=True)


@pytest.fixture
def site() -> FakeSite:
    return FakeSite()


@pytest.fixture
def profile_dir(tmp_path: Path) -> Path:
    target = tmp_path / "northwind"
    init_profile(target, "Northwind Field Software", [f"{ROOT}/", f"{ROOT}/docs/", f"{ROOT}/support/"])
    return target


@pytest.fixture
def crawl(site: FakeSite, profile_dir: Path):
    def run():
        return Crawler(profile_dir, client=site.client(), now=site.now).run()

    return run
