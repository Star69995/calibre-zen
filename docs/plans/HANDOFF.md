# Where the work stands, and what is left

A note for picking the work up on another machine. The plans it points to stay the
source of truth; this file says where they stand today (2026-11-05) and how to get
a working setup. Delete it, or rewrite it, when it goes stale.

## Set up on a new machine

- Branch `zen`. Remotes: `origin` is `purplecandy/calibre-zen` (no write access),
  `fork` is `Star69995/calibre-zen`; push to `fork`.
- A calibre binary of the **same version as `src/calibre/constants.py`** (9.17.0).
  The installed Calibre Zen 9.15 is refused. The official calibre 9.17 works.
- Tests (Git Bash): `CALIBRE_ZEN_CALIBRE_DEBUG="<path>/calibre-debug.exe" ./zen-test`.
  On Windows set `TEMP`, `TMP` and `TMPDIR` to a short folder (e.g. `C:\zt`), and run
  one `./zen-test` at a time.
- The app (PowerShell): `$env:CALIBRE_ZEN_BUNDLE='C:\Program Files\Calibre2'; .\calibre-zen.cmd -Lang he`
  (drop `-Lang he` for English). Close an installed Calibre Zen first.
- Four tests fail on Windows on a clean checkout, so they are not yours:
  `test_double_click_default_is_ours_but_still_a_tweak`,
  `test_the_test_window_leaves_a_running_window_s_socket_alone`,
  `test_ipc_endpoints_carry_the_name`,
  `test_the_tray_reopens_the_window_the_way_it_was_started`.
  Last full run: 421 tests, only those four.
- Linux (a cloud container, 2026-11-05): calibre 9.17's `calibre-9.17.0-x86_64.txz`
  unpacked anywhere works as `CALIBRE_ZEN_CALIBRE_DEBUG`, once Qt's system
  libraries are there (`libegl1 libopengl0 libxkbcommon0 libfontconfig1
  libxcb-cursor0`). Four tests fail there on a clean checkout because there is no
  GPU for WebEngine: `test_host.HostProcess` (setUpClass) and three in
  `test_reader.TestSpareReader`. Last run: 419 tests, only those four.
- Many source files are CRLF. A script that edits them must read with `newline=''`
  and keep the endings, or a multi-line replace silently misses.
- Hebrew screenshots offscreen need `QT_QPA_FONTDIR=C:\Windows\Fonts` and a forced
  right-to-left layout. Screenshots go under `.calibre-zen\shots\<topic>\`
  (git-ignored), as `CLAUDE.md` says.

## Built so far (in `docs/plans/ui-workflow/README.md`)

U5 placement picture and correct button placement, U6 Columns picker, U7 step 1
(settings open while jobs run, clash notice), U8 jobs panel and Preferences footer. The install dialog's list of places as ticked
rows instead of solid black ones, all in view (U5 follow-up).
Hebrew translation sweep done, with the `N_()` marker for strings in tables.

## What is left

Order is the plan's "One order for both plans". Each item follows the checklist at
the end of the UI-workflow plan: off switch, `_()` plus Hebrew, test, Hebrew and
English incl. right-to-left, screenshots shown, docs ticked.

**UI workflow** (`plans/ui-workflow/README.md`)

- **U10** plugin manager (the next one; uses U5's placement picture), with **U9**
  (offer plugins at first install) and **U12** (plugin contract and template) as its
  last steps. U9 waits for the list of which of the 19 plugins to rewrite.
- **U1** selection bar. **U3** command palette with **U11** descriptions/tooltips
  (they share a source). **U4** editing the toolbar in place. **U2** the device as a
  place.
- **U0** screenshots with and without a device, Hebrew and English: still missing.
- U7 follow-ups: a survey of which settings pages clash with a job; "apply when the
  jobs finish" (undecided); the same notice for library switch and export/import;
  full-flow screenshots.
- U8 follow-ups: a spinner; the same footer in other dialogs.
- Not checked on a real screen: the jobs panel's border (the offscreen grab cannot
  show it), and the Columns panel in Hebrew itself (seen only inside the full window).

**Code quality** (`plans/code-quality/README.md`): E1 baseline and A defects, I one
settings registry, C3 one `wrap` helper, B2 one `guarded()`, D2 move the toolbar
patches from `hooks.py` to `toolbars.py`, then the rest of C and D, F, G.

**Releases** (`plans/releases/README.md`): R0 to R8, all blocked on the name and
branding decision.

## Open decisions (yours)

- Product name, and how far the branding departs from Zen.
- Where releases are hosted (`Star69995/calibre-zen` Releases, or elsewhere).
- Which of the 19 plugins to rewrite, one source per plugin, and licences.
- Should Preferences become non-modal.
- "Apply when jobs finish" in U7, and one message for library switch and
  export/import.
- After a significant visual change: whether to regenerate the `og:image`.
