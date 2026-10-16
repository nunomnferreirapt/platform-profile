import json
import os
from pathlib import Path

from platform_profile.sources import read_source

from conftest import ROOT, FakeSite


def test_crawl_writes_sources_and_manifest(crawl, site: FakeSite, profile_dir: Path) -> None:
    result = crawl()
    assert result.summary() == "crawl: 7 new, 0 changed, 0 unchanged, 1 failed, 0 removed"
    assert result.failed == [f"{ROOT}/broken"]
    written = sorted(p.name for p in (profile_dir / "sources").glob("*.md"))
    assert written == ["docs-api.md", "docs-limits.md", "docs.md", "index.md", "legal.md", "pricing.md", "support.md"]
    meta, body = read_source(profile_dir / "sources" / "pricing.md")
    assert meta["url"] == f"{ROOT}/pricing"
    assert meta["title"] == "Pricing | Northwind Field Software"
    assert meta["fetched_at"] == "2026-01-01T09:00:00+00:00"
    assert meta["kind"] == "website"
    assert len(meta["sha256"]) == 64
    assert body.startswith("# Pricing")
    manifest = json.loads((profile_dir / "manifest.json").read_text())
    assert manifest["crawled_at"] == "2026-01-01T09:00:00+00:00"
    entry = manifest["pages"][f"{ROOT}/docs/api"]
    assert entry["path"] == "sources/docs-api.md"
    assert entry["kind"] == "docs"
    assert entry["sha256"] == read_source(profile_dir / "sources" / "docs-api.md")[0]["sha256"]


def test_crawl_respects_domain_robots_depth_and_suffixes(crawl, site: FakeSite) -> None:
    crawl()
    assert "/robots.txt" in site.requests
    assert "/private/internal.html" not in site.requests, "disallowed by robots.txt"
    assert "/brochure.pdf" not in site.requests, "binary suffix is never fetched"
    assert "/northwind" not in site.requests, "the partner.example link is another domain"
    assert "/docs/limits" in site.requests, "two hops from the /docs/ seed"
    assert "/docs/deep" not in site.requests, "three hops from the nearest seed"


def test_crawl_honors_max_pages(site: FakeSite, profile_dir: Path) -> None:
    import yaml

    from platform_profile.crawl import Crawler

    data = yaml.safe_load((profile_dir / "profile.yaml").read_text())
    data["crawl"]["max_pages"] = 2
    (profile_dir / "profile.yaml").write_text(yaml.safe_dump(data))
    result = Crawler(profile_dir, client=site.client(), now=site.now).run()
    assert len(result.new) + len(result.failed) == 2


def test_second_crawl_is_incremental_and_does_not_rewrite(crawl, profile_dir: Path) -> None:
    crawl()
    pricing = profile_dir / "sources" / "pricing.md"
    old_time = 1_600_000_000
    os.utime(pricing, (old_time, old_time))
    result = crawl()
    assert len(result.new) == 0
    assert len(result.unchanged) == 7
    assert pricing.stat().st_mtime == old_time
    assert (profile_dir / "manifest.prev.json").is_file()


def test_changed_page_is_rewritten_and_previous_text_kept(crawl, site: FakeSite, profile_dir: Path) -> None:
    crawl()
    site.overrides["/pricing"] = "<html><head><title>Pricing</title></head><body><main><h1>Pricing</h1><p>Starter is now 39 EUR.</p></main></body></html>"
    site.clock = site.clock.replace(day=2)
    result = crawl()
    assert result.changed == [f"{ROOT}/pricing"]
    assert len(result.unchanged) == 6
    meta, body = read_source(profile_dir / "sources" / "pricing.md")
    assert meta["fetched_at"] == "2026-01-02T09:00:00+00:00"
    assert "39 EUR" in body
    assert "59 EUR" in (profile_dir / ".prev" / "pricing.md").read_text()


def test_removed_page_is_dropped_and_failed_page_is_kept(crawl, site: FakeSite, profile_dir: Path) -> None:
    crawl()
    site.overrides["/support"] = ""  # 404 now
    result = crawl()
    assert f"{ROOT}/support" in result.failed
    assert (profile_dir / "sources" / "support.md").is_file(), "a failed fetch keeps the last good copy"
    # Remove the link to pricing and the page itself: it is no longer reachable, so it is removed.
    site.overrides["/"] = "<html><head><title>Home</title></head><body><main><h1>Home</h1><p>Nothing linked.</p></main></body></html>"
    site.overrides["/support"] = "<html><head><title>Support</title></head><body><main><h1>Support</h1></main></body></html>"
    result = crawl()
    assert f"{ROOT}/pricing" in result.removed
    assert not (profile_dir / "sources" / "pricing.md").exists()
    assert (profile_dir / ".prev" / "pricing.md").is_file()
