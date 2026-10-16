"""Short status of a profile folder."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .check import run_check
from .config import Layout, Profile
from .diff import compute_drift
from .manifest import Manifest


def render_report(profile_dir: Path) -> str:
    layout = Layout(profile_dir)
    profile = Profile.load(profile_dir)
    manifest = Manifest.load(layout.manifest)
    kinds = Counter(seed.kind for seed in profile.seeds)
    kind_text = ", ".join(f"{kind}: {count}" for kind, count in sorted(kinds.items())) or "none"
    lines = [
        f"Profile: {profile.name} ({layout.root})",
        f"Seeds: {len(profile.seeds)} ({kind_text}); precedence {' > '.join(profile.precedence)}",
        f"Sources: {len(manifest.pages)} page(s), last crawl {manifest.crawled_at or 'never'}",
    ]
    drift = compute_drift(profile_dir)
    if drift is None:
        lines.append("Drift: no previous crawl to compare against")
    elif drift.pending:
        lines.append(f"Drift: {drift.counts()} pending (run `platform-profile diff`)")
    else:
        lines.append("Drift: none since previous crawl")
    check = run_check(profile_dir)
    lines.append(f"Profile pages: {len(check.pages)}")
    for page in check.pages:
        state = "ok" if page.ok else f"{len(page.violations)} violation(s)"
        if page.warnings:
            state += f", {len(page.warnings)} warning(s)"
        lines.append(f"  {page.path}: {page.citations} citation(s), {state}")
    if check.pages:
        lines.append(f"Citation check: {len(check.violations)} violation(s), {len(check.warnings)} warning(s)")
    return "\n".join(lines)
