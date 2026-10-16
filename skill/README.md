# Claude Code skill: platform-profile

`SKILL.md` teaches Claude Code to run the crawl, read `sources/`, write `profile/` pages with citations, and run the check before it reports done.

Install it by symlinking or copying this folder into your skills directory:

```bash
# symlink (updates with the repo)
ln -s "$(pwd)/skill" ~/.claude/skills/platform-profile

# or copy
cp -r skill ~/.claude/skills/platform-profile
```

Then, in a project that contains a profile folder, ask Claude Code to "build the knowledge profile for <Company> in <dir>". The skill expects `uv run platform-profile` to work from the repository root, so run it from a clone of this repository or point the commands at your own install.
