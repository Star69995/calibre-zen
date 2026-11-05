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
- Merge a release **tag**, never upstream `master`.
- Clean up at the end: the baseline worktree, the downloaded installer and the
  unpacked bundle (all under the scratchpad directory).

## 1. Find the release

```sh
git fetch upstream --tags --prune
git tag -l 'v[0-9]*' | sort -V | tail -3          # newest is the target
python -c "import json;print(json.load(open('packaging/upstream.json'))['version'])"   # where we are
```

Same version: say the fork is current and stop. Otherwise read the changelog of
**every** release after the current one: `git show v<new>:Changelog.txt`, down to
the section of the version we are on.

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

Update the "(currently X)" line in CLAUDE.md. Commit on the worktree branch with
the guide's trailer plus the attribution the session gives.

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
