from pathlib import Path

from platform_profile.cli import main
from platform_profile.diff import compute_drift, render_drift

from conftest import ROOT, FakeSite


def test_diff_without_previous_crawl(profile_dir: Path, capsys) -> None:
    assert compute_drift(profile_dir) is None
    assert main(["diff", str(profile_dir)]) == 0
    assert "No previous crawl" in capsys.readouterr().out


def test_diff_reports_new_changed_and_removed(crawl, site: FakeSite, profile_dir: Path) -> None:
    crawl()
    site.overrides["/pricing"] = "<html><head><title>Pricing</title></head><body><main><h1>Pricing</h1><p>Starter is now 39 EUR.</p></main></body></html>"
    site.overrides["/support"] = (
        "<html><head><title>Support</title></head><body><main><h1>Support</h1>"
        '<p>See <a href="/support/sla">the SLA</a>.</p></main></body></html>'
    )
    site.overrides["/support/sla"] = "<html><head><title>SLA</title></head><body><main><h1>SLA</h1><p>99.9 percent.</p></main></body></html>"
    site.overrides["/legal"] = ""
    site.clock = site.clock.replace(day=2)
    crawl()
    drift = compute_drift(profile_dir)
    assert drift is not None and drift.pending
    assert [e.url for e in drift.new] == [f"{ROOT}/support/sla"]
    assert [after.url for _, after in drift.changed] == [f"{ROOT}/pricing", f"{ROOT}/support"]
    assert drift.removed == []  # legal failed, so its last good copy is kept
    text = render_drift(profile_dir, drift)
    assert "Drift since 2026-01-01T09:00:00+00:00 (current crawl 2026-01-02T09:00:00+00:00): 1 new, 2 changed, 0 removed" in text
    assert "+ sources/support-sla.md" in text
    assert "~ sources/pricing.md" in text
    assert "-| Starter | 29 EUR | 3 |" in text
    assert "+Starter is now 39 EUR." in text
    assert "fetched_at" not in text, "front matter is not part of the drift diff"
