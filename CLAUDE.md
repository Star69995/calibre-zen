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

## Translations

Strings only this fork has are translated in `src/calibre_zen/locales/<lang>.po`
and added behind calibre's own catalog by `src/calibre_zen/i18n.py`. Write UI text
with `_()` / `ngettext()`; add the pair to a language's `.po` to ship it there.
Keep placeholders exactly; `tests/test_i18n.py` checks them. A missing
translation is not a test failure.
