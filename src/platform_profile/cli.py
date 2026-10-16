"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .check import run_check
from .config import init_profile
from .crawl import Crawler
from .diff import compute_drift, render_drift
from .report import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="platform-profile",
        description="Crawl a company's public pages into one git-tracked knowledge profile that AI agents can cite.",
    )
    parser.add_argument("--version", action="version", version=f"platform-profile {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a profile folder")
    p_init.add_argument("profile_dir", type=Path)
    p_init.add_argument("--name", required=True, help="company name")
    p_init.add_argument("--url", action="append", default=[], metavar="URL", help="seed URL; repeat for more")

    for name, help_text in (
        ("crawl", "fetch seed URLs and same-domain links, write sources/, update manifest.json"),
        ("diff", "show what changed since the previous crawl"),
        ("check", "verify that every profile/ page cites only existing sources/ files"),
        ("report", "print a short status of the profile"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("profile_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"platform-profile: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        profile = init_profile(args.profile_dir, args.name, args.url)
        print(f"created {args.profile_dir} for {profile.name} with {len(profile.seeds)} seed(s)")
        for seed in profile.seeds:
            print(f"  {seed.kind:8} {seed.url}")
        print("edit profile.yaml to adjust kinds, precedence and crawl limits")
        return 0
    if args.command == "crawl":
        result = Crawler(args.profile_dir).run()
        print(result.summary())
        for url in result.failed:
            print(f"  failed: {url}")
        return 0
    if args.command == "diff":
        drift = compute_drift(args.profile_dir)
        if drift is None:
            print("No previous crawl to compare against. Run `platform-profile crawl` twice.")
            return 0
        print(render_drift(args.profile_dir, drift))
        return 0
    if args.command == "check":
        result = run_check(args.profile_dir)
        print(result.render())
        return 0 if result.ok else 1
    if args.command == "report":
        print(render_report(args.profile_dir))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
