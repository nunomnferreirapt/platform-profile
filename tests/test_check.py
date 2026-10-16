from pathlib import Path

from platform_profile.check import run_check
from platform_profile.cli import main


def write_page(profile_dir: Path, name: str, text: str) -> None:
    (profile_dir / "profile" / name).write_text(text, encoding="utf-8")


def test_check_passes_when_every_claim_cites_an_existing_source(crawl, profile_dir: Path, capsys) -> None:
    crawl()
    write_page(
        profile_dir,
        "pricing.md",
        "# Pricing\n\n[kind: pricing] Three plans, billed yearly. [source: sources/pricing.md]\n\n"
        "[kind: feature] The REST API is on Team and Enterprise. [source: sources/docs-api.md] [source: sources/pricing.md]\n",
    )
    result = run_check(profile_dir)
    assert result.ok
    assert result.pages[0].citations == 3
    assert result.warnings == ["profile/pricing.md: [kind: pricing] block cites only website sources; precedence prefers docs, support"]
    assert main(["check", str(profile_dir)]) == 0
    out = capsys.readouterr().out
    assert "profile/pricing.md: 3 citation(s), ok" in out
    assert "WARNING profile/pricing.md: [kind: pricing]" in out


def test_check_fails_on_missing_outside_and_uncited(crawl, profile_dir: Path, capsys) -> None:
    crawl()
    write_page(profile_dir, "product.md", "# Product\n\nNorthwind syncs field data. [source: sources/nope.md]\n")
    write_page(profile_dir, "positioning.md", "# Positioning\n\nBest in class, trust me.\n")
    write_page(profile_dir, "integrations.md", "# Integrations\n\nExports to GIS. [source: profile/product.md]\n\n[kind: feature] Offline capture.\n")
    result = run_check(profile_dir)
    assert not result.ok
    assert result.violations == [
        "profile/integrations.md: citation outside sources/: [source: profile/product.md]",
        "profile/integrations.md: [kind: feature] block has no citation",
        "profile/positioning.md: no citations; every profile page must cite at least one sources/ file",
        "profile/product.md: cited file missing: sources/nope.md",
    ]
    assert main(["check", str(profile_dir)]) == 1
    out = capsys.readouterr().out
    assert "VIOLATION profile/product.md: cited file missing: sources/nope.md" in out
    assert "check: 4 violation(s), 0 warning(s)" in out


def test_check_with_no_profile_pages_is_ok(profile_dir: Path, capsys) -> None:
    assert main(["check", str(profile_dir)]) == 0
    assert "No profile pages yet" in capsys.readouterr().out
