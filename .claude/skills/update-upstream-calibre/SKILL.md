---
name: update-upstream-calibre
description: Merge the latest upstream calibre release (kovidgoyal/calibre) into calibre-zen, pin its installers, verify against the matching binary, and report what is new. Use when the user asks to pull, update, sync or merge upstream/original calibre, to take a new calibre release, or what is new in calibre.
---

# Update the upstream calibre release

calibre-zen is calibre's release binary with this fork's Python on top, so the
source tree must sit on the **same release tag** as `packaging/upstream.json`.
The mechanics (merge, conflict, pin, test, PR) are written down in
[docs/guides/updating-upstream-calibre.md](../../../docs/guides/updating-upstream-calibre.md).
Read it first and follow it; this skill is the order of work around it and the
judgement it does not spell out. If a run teaches something the guide lacks, add
it to the guide, not here.

## Boundaries

- Work in a **new worktree** (`wt/upstream-<version>`), never in the user's
  checkout: it usually holds unfinished work.
- Stop after the local commit and the report. **Do not push, open a PR or merge
  into `zen` unless asked.** When asked: this machine's `gh` account has no write
  access to `purplecandy/calibre-zen`, so push to the `fork` remote and open the PR
  from there against `purplecandy/calibre-zen` base `zen` (`gh auth status` first).
- Merge a release **tag**, never upstream `master`. A fix that is on `master` only and
  the user wants early is cherry-picked (`git cherry-pick -x`) and its SHA added to
  `picked` in `upstream-sync.json`; the next release that contains it empties `picked`.
- Clean up at the end: the baseline worktree, the downloaded installer and the
  unpacked bundle (all under the scratchpad directory).

## 1. Find the release

[docs/upstream-sync.json](../../../docs/upstream-sync.json) records the newest
release of each source this fork has **pulled** from. calibre: the merged tag and
commit. Calibre Zen: the `origin/zen` commit `reviewed` through and the commits
`taken`. Read it first: it is where reading the changes starts.

```sh
git fetch upstream --tags --prune
git tag -l 'v[0-9]*' | sort -V | tail -3          # newest is the target
python -c "import json;print(json.load(open('packaging/upstream.json'))['version'])"   # where we are
```

Same version: say the fork is current and stop. Otherwise read the changelog of
**every** release after the current one: `git show v<new>:Changelog.txt`, down to
the section of the version we are on.

**Also check Calibre Zen (`origin`), every time, not only calibre.** This fork
sits on both. `git fetch origin --tags --prune`, then
`git log --no-merges zen..origin/zen` (and `git rev-list --left-right --count
origin/zen...zen`). Say which calibre release it is on (`constants.py`,
`packaging/upstream.json` at `origin/zen`: it may be behind this fork), and
separate its fixes to `src/calibre_zen/` and `packaging/` from new features such as
a whole new module. Look at the `origin/wt/*` branches that moved too: they are
work not merged yet. Report both sources together. Read `origin/zen` after the
`reviewed` commit in `upstream-sync.json`; if that is no longer an ancestor of
`origin/zen` (a force-push), say so and read from `git merge-base zen origin/zen`.

**From Calibre Zen take macOS fixes only, never its web app or website.** This
fork has its own identity and site. Never merge `origin/zen`: cherry-pick (`-x`)
the macOS commits (`packaging/macos/`, nothing else of theirs) after the calibre
merge commit, as commits of their own, then change their text to this fork's names
(bundle id `io.github.star69995.calibre-zen-margin`, `$DISPLAY_NAME`). Report
everything else of theirs as not taken, in one line.

## 2. Merge, pin, test

Follow the guide's sections 1 to 4. Points that decide the outcome:

- `git rev-list --left-right --count origin/zen...zen` tells whether local `zen`
  has commits `origin/zen` lacks. Base the worktree on local `zen` and say so.
- The only expected conflict is `src/calibre/constants.py`. Anything else is a
  fork edit (`# calibre-zen:` markers, the table in BUILDING.md) meeting new
  upstream code; look at it, do not take either side blindly.
- Compare upstream's `bypy/` and `setup/` changes between the two tags with the
  fork's `packaging/` copies. A change there does not arrive with the merge.
- Digests come from `gh release view v<new> -R kovidgoyal/calibre --json assets`.
  Replace each old digest by the new one explicitly; a blanket search and replace
  also rewrites history in the `_comment` fields.
- Get the matching binary (Windows: unpack the `.msi` with `msiexec /a`; macOS: the
  `.dmg`), check its sha256 against `upstream.json` first.
- **Judge the test run against a baseline**: the previous `zen` in a second
  worktree, run with the previous release's binary. Only failures present in the
  merge and not in the baseline are yours. When they name an overlay audit
  (`test_srvfix` audit, `test_reader_look` colours), fix it in `src/calibre_zen/` as
  the guide's "The overlay's audits of upstream" says.
- Lint with the Ruff pinned in `.github/workflows/zen-ci.yml`. `uvx` may be missing:
  `pip install --target <scratch> ruff==<pin>` works. Upstream changes its lint
  rules between releases; `ruff check --fix` on the fork's own paths only.
- Compile the tree with the new binary (the guide has the command).

Update the "(currently X)" line in CLAUDE.md. **Update
`docs/upstream-sync.json` in the same commit**: whatever the merge took, and only
that. Calibre: `pulled` (tag), `commit` (`git rev-parse v<new>^{commit}`) and
`date`, and the tag must equal `packaging/upstream.json` `version`. Calibre Zen,
when something was cherry-picked: `taken` gets those `origin/zen` commits (their
own SHAs, not the cherry-picks'), and `reviewed`, `date`, `version` (`zen_version`
there) and `calibre` (its calibre release) move to the `origin/zen` commit read up
to, even if nothing was taken. A run that only looked changes no file.
Commit on the worktree branch with the guide's trailer plus the attribution the
session gives.

## 3. Report to the user

Answer in the language the user writes in. Lead with the outcome (merged, tests,
what was needed beyond the merge, what is not done), then the new features.

For the features, from the changelogs of all releases taken:

- Group by what the user cares about, major items first, and keep it short.
  Bug fixes only when they touch something this fork styles or relies on.
- Mark what **concerns this fork**: the overlay styles (tag browser, cover grid,
  viewer, preferences, dark mode, layout), Hebrew/RTL, the content server and
  `host/`. Say whether the overlay needed a change for each.
- Say what was **not verified**: the app was run only through the test suite
  unless it was actually launched and looked at.
- List anything in upstream's packaging that was seen and deliberately not ported,
  with the reason.
