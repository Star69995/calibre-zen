# calibre-zen

A fork of calibre. The fork's own code is `src/calibre_zen/` (read its
`README.md` before changing anything there); everything else under `src/` is
upstream calibre and is kept unchanged except for the places `BUILDING.md`
lists. Nothing is compiled: a package is calibre's release binary with this
fork's Python laid on top, so the source tree must be on the same calibre tag
as `packaging/upstream.json`.

## Running and testing from source

Both need a calibre binary of the **same version as `src/calibre/constants.py`**
(currently 9.15.0). The installed Calibre Zen of that version works; a newer
upstream calibre does not.

- Tests: `CALIBRE_ZEN_CALIBRE_DEBUG=<path to calibre-debug> ./zen-test [module ...] [-k name]`
  (a POSIX shell; Git Bash on Windows). Runs in English with a throwaway config.
  `./zen-test i18n` runs one module. Some tests fail on Windows before any change
  (path separators in `test_tray`, `test_update`, ...); compare against a clean
  checkout rather than assuming a failure is yours.
- The app: `./calibre-zen` is macOS only. On Windows use `.\calibre-zen.cmd`
  (wraps `calibre-zen.ps1`), which borrows the binary from
  `C:\Program Files\Calibre Zen` (or `CALIBRE_ZEN_BUNDLE`), keeps settings and a
  library in `.calibre-zen\`, and takes `-Lang he`, `-Library <dir>`, `-Fresh`,
  `-Tool calibredb ...` and `-- app args`. It refuses to start while an installed
  Calibre Zen is open: both share one single-instance lock, so the launch would
  hand over to that one and run none of this tree.
- npm scripts: `package.json` is only a front door to the launchers above (there is
  no JavaScript; `scripts/dev.mjs` picks the launcher for the OS). Extra arguments
  go after `--`. `npm start`, `start:he`, `start:fresh` (the app; `--lang <code>`
  and `--fresh` mean the same on every OS), `npm test [-- theme -k hover]`,
  `test:list`, `npm run tool -- calibredb list`, `npm run seed`, `npm run gutenberg`
  (the dev libraries). On Windows `npm test` finds Git Bash next to `git.exe` (a
  bare `bash` there is WSL's) and defaults `CALIBRE_ZEN_CALIBRE_DEBUG` to the
  installed Calibre Zen. Keep these in step when a launcher gains an option.

## Translations

Strings only this fork has are translated in `src/calibre_zen/locales/<lang>.po`
and added behind calibre's own catalog by `src/calibre_zen/i18n.py`. Write UI text
with `_()` / `ngettext()`; add the pair to a language's `.po` to ship it there.
Keep placeholders exactly; `tests/test_i18n.py` checks them. A missing
translation is not a test failure.

## Taking a new calibre release

`docs/guides/updating-upstream-calibre.md` is the procedure, and the project skill
`.claude/skills/update-upstream-calibre/` runs it (`/update-upstream-calibre`),
including the changelog report. The merge goes in its own worktree, on a release
tag. Two overlay tests fail on purpose when upstream adds something the fork must
decide about (`test_srvfix` audit, `test_reader_look` colours); the guide says how
to answer each.

## General working rules

Inlined from the maintainer's global `~/.claude/CLAUDE.md` so they travel with
the repo. Anything above this section takes precedence.

### Dev/test servers

If a task would benefit from a running dev/test server (`npm run dev`,
`wrangler dev`, etc.) — e.g. visual verification of a UI change — you may
start one yourself on your own initiative, in the background. Always close
it yourself when you're done with it (don't leave it running after your
task finishes). Don't stop a server you didn't start yourself without
asking first — it may be the user's own long-running terminal session. If
you notice orphaned/duplicate server processes you didn't start, point them
out and ask before killing them.

Exception: if the user explicitly asks you to start/stop/restart a server,
or a project's own CLAUDE.md explicitly says otherwise, follow that instead.

### Code quality

Favor reuse over duplication: before writing new code, check for an
existing function/component/util that already does this and extend or
call it instead of copying logic.

### Docs upkeep

After a structural change (new module, moved files, changed architecture
or conventions), update the project's CLAUDE.md (or create one if it
doesn't exist yet) and its README.md in the same pass, so neither drifts
from the code.

