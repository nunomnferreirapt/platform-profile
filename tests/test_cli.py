from pathlib import Path

import pytest

import platform_profile.cli as cli
from platform_profile import crawl as crawl_module

from conftest import ROOT, FakeSite


def test_cli_init_crawl_report_round_trip(tmp_path: Path, site: FakeSite, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(crawl_module, "make_client", site.client)
    monkeypatch.setattr(crawl_module, "utc_now", site.now)
    target = tmp_path / "northwind"
    assert cli.main(["init", str(target), "--name", "Northwind Field Software", "--url", f"{ROOT}/", "--url", f"{ROOT}/docs/"]) == 0
    assert "created" in capsys.readouterr().out
    assert cli.main(["crawl", str(target)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("crawl: 7 new, 0 changed, 0 unchanged, 1 failed, 0 removed")
    assert f"failed: {ROOT}/broken" in out
    (target / "profile" / "product.md").write_text("# Product\n\nOffline capture. [source: sources/index.md]\n")
    assert cli.main(["report", str(target)]) == 0
    out = capsys.readouterr().out
    assert "Profile: Northwind Field Software" in out
    assert "Seeds: 2 (docs: 1, website: 1); precedence docs > support > website" in out
    assert "Sources: 7 page(s), last crawl 2026-01-01T09:00:00+00:00" in out
    assert "Drift: no previous crawl to compare against" in out
    assert "profile/product.md: 1 citation(s), ok" in out


def test_cli_errors_cleanly_without_profile(tmp_path: Path, capsys) -> None:
    assert cli.main(["crawl", str(tmp_path / "missing")]) == 2
    assert "run `platform-profile init` first" in capsys.readouterr().err
