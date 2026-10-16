"""Profile folder layout and the profile.yaml model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

DEFAULT_PRECEDENCE: tuple[str, ...] = ("docs", "support", "website")
KINDS: tuple[str, ...] = DEFAULT_PRECEDENCE

PROFILE_HEADER = """\
# platform-profile configuration.
# seeds: one entry per public surface. kind is one of docs, support, website.
# precedence: when sources disagree, the earlier kind wins. This is a convention
# for the agent that writes profile/ pages; the check command only warns on it.
"""


@dataclass(frozen=True)
class Layout:
    """Paths inside a profile folder."""

    root: Path

    @property
    def profile_yaml(self) -> Path:
        return self.root / "profile.yaml"

    @property
    def sources_dir(self) -> Path:
        return self.root / "sources"

    @property
    def profile_dir(self) -> Path:
        return self.root / "profile"

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def manifest_prev(self) -> Path:
        return self.root / "manifest.prev.json"

    @property
    def prev_dir(self) -> Path:
        """Previous text of pages that changed or disappeared in the last crawl."""
        return self.root / ".prev"

    def exists(self) -> bool:
        return self.profile_yaml.is_file()


@dataclass
class Seed:
    url: str
    kind: str = "website"


@dataclass
class CrawlRules:
    same_domain_only: bool = True
    max_pages: int = 50
    max_depth: int = 2
    respect_robots: bool = True


@dataclass
class Profile:
    name: str
    seeds: list[Seed] = field(default_factory=list)
    precedence: list[str] = field(default_factory=lambda: list(DEFAULT_PRECEDENCE))
    crawl: CrawlRules = field(default_factory=CrawlRules)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "seeds": [asdict(seed) for seed in self.seeds],
            "precedence": list(self.precedence),
            "crawl": asdict(self.crawl),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Profile:
        seeds = [Seed(url=str(s["url"]), kind=str(s.get("kind", "website"))) for s in data.get("seeds", [])]
        crawl = CrawlRules(**{k: v for k, v in data.get("crawl", {}).items() if k in CrawlRules.__dataclass_fields__})
        return cls(
            name=str(data.get("name", "")),
            seeds=seeds,
            precedence=[str(k) for k in data.get("precedence", DEFAULT_PRECEDENCE)],
            crawl=crawl,
        )

    @classmethod
    def load(cls, profile_dir: Path) -> Profile:
        layout = Layout(profile_dir)
        if not layout.exists():
            raise FileNotFoundError(f"no profile.yaml in {profile_dir}; run `platform-profile init` first")
        data = yaml.safe_load(layout.profile_yaml.read_text(encoding="utf-8")) or {}
        return cls.from_dict(data)

    def save(self, profile_dir: Path) -> None:
        body = yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)
        Layout(profile_dir).profile_yaml.write_text(PROFILE_HEADER + body, encoding="utf-8")

    @property
    def lowest_kind(self) -> str:
        return self.precedence[-1] if self.precedence else "website"


def guess_kind(url: str) -> str:
    """Guess a seed kind from its host and path. The user can edit profile.yaml afterwards."""
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.lower()
    if host.startswith(("docs.", "developer.", "developers.", "api.")) or any(
        token in path for token in ("/docs", "/documentation", "/developer", "/api")
    ):
        return "docs"
    if host.startswith(("support.", "help.", "status.")) or any(
        token in path for token in ("/support", "/help", "/faq", "/knowledge")
    ):
        return "support"
    return "website"


def init_profile(profile_dir: Path, name: str, urls: list[str]) -> Profile:
    """Create a new profile folder. Fails if one already exists."""
    layout = Layout(profile_dir)
    if layout.exists():
        raise FileExistsError(f"{layout.profile_yaml} already exists")
    if not urls:
        raise ValueError("at least one --url is required")
    for url in urls:
        if urlsplit(url).scheme not in ("http", "https"):
            raise ValueError(f"seed must be an http(s) URL: {url}")
    profile = Profile(name=name, seeds=[Seed(url=url, kind=guess_kind(url)) for url in urls])
    layout.root.mkdir(parents=True, exist_ok=True)
    layout.sources_dir.mkdir(exist_ok=True)
    layout.profile_dir.mkdir(exist_ok=True)
    profile.save(profile_dir)
    from .manifest import Manifest  # local import keeps config free of manifest at module level

    Manifest().save(layout.manifest)
    return profile
