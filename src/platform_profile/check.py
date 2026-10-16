"""Citation check: generated text is never evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Layout, Profile
from .sources import read_source

CITATION = re.compile(r"\[source:\s*([^\]]+?)\s*\]")
KIND_TAG = re.compile(r"\[kind:\s*(pricing|feature)\s*\]", re.IGNORECASE)
VALID_TARGET = re.compile(r"sources/[A-Za-z0-9._-]+\.md")


@dataclass
class PageHealth:
    path: str
    citations: int = 0
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass
class CheckResult:
    pages: list[PageHealth] = field(default_factory=list)

    @property
    def violations(self) -> list[str]:
        return [f"{page.path}: {msg}" for page in self.pages for msg in page.violations]

    @property
    def warnings(self) -> list[str]:
        return [f"{page.path}: {msg}" for page in self.pages for msg in page.warnings]

    @property
    def ok(self) -> bool:
        return not self.violations

    def render(self) -> str:
        lines = []
        for page in self.pages:
            state = "ok" if page.ok else f"{len(page.violations)} violation(s)"
            lines.append(f"{page.path}: {page.citations} citation(s), {state}")
        for item in self.violations:
            lines.append(f"VIOLATION {item}")
        for item in self.warnings:
            lines.append(f"WARNING {item}")
        if not self.pages:
            lines.append("No profile pages yet. Write profile/<topic>.md files that cite sources/.")
        elif self.ok:
            lines.append(f"check: {len(self.pages)} page(s) ok, {len(self.warnings)} warning(s)")
        else:
            lines.append(f"check: {len(self.violations)} violation(s), {len(self.warnings)} warning(s)")
        return "\n".join(lines)


def run_check(profile_dir: Path) -> CheckResult:
    layout = Layout(profile_dir)
    profile = Profile.load(profile_dir)
    result = CheckResult()
    kind_cache: dict[str, str] = {}
    for path in sorted(layout.profile_dir.rglob("*.md")):
        rel = path.relative_to(layout.root).as_posix()
        health = PageHealth(path=rel)
        text = path.read_text(encoding="utf-8")
        targets = CITATION.findall(text)
        health.citations = len(targets)
        if not targets:
            health.violations.append("no citations; every profile page must cite at least one sources/ file")
        for target in dict.fromkeys(targets):
            if not VALID_TARGET.fullmatch(target):
                health.violations.append(f"citation outside sources/: [source: {target}]")
            elif not (layout.root / target).is_file():
                health.violations.append(f"cited file missing: {target}")
        _check_kind_blocks(text, layout, profile, health, kind_cache)
        result.pages.append(health)
    return result


def _source_kind(layout: Layout, target: str, cache: dict[str, str]) -> str | None:
    if target in cache:
        return cache[target]
    path = layout.root / target
    if not path.is_file():
        return None
    meta, _ = read_source(path)
    kind = str(meta.get("kind", "website"))
    cache[target] = kind
    return kind


def _check_kind_blocks(text: str, layout: Layout, profile: Profile, health: PageHealth, cache: dict[str, str]) -> None:
    lowest = profile.lowest_kind
    for block in re.split(r"\n\s*\n", text):
        tag = KIND_TAG.search(block)
        if not tag:
            continue
        label = tag.group(1).lower()
        cited = [t for t in CITATION.findall(block) if VALID_TARGET.fullmatch(t)]
        if not cited:
            health.violations.append(f"[kind: {label}] block has no citation")
            continue
        kinds = {k for k in (_source_kind(layout, t, cache) for t in cited) if k}
        if kinds and kinds == {lowest}:
            preferred = ", ".join(k for k in profile.precedence if k != lowest) or "a higher-precedence kind"
            health.warnings.append(f"[kind: {label}] block cites only {lowest} sources; precedence prefers {preferred}")
