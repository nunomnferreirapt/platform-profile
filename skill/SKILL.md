---
name: platform-profile
description: Build and maintain a company's knowledge profile from its crawled public pages, citing only sources/ files, never generated text.
---

# platform-profile

Use this skill when asked to build, refresh or verify a company knowledge profile with the `platform-profile` tool. The profile folder holds `profile.yaml`, `sources/` (crawled pages, read-only for you), `profile/` (the pages you write) and `manifest.json`.

## Rules

1. `sources/` is the only evidence. Never edit files there.
2. Every statement you write in `profile/` carries a citation in this exact form: `[source: sources/<slug>.md]`. One or more per paragraph.
3. Never state anything that no cited source says. If the sources are silent, write "Not stated in public sources." instead of guessing.
4. Tag paragraphs that make a pricing claim with `[kind: pricing]` and paragraphs that make a feature claim with `[kind: feature]`. Prefer sources whose `kind` is earlier in `precedence` (default `docs`, then `support`, then `website`). When sources disagree, the earlier kind wins; say so in the paragraph and cite both.
5. Finish with `check`. Do not report done while it prints a violation.

## Steps

1. Locate the profile folder. If it does not exist, run `uv run platform-profile init <dir> --name "<Company>" --url <url> ...` and ask the user to confirm the seed kinds in `profile.yaml`.
2. Run `uv run platform-profile crawl <dir>`. Read the summary line. If pages failed, say which.
3. If a previous crawl exists, run `uv run platform-profile diff <dir>` and read the drift. Changed sources mean the profile pages that cite them must be re-read.
4. Read every file under `sources/`. The header gives url, title, fetched_at, sha256 and kind.
5. Write or update one page per topic in `profile/`: `product.md`, `pricing.md`, `integrations.md`, `support.md`, `positioning.md`. Short paragraphs, each with its citation. Skip a topic when no source covers it, and say so in the page.
6. Run `uv run platform-profile check <dir>`. Fix every violation. Read every warning and either cite a higher-precedence source or leave the warning and tell the user why.
7. Run `uv run platform-profile report <dir>` and paste its output in your summary. List the files you changed so the user can review the diff before committing.

## Example paragraph

```markdown
[kind: pricing] Three plans are offered, priced per user per month and billed yearly: Starter, Team and Enterprise. [source: sources/pricing.md]
```
