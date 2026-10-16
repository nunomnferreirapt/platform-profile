"""Drift report: what changed between the previous crawl and the current one."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

from .config import Layout
from .manifest import Entry, Manifest
from .sources import split_source


@dataclass
class Drift:
    prev_crawled_at: str | None
    crawled_at: str | None
    new: list[Entry] = field(default_factory=list)
    changed: list[tuple[Entry, Entry]] = field(default_factory=list)
    removed: list[Entry] = field(default_factory=list)

    @property
    def pending(self) -> bool:
        return bool(self.new or self.changed or self.removed)

    def counts(self) -> str:
        return f"{len(self.new)} new, {len(self.changed)} changed, {len(self.removed)} removed"


def compute_drift(profile_dir: Path) -> Drift | None:
    """Return None when there is no previous manifest to compare against."""
    layout = Layout(profile_dir)
    if not layout.manifest_prev.is_file():
        return None
    prev = Manifest.load(layout.manifest_prev)
    cur = Manifest.load(layout.manifest)
    drift = Drift(prev_crawled_at=prev.crawled_at, crawled_at=cur.crawled_at)
    for url, entry in sorted(cur.pages.items()):
        before = prev.pages.get(url)
        if before is None:
            drift.new.append(entry)
        elif before.sha256 != entry.sha256:
            drift.changed.append((before, entry))
    for url, entry in sorted(prev.pages.items()):
        if url not in cur.pages:
            drift.removed.append(entry)
    return drift


def _body(path: Path) -> str | None:
    if not path.is_file():
        return None
    _, body = split_source(path.read_text(encoding="utf-8"))
    return body


def render_drift(profile_dir: Path, drift: Drift) -> str:
    layout = Layout(profile_dir)
    lines = [
        f"Drift since {drift.prev_crawled_at or 'unknown'} (current crawl {drift.crawled_at or 'unknown'}): {drift.counts()}",
    ]
    if not drift.pending:
        lines.append("No drift.")
        return "\n".join(lines)
    if drift.new:
        lines.append("")
        lines.append("New pages:")
        lines.extend(f"  + {entry.path}  {entry.url}" for entry in drift.new)
    if drift.changed:
        lines.append("")
        lines.append("Changed pages:")
        for before, after in drift.changed:
            lines.append(f"  ~ {after.path}  {after.url}")
            old_text = _body(layout.prev_dir / Path(before.path).name)
            new_text = _body(layout.root / after.path)
            if old_text is None or new_text is None:
                lines.append("    (previous text not available; compare with git history)")
                continue
            diff = difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile=f"a/{before.path}",
                tofile=f"b/{after.path}",
                lineterm="",
            )
            lines.extend(f"    {line}" for line in diff)
    if drift.removed:
        lines.append("")
        lines.append("Removed pages:")
        lines.extend(f"  - {entry.path}  {entry.url}" for entry in drift.removed)
    return "\n".join(lines)
