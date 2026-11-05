# Code-quality clean-up of `src/calibre_zen/`

A review of the fork's own code (about 25k lines of Python, 7k of them tests),
written down so someone else can pick it up. Nothing in it has been changed yet.

**Verdict.** The design is clean and unusually well explained: docstrings say
*why* and keep measured Qt findings, every wrap of upstream is made from outside,
idempotent, switchable and fail-soft. Nothing is structurally wrong. What is
weak is **copy-paste between modules**, a few over-long functions, inconsistent
error swallowing, magic numbers, and the newest uncommitted code (`books/`),
which does not follow the rest of the tree's style.

## How this was produced, and how far to trust it

Six reviewers each read one area in full (theme/icons/forms; centre/filters/
status/editor; reader/report; tray/update/upgrade/host; onboarding/download/
books/hooks/toolbars; tests and dev scripts), plus `ruff` with the repo's own
`pyproject.toml` config. Only the counts marked **verified** below were re-checked
by hand. Every other claim is a reviewer's reading of the code: **open the cited
place and confirm it before changing it**, and treat line numbers as approximate
(the tree has uncommitted changes and moves).

`ruff` is not a project dependency that is installed here. To rerun it:
`python -m pip install ruff`, then `ruff check src/calibre_zen`. Ignore its
`format --check` complaint about `except Exception, SystemExit:` (that is Python
3.14 syntax; calibre's bundled Python is older).

## Ground rules for whoever does this

- Read `CLAUDE.md` and `src/calibre_zen/README.md` first. Everything outside
  `src/calibre_zen/` is upstream calibre and stays untouched.
- Reuse over duplication is a standing rule of this repo, and most of this
  document is that rule applied. Check for an existing helper before adding one.
- Behaviour must not change in the refactors (sections B to D). Do them in small
  commits, one theme each, with the tests green between them.
- Tests: `npm test`, or `CALIBRE_ZEN_CALIBRE_DEBUG=<calibre-debug> ./zen-test`.
  Some tests already fail on Windows before any change (`test_tray`,
  `test_update`: see E1). Record a baseline from a clean checkout first and
  compare against it.
- After a structural change (new shared module, moved files) update
  `src/calibre_zen/README.md` and `CLAUDE.md` in the same pass.
- User-visible text goes through `_()`; keep placeholders exactly.
- Follow "Checking a change" in `CLAUDE.md`. A refactor that touches UI code is
  checked in Hebrew and English with before and after screenshots, which is how
  "behaviour did not change" is shown, and the screenshots are shown for approval.
- This plan runs alongside [the UI workflow plan](../ui-workflow/README.md), which
  has one order for both. Refactors and features never share a commit.

## The standard the code is held to

Sections A to J are findings. This section is the rule they are measured against,
and the one new code is written to, so the next review finds less. Where a rule
has a number, a tool or a test can check it; the rest are judgement, and a review
says which one a change breaks.

1. **One job per function.** A function does one thing and is named for it.
   Aim for under about 40 lines and three levels of nesting. The offenders are
   listed in D4.
2. **No repeated logic.** The second copy of a non-trivial block is extracted, not
   tolerated until a third. Check for an existing helper first, as `CLAUDE.md`
   already says. Sections B and C are this rule applied to what is there.
3. **Reusable pieces are small and general.** A helper takes what varies as
   arguments and knows nothing about its first caller. It lives in the lowest
   module that can hold it, and it has a test.
4. **Dependencies point one way.** Lower layers never import higher ones:
   `theme/` and the settings registry, then widgets and features, then `hooks.py`.
   A module with no Qt in it stays free of Qt, so the rest can use it early
   (`features.py` is the counterexample, see B1). No upward import such as
   `onboarding/importer.py` reaching into `hooks`.
5. **Settings live in one declared place** (section I). Code never parses an
   environment variable or a `gprefs` key by hand.
6. **No magic numbers or strings.** A size, a delay or a state name is a token or a
   named constant in the module that owns it (D5, D6).
7. **Change one thing in one place.** Adding a language, a colour scheme, an icon
   pack, a column or a switch is one entry in one file, as the README already
   promises for fonts and icon packs. Where it takes more, that is a finding.
8. **Failures are handled one way.** Cosmetic wraps fail soft on purpose, and the
   failure is recorded through the same helper everywhere (B2). Nothing swallows
   an exception without leaving a trace.
9. **Every wrap of upstream** is made from outside, is idempotent, can be switched
   off, and goes through the one wrap helper (C3).
10. **Comments say why.** Names say what. A counted comment ("six wraps") is wrong
    sooner or later, so say what the wraps are for (G).
11. **Cheap on the hot path.** Nothing is recomputed per paint, per keystroke or per
    row that can be cached or computed once. Measure before optimising, and keep
    what was measured next to the code, as the README does (section J).
12. **Tools enforce what they can.** `ruff` runs in CI with the repo's
    `pyproject.toml`. Complexity and length rules (function length, branches,
    arguments) are to be enabled at the thresholds above after checking what they
    flag today, so a threshold starts at the current worst case and tightens.

## A. Real defects (fix first, each is small)

| # | Where | Problem | Fix |
|---|---|---|---|
| A1 | `reader/look/__init__.py:340-372`, `reader/__init__.py:86` | `install()` wraps sheets, qt and viewer_js in their own `try/except` that only prints. `guard.run_install('reader-look', ...)` never sees the failure, so it is never recorded or offered as an install-failure report, which is the purpose stated in `report/guard.py`. | Let the exceptions propagate, or run each sub-install through `guard.run_install`. |
| A2 | `reader/look/sheets.py:230` | `wrap_window` checks the mark `zen_sheets` on the current `EbookViewer.__init__`. `look.install` runs sheets before qt, so on a second `install()` the outermost wrapper is qt's, the check fails and `attach` is wrapped twice. Breaks "install is idempotent". | Add a test that calls `install()` twice and counts wrappers, then fix with the shared wrap helper (C3). |
| A3 | `books/cleanup.py:490-508` (`style_headings`, `keep_ornaments_with_text`) | `set('style', ...)` overwrites any existing inline style. | Merge into the existing style string. Add a test with a pre-styled heading. |
| A4 | `books/actions.py:74-89` | The batch runs on the GUI thread with `QApplication.processEvents()`: the UI freezes per epub and Cancel is only checked between books. | Run on a worker (`ThreadedJob` / `gui.job_manager`, as calibre does) or a `QThread`. |
| A5 | `tray/settings.py:70-90` vs `host/autoadd.py:108-133` (and `host/main.py:86`) | `inside()` and `folder_problem()` exist twice; the tray copy has no `os.path.normcase`, so the two disagree on Windows (**verified**: `normcase` appears only in `autoadd.py`). | Tray imports `autoadd.inside` (stdlib-only at top) and keeps only its translated messages; reuse `same_path`. |
| A6 | `tests/test_books.py:221` | The `<title>` in `make_epub` contains U+FFFD characters (**verified**: the file contains one), a corrupted non-ASCII literal and an encoding trap. | Write an explicit title or `'T\u00e9st'`. |
| A7 | `report/guard.py`, `report/classify.py`, `report/__init__.py` | `guard._offered` is written and never read; `classify._CALIBRE_MARK` unused; `report.debug_state` has no callers. | Delete after confirming with `grep`. |

## B. The two repo-wide duplications (biggest payoff)

**B1. Environment switches.** The "is this switch off" parse
(`('0','false','no','off')`) is spelled out in about **15 places**
(**verified**: 15 hits for the literal or `OFF_VALUES` outside tests):
`hooks.py`, `lookfeel.py`, `update.py:68`, `tray/handoff.py:47`,
`host/fixes.py:66,152`, `report/__init__.py:52` (case-sensitive, unlike the
others), `report/devmenu.py:24`, `theme/rewrite.py:60`, `theme/appearance.py:65`,
`icons/registry.py:41`, `onboarding/__init__.py:53`, `onboarding/importer.py:78`,
`centre/grid.py`, and more. `features.from_env` and `OFF_VALUES` already exist
(`features.py:31,65`) but `features.py` imports Qt menus at the top, so Qt-free
modules avoid it.
- Move `OFF_VALUES` and `from_env` (add `env_flag(name, default=True)`) into a
  Qt-free module, make `features.py` use it, replace every copy.
- About 28 modules also repeat the same `_installed` plus `enabled()`
  boilerplate; consider one small `once` decorator.
- Watch for the differing casing and defaults between copies: unify on one
  behaviour and note it.

**B2. `traceback.print_exc()` in `except Exception`.** **Verified: 70 sites**
outside tests (centre/status/editor/filters 15, reader 12, report 5, others),
plus silent `except Exception: pass` at `centre/tiles.py:746,762`,
`centre/layout.py:226,237`, `theme/dropdowns.py:79,141,155,190`,
`theme/splits.py:98`, `theme/variants.py:36,62,96`, `theme/rewrite.py:78,153`,
`features.py:192`, `hooks.py:356-362,407-410,439-441`, `toolbars.py:122`.
`download/__init__.py:45` already has a `_safe`.
- Add one helper (a `guarded()` context manager / decorator) that prints the
  traceback when calibre's `DEBUG` is on and, for the install-time cosmetic
  wraps, records the event through `report/guard` (the guard docs call an
  upstream rename "the project's most valuable signal"; silent `pass` hides it).
- Narrow the `try` blocks while there (e.g. `theme/variants.py:35` wraps
  `icon.cacheKey()` for no reason).
- Do not blanket-replace: some swallows are deliberate fail-soft fallbacks.
  Keep the fallback, change only how the failure is recorded.

## C. Other duplication worth one shared helper

- **C1. Chrome colour cache and `text_color()`.** Three copies each:
  `centre/table.py:164,178` (`colors`/`forget_colors`), `filters/view.py:87`,
  `reader/look/qt.py:73,87`, `download/chrome.py:26`. `Chrome` already reads the
  text colour as a local at `theme/semantic.py:71`. Expose `Chrome.text`; add one
  `rewrite.cached_chrome()`; move `tinted` (`centre/preview.py:84`) into `theme/`.
- **C2. RGBA parsing of Chrome's format.** `reader/look/qt.py:70-96`,
  `reader/look/__init__.py:95-107`, `download/matches.py:240`. One helper under
  `theme/`.
- **C3. Method wrapping (`orig` / `MARK` / `__wrapped__` / `setattr`).** About 10
  hand-rolled copies: `reader/look/qt.py` (`wrap_toc`, `wrap_window`, `wrap_base`,
  `wrap_overlay`, `wrap_toc_model`), `sheets.py`, `book_header.py:211`,
  `viewer_js.py:55`, `hooks.py` (6x), `toolbars.py` (3x), `download/__init__.py:63-106`,
  `theme/splits.py:130`, `i18n.py`, `onboarding/__init__.py`. The mark string
  `'zen_reader_look'` is a literal in `qt.py:686`, `sheets.py:193` and
  `look/__init__.py:297` while `qt.py:62` defines `MARK`. One `wrap.after(cls,
  name, fn)` / `wrap.around(...)` that records the mark on the class fixes A2 too.
- **C4. Scale-to-cover-and-crop**: `centre/grid.py:127` (`fill`),
  `centre/preview.py:428` (`rounded`), `centre/table.py:372` (`paint_cover`).
- **C5. Restart-after-quit and detached spawn.** `upgrade.py:454-504` and
  `tray/handoff.py:93-135` copy `arm()`/`disarm`, the `restart_after_quit`
  rebinding with its `RuntimeError` check, and the `DETACHED_PROCESS` /
  `start_new_session` kwargs. One module with `hook_restart_after_quit(cb)` and
  `detached_kwargs()`.
- **C6. Glyph icon for a widget** is written four times (`centre/layout.py:70`,
  `status/segments.py:49`, `centre/tiles.py:477`, `editor/files.py:148`);
  re-polish at `status/segments.py:333` duplicates `theme/splits.py:79` and
  `theme/richtext.py:56`. Add `registry.apply_glyph(widget, name)`.
- **C7. Smaller ones**: `theme/rewrite.chrome()` is called from ~17 modules but
  lives in the stylesheet-rewrite module, and two places rebuild
  `(app.palette(), app.property('is_dark_theme'))` (`theme/dropdowns.py:97`,
  `surfaces.py:21`): add `semantic.live_chrome()`; `icons/registry.py:111-153`
  `icon()`/`glyph_icon()` and `icons/pack.py:42-65` `svg()`/`glyph_svg()` repeat
  their cache/read block; `rating.py:180,207,233` re-derive `metrics()`;
  `from calibre_zen.theme.tokens import components` is imported inside functions
  about 20 times though it has no Qt dependency (`centre/*` already imports it at
  the top); `onboarding/page.py:251-286` hand-writes eight forwarding overrides
  that `StepMixin` can do with `super()`; `onboarding/import_page.py` and
  `advanced_page.py` repeat `changed`/`isComplete`/`commit`/error dialog (a
  `SetupPage` base); `FONT_WEIGHT['semibold']` font building appears 9 times
  though `reader/look/qt.py:99 semibold()` exists; "clear a layout" loops in
  `download/panel.py:376,394` and `centre/preview.py:528`;
  `reader/activation.py:21` redefines `ismacos`/`iswindows`;
  the `('homebrew','flatpak','store')` tuple in `upgrade.py`; host/launch.py and
  host/endpoints.py both normalise scheme/`url_prefix`.

## D. Structure and size

- **D1. Split `upgrade.py` (925 lines).** Five concerns: channel detection,
  download, macOS staging, two embedded helper scripts, and a ~350-line Qt dialog
  built inside `_make_dialog_class()`. Move the dialog to `upgrade_dialog.py` as a
  plain module-level class (`update.py` already imports Qt lazily). Also: make
  `update._save_notified` public (upgrade calls it while update lazily imports
  upgrade); state strings become constants; one `_enter(state, primary, cancel,
  status)` helper for `set_ready`/`on_failed`/`on_not_writable`; unused `_feed`
  in `update.py:235`; rename `update.open_url` (clashes with calibre's);
  explain the matching 10-minute timeouts in the two helper scripts.
- **D2. `hooks.py` (643 lines) is a grab-bag.** Four of its patch functions are
  toolbar logic (`_patch_toolbar_layout`, `_patch_toolbar_names`,
  `_patch_toolbar_icon_size`, `TOOLBAR_KEYS`/`TOOLBAR_ADDITIONS`), and
  `toolbars.py` now exists for that; `onboarding/importer.py:411` imports
  `hooks` upward to reach them. Move them to `toolbars.py`, the icon patches to
  `icons/`. Replace the 25 `guard.run_install(...)` lines with an `_INSTALLS`
  tuple and a loop (keep the ordering comment). Its ~190-line module docstring
  duplicates the README patch table and has drifted (no `toolbars.py`, no
  `books/`): cut it to a pointer.
- **D3. `tray/keeper.py` (622 lines)** is a state string plus ~10 interacting
  flags (`settling`, `free_since`, `expect_free`, `waiting_since`, `lock_seen`,
  `busy`, `asking`, `on_stopped`, ...). The tuple `(OPENING, RESUMING,
  RESTARTING)` is spelled out at lines 210 and 329 and in `tray/menu.py:197`:
  add a `MOVING` constant, and extract the lock-grace logic into a small class.
  Line 92 re-imports `json`.
- **D4. Long functions** to split: `editor/dialog.py::do_layout` (~135 lines) and
  `editor/files.py::build` (~100, uses `cl`, `al`, `fl`, `g`, `b` names and
  `# Cover` banners), `forms/__init__.py::Group.row` (59), `dates.py::decorate`
  (67, five jobs; the Today and Clear buttons are copy-pasted),
  `download/matches.py::MatchDelegate.paint` (~100), `download/panel.py::changes`,
  `reader/look/qt.py::dress_panels` (50 lines of magic numbers) and `draw_match`
  (a 55-line copy of an upstream method), `tray/menu.py::refresh` (~50).
- **D5. Magic numbers.** `dialog.py:77` (160 vs the existing `EDITOR_COVER_W`),
  `qt.py` (`4, 8, 6, 18`, `16, 24, 32`), `rating.py` (`8, 6, 10, 0.35, 0.04,
  1.5`), `forms/__init__.py` (`6, 2, 16777215`), `tray/icon.py:80-89`,
  `keeper.py:126`, `download/panel.py:295`, `chrome.py:111`, `covers.py:116`,
  `matches.py:234`. The README requires tokens (`READER_*`, `RATING_*`, ...).
  Also move `as_mapping()` in `theme/tokens/components.py:327` to the end of the
  file, away from the token blocks.
- **D6. Private state reached across modules.** `editor/files.py:126` sets
  `dialog._zen_files_cover_slot`; `filters/panel.py:213` reads
  `self.list._model.entries`; `centre/preview.py:362` reads `view._model`;
  `Level.scroll` is set and read via `getattr` (`filters/panel.py:155,160`) but
  never declared; `report/issue.py:49,65` calls `event._qt_version` and
  `_os_context`; `report/devmenu.py:76` touches `guard._states`. Declare or add
  public accessors. `Entry.kind` and `Entry.mark` (`filters/levels.py:52,56`) are
  bare strings compared in several files: use constants.

## E. Tests and dev tooling

- **E1. Windows failures have one root cause.** `tests/test_tray.py` (about lines
  513, 578, 1005-1024) and `tests/test_update.py:32,36` assert literal POSIX
  paths such as `'/repo/.calibre-zen/bootstrap.py'` against code that runs
  `os.path.abspath` (`tray/handoff.py:73`), which yields `C:\repo\...`. Build
  expected values with the same transform (`os.path.abspath`, `Path.as_uri()`),
  use `os.path.join(self.mkdtemp(), ...)`, or assert on `os.path.basename`.
  This is the likeliest way to get the suite green on Windows.
- **E2. Shared test helpers exist but are bypassed.** `tests/test_host.py:52-66`
  `Scratch` re-implements `ZenTestCase.tmp/mkdtemp`; direct `tempfile.mkdtemp`
  in `test_host.py:241,296`, `test_reader_sheets.py:167,184`, `test_srvfix.py:100`;
  `editor_dialog` (`test_gui.py:315-337`) and `TestColumnsForm.dialog`
  (`:614-634`) are copy-pasted: one `open_zen_editor` in `base.py`.
  `test_books.py:38-42,111-115` works around calibre's 75-character library path
  limit with a class-level counter: a `short_dir` helper in `base.py`.
- **E3. Timing.** Hand-rolled `time.sleep` poll loops (`test_srvfix.py:56-62`,
  `test_host.py:648-653,719-726`) duplicate `base.wait_until`; fixed
  `process_events(100/200)` in `test_gui.py:57,64,216,296` should wait on the
  observable condition.
- **E4. Smaller.** Private-attribute poking (`test_gui.py:700,723,726`,
  `test_toolbars.py:73`): find widgets with `findChild` by object name; a
  redundant `app()` call in `test_toolbars.py:51-53`; the `lambda ... or real(...)`
  patch at `test_gui.py:506` should be `mock.patch.object(..., wraps=real)`;
  ruff: lambda assignment `test_books.py:214`, `sorted()[0]` at `:291`.
- **E5. Launchers.** The calibre version check is written three times
  (`zen-test:45`, `calibre-zen:71`, `calibre-zen.ps1:50`); the shell launcher
  silently skips recording the library when `python3` is missing while the ps1 uses
  calibre's own config code; the PowerShell flag set is repeated in
  `scripts/dev.mjs:37,50` and `calibre-zen.cmd:3`; the default
  `C:\Program Files\Calibre Zen` path is in both `dev.mjs:77` and the ps1;
  `--host`/`--headless` exist only in the shell launcher. Keep `CLAUDE.md`'s
  npm-scripts paragraph in step with any launcher change.

## F. The new `books/` code and `toolbars.py` (uncommitted)

- **Style does not match the tree.** `books/cleanup.py` and `books/epub.py` use
  80 columns, no type hints and `%` formatting (**verified**: 11 `%`-format sites,
  ruff `printf-string-formatting`); the rest of the project is 160 columns, hinted,
  f-strings. Also ruff: unsorted imports in `books/actions.py`, `books/epub.py`,
  `i18n.py:74`, `theme/popups.py:44`, `tests/test_books.py:60,73` (6 are auto-fixable
  with `ruff check --fix`).
- **`epub.py`**: `_heading_texts` yields elements, not texts; `_split_chapters`
  is a `while True` with a five-level scan that restarts after each split
  (extract `_next_unsplit_heading()`); `Options(is_ornament=None)` is mutated per
  file (line 183), contradicting its docstring; `_fingerprint` imports `etree`
  locally though `cleanup.py` imports it at the top; the whitespace-normalise
  expression appears 4-5 times (one `_norm_text(el)`); `Report.format` is
  English-only text shown in a dialog (wrap in `_()`).
- **`books/__init__.py:28,86-93`**: `_installed` is redundant, `register()` is
  already idempotent.
- **Not documented anywhere.** `books/` is absent from the module table in
  `src/calibre_zen/README.md` and from `CLAUDE.md`, and has no README of its own.
  Add it (this is also what the "Docs upkeep" rule asks).
- `toolbars.py` is clean and documented; only `toolbars.py:137` (`self.locations =
  locations`) needs a comment, and `from __future__ import annotations` appears
  only there.

## G. Documentation drift

- Stale counts in comments: `status/__init__.py:30,78` says "six wraps" (seven
  are assigned at 176-182); `centre/tiles.py:7` "Two things" lists three;
  `reader/look/qt.py:15` "Four wraps" (five or more); `reader/look/__init__.py:13`
  "One wrap" lists two; `report/__init__.py:14` "Three wraps" lists four;
  `centre/grid.py:116` "as before" with nothing before it; `centre/table.py:123`
  has a stray `# }}}`; `forms/__init__.py:236` has a stray `\n        ` inside a
  docstring.
- The layout block of `src/calibre_zen/README.md` (~lines 156-189) omits several
  modules that are described only in later prose: `tray/channel.py`, `handoff.py`,
  `locks.py`, `host/secret.py`, `reader/viewer_js.py`, `report/`, `devtools.py`,
  `theme/appearance.py`, `dropdowns.py`, `richtext.py`, `surfaces.py`,
  `features.py`, `icons/render.py`, `icons/audit.py`, `books/`.
- `devtools.py` is the screenshot tool, but `CALIBRE_ZEN_DEVTOOLS` belongs to
  `report/devmenu.py`; the names invite confusion.
- UI strings not wrapped in `_()` in `report/consent.py`, `report/preview.py`,
  `report/devmenu.py`, `status/segments.py:197` (translates a fragment
  `' on port {}'`, which cannot be translated well) and `editor/__init__.py:67`
  (`_()` on a variable).

## H. Smaller items, take opportunistically

`centre/table.py:294` `row_ends` rebuilds and sorts the visible-column list on
every cell paint; `centre/grid.py:60` redundant inner `import os`;
`centre/layout.py:145` local `grid` shadows the imported module;
`status/segments.py:220` inline `QMenu` import, `:320` repeats `self.percent =
None`; `centre/tiles.py:620,627,538` dead `AttributeError` fallback, a None check
on an always-set value, a thin `cover_band` wrapper; `rating.natural_width(w)`
never uses `w`; `draw_stars(show_empty=...)` never passed `False`;
`icons/render.py:68 icon()` unused; `icons/render.py:52` imports `PyQt6.QtSvg`
directly where `tray/icon.py` uses `qt.core`; `i18n.py` has two `global`
statements in `attach()`; `event._exception_values` re-implements the chain walk
in `classify.frames`; `status/layout_menu.py:90` and `editor/__init__.py:71` skip
the `except AttributeError, TypeError: return False` guard the other `install()`
functions use.

## I. Settings and configuration (new)

Measured on 2026-11-05 for this plan: **41** distinct `CALIBRE_ZEN_*` environment
names read across **28** modules, and **42** `gprefs` keys starting `zen_`
spread over **24**. Each is a string literal at its point of use, with its own
default and its own parsing (B1 is only the "off" switch). Nothing lists them, so
adding one, finding one, or documenting one all mean a search, and the README's
list of switches (`README.md:98-104`) already shows only some of them.

- **I1. One registry.** A Qt-free module, `settings.py`, declares every setting
  once: name, kind (switch, choice, number, text), default, where it is stored
  (environment, `gprefs`, or both, with which one wins), a one-line description,
  and the module that owns it. Typed accessors (`settings.get(CENTRE)`) replace
  the inline `os.environ.get(...)` and `gprefs['zen_...']`. B1's `env_flag` and
  `OFF_VALUES` become part of it, and the "off" parse is written once, with one
  casing rule.
- **I2. Generated, not written.** The switch list in the README and the table in
  `CLAUDE.md` are printed from the registry by a small script, and a test fails
  when the README is out of date. A setting that is read but not declared fails a
  test too (a grep for `CALIBRE_ZEN_` and `zen_` keys outside the registry).
- **I3. Defaults in one file.** The tunable numbers that are now literals in code
  (D5) go to the token modules or to the registry, grouped by area, so a person
  who wants a different delay, size or limit edits a file with a comment on each
  line, and nothing else. Keep the layers from "Tokens" in the overlay README:
  `.qss` templates name only tokens.
- **I4. Documented where it is read.** `--help` for `calibre-zen`, or a
  `settings --list` command, prints the registry, so an environment variable is
  discoverable without reading source.
- **I5. Migration is explicit.** A renamed key keeps its old name for one release,
  declared in the registry as an alias, instead of a private fallback somewhere.
- **I6. The brand in one place.** The display name already has a constant
  (`zen_display_name`), but the literal "Calibre Zen" is spelled out in about 28
  files (checked by `grep`): dialogs, the tray, update and report texts,
  onboarding, packaging, the issue template. Declare the product's display name,
  short name, repository, releases and issues addresses and installer ids once,
  have every visible string read from it, and add a test that fails when a literal
  brand name appears anywhere else. This is a prerequisite of the separate
  branding in [the releases plan](../releases/README.md).

Do I1 and I2 as one change and convert the readers module by module afterwards;
each module is a small commit that must not change behaviour (see the ground
rules), and the casing difference in `report/__init__.py:52` is called out when it
is reached.

## J. Efficiency: measure first (new)

Nothing here is a finding yet, which is the point: guesses about speed are
cheap and wrong. Before changing anything for speed, record the numbers, using the
scripts in `docs/plans/modes/measure/` where they fit.

- **Startup.** What the overlay adds to the time to the first window and to the
  memory at idle, per install in `hooks.install`. The install list is the natural
  place to time each entry (the `_INSTALLS` tuple of D2 makes that one loop).
- **Paint and scroll.** The known suspects are `centre/table.py:294 row_ends` (on
  every cell paint, H) and the per-paint colour lookups behind C1. Measure
  scrolling a library of 2,000 books, which the measure scripts can generate.
- **Cost of a refactor.** The shared helpers of B and C must not make a hot path
  slower; the same measurement before and after is the proof.
- A result that matters is written next to the code it justifies, as the README
  already does for Qt findings.

## Suggested order

This is the order for the clean-up alone. B1 is now part of I. When the UI work is going on too, use
the combined order in [the UI workflow plan](../ui-workflow/README.md#one-order-for-both-plans):
it moves B1, B2 and C3 ahead of the UI features, and D2 (toolbar code into
`toolbars.py`) ahead of the toolbar features.

1. **A** (defects), each with a test where one is cheap. A1/A2 first.
2. **I** (the settings registry, which includes B1), then **B2** (the helpers; they
   touch many files but are mechanical). **J** starts here with the baseline
   measurements, so later steps can show they did not make anything slower.
3. **E1** (get the Windows suite green, which makes every later step safer).
4. **F** (bring `books/` in line and document it), **G** (docs).
5. **C3** (shared wrap helper, closes A2 properly), then the rest of **C**.
6. **D** (splits) last, since they are the largest diffs.

When a theme is done, tick it here or delete its section so the file stays an
honest list of what remains.
