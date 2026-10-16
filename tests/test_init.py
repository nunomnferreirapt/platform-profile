from pathlib import Path

import pytest
import yaml

from platform_profile.config import Profile, guess_kind, init_profile

from conftest import ROOT


def test_init_creates_layout_and_guesses_kinds(profile_dir: Path) -> None:
    assert (profile_dir / "sources").is_dir()
    assert (profile_dir / "profile").is_dir()
    assert (profile_dir / "manifest.json").is_file()
    data = yaml.safe_load((profile_dir / "profile.yaml").read_text())
    assert data["name"] == "Northwind Field Software"
    assert data["precedence"] == ["docs", "support", "website"]
    assert data["crawl"] == {"same_domain_only": True, "max_pages": 50, "max_depth": 2, "respect_robots": True}
    kinds = {seed["url"]: seed["kind"] for seed in data["seeds"]}
    assert kinds == {f"{ROOT}/": "website", f"{ROOT}/docs/": "docs", f"{ROOT}/support/": "support"}
    assert Profile.load(profile_dir).seeds[1].kind == "docs"


def test_init_refuses_existing_profile_and_bad_urls(profile_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(FileExistsError):
        init_profile(profile_dir, "Again", [f"{ROOT}/"])
    with pytest.raises(ValueError):
        init_profile(tmp_path / "other", "Other", ["ftp://northwind.example/"])
    assert guess_kind("https://help.northwind.example/") == "support"
