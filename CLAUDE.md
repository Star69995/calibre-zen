# Calibre Zen Margin

A fork of Calibre Zen (purplecandy/calibre-zen), itself a fork of calibre. The
product is **Calibre Zen Margin** (`zen_display_name`), app name
`calibre-zen-margin` (`__appname__`), PATH prefix `margin-` (`linux.py`), and it
must install beside both calibre and Calibre Zen: never reuse their names, the
`.msi` UpgradeCode (`zen_upgrade_code`) or their update feed. Releases, the
update feed and the website live in `zen_repo` (Star69995/calibre-zen-margin). The
code keeps the `zen`/`calibre_zen` names inside, so merges from Calibre Zen
stay small. Credit Kovid Goyal (calibre) and Nadeem Siddique (Calibre Zen)
wherever the product is described.

The fork's own code is `src/calibre_zen/` (read its
`README.md` before changing anything there); everything else under `src/` is
upstream calibre and is kept unchanged except for the places `BUILDING.md`
lists. Nothing is compiled: a package is calibre's release binary with this
fork's Python laid on top, so the source tree must be on the same calibre tag
as `packaging/upstream.json`.

## Running and testing from source

Both need a calibre binary of the **same version as `src/calibre/constants.py`**
(currently 9.17.0). The installed Calibre Zen of that version works; a newer
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
  `test:list`, `npm run tool -- calibredb list`. The dev libraries: `npm run seed` and
  `npm run gutenberg` (with `gutenberg:fetch` before it) build them, `start:seed` and
  `start:gutenberg` open them (`start --library seed|gutenberg|<dir>`; the default
  library is used whenever the flag is absent). On Windows `npm test` finds Git Bash next to `git.exe` (a
  bare `bash` there is WSL's) and defaults `CALIBRE_ZEN_CALIBRE_DEBUG` to the
  installed Calibre Zen. Keep these in step when a launcher gains an option.

## Brand and website

- The icon is drawn by `imgsrc/margin_mark.py` into `imgsrc/calibre.svg`;
  `imgsrc/render_margin_pngs.py` (run with `calibre-debug -e`) re-renders the
  PNGs. Never hand-edit the SVG.
- `site/` is the website (English at the root, Hebrew in `site/he/`), deployed
  by `.github/workflows/pages.yml`. Releases appear on it by themselves.
  Screenshots: `scripts/showcase_library.py` builds the library,
  `scripts/site-shots.sh <library>` photographs it in both languages and themes.
- A release: bump `zen_version`, push `zen`, tag `v<zen_version>` and push the
  tag to the `fork` remote; `zen-package.yml` drafts the release, which is then
  given notes and published.

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

## Checking a change

Every change a person can see is checked before it is called done, and shown.

- **Hebrew and English, always.** Run it in both (`.\calibre-zen.cmd -Lang he`,
  then without), not only the language you wrote it in. In Hebrew the whole window
  is right to left, so look for: the order of toolbar buttons, tabs, columns and
  menus mirrored; arrows and chevrons that mean "next" or "back" pointing the right
  way; alignment and padding written with logical sides (start/end, not
  left/right); text cut off in the wrong place; and mixed-direction text (file
  names, numbers, `Ctrl+K`, English plugin names inside a Hebrew line) in the
  order a reader expects. Fix the layout, not only the translation.
- **Screenshots for approval.** Take them in both languages, and in light and dark
  when the look changed, then show them with the full path of each file. Use the
  offscreen tool in the overlay README ("Screenshots without taking the machine",
  `CALIBRE_ZEN_SHOT_DIR`), not a screen grab, and keep them under
  `.calibre-zen\shots\<topic>\` (git-ignored). Show the state that changed:
  with and without a device, a menu open, a selection made. A change is not
  accepted until the screenshots have been seen, and screenshots are not
  committed unless a guide uses them (`docs/guides/design/`).
- **Tests are not a replacement.** A passing test says the object exists, not that
  it looks right. A refactor that touches UI code gets before and after
  screenshots too, which is how "behaviour did not change" is shown.
- **Plans.** The work in progress is in `docs/plans/` (index in `docs/README.md`).
  Tick or delete an item there when it is done.
- **Code standard.** New and changed code meets "The standard the code is held
  to" in `docs/plans/code-quality/README.md`: one job per function, no repeated
  logic, one declared place for every setting, no magic numbers, one way to
  record a failure, cheap on the hot path.

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

## Web UI rules (`site/`)

The website is this project's browser UI; these apply to it (not to the Qt app).

- Use `-` (hyphen), never `—` (em dash), in UI copy/text.
- Minimum text size: 12px. Layout must stay usable down to a 320px viewport width.
- Focusable fields (`input`, `textarea`, `select`) need `font-size: 16px` or larger - this overrides the 12px minimum above. Below 16px, iOS Safari zooms the page in when the field gets focus, and that zoom shifts the visual viewport, so sticky/fixed bars drift off screen and the user has to pinch back out. Never solve it with `user-scalable=no` or a permanent `maximum-scale=1` in the viewport meta: Safari ignores the former anyway, and both block pinch-zoom for everyone for the whole visit. If a field genuinely must show smaller text, add `maximum-scale=1` to the viewport meta on `focusin` and remove it on `focusout`.
- **iOS Safari's on-screen keyboard shrinks and offsets the *visual* viewport without touching the *layout* viewport, and doesn't fire `visualViewport` events continuously during its own open/close animation** - any sticky/fixed bar (header, toolbar, action bar) can drift off-screen or end up hidden behind the keyboard. This does not reproduce in a desktop browser or in the iOS Simulator's software keyboard - it needs a real device to test. Extensively tested across many real-device approaches, on a page with a *stack* of several sticky bars (not just one): the fix that looks obvious - give each bar its own `transform`/`top` that chases `window.visualViewport.offsetTop` - is fragile once there's more than one bar. It breaks in different ways depending on the exact implementation: z-index ordering between the bars becomes load-bearing and easy to get backwards (a bar with no explicit `z-index` silently paints *underneath* a sibling that has one, even if it's later in the DOM), and WebKit can glitch-repaint (a bar flickers transparent/disappears) even with a permanently-applied `transform` meant to keep it on a stable GPU layer. The approach that held up cleanly, repeatedly: don't move each bar - make the **app's own outer shell** the thing that tracks the keyboard. Give the shell `position: fixed` with its `top` and `height` bound to CSS variables kept in sync with `visualViewport.offsetTop` and `visualViewport.height` (a `resize`/`scroll` listener on `window.visualViewport`, refreshed every frame via `requestAnimationFrame` for as long as a field has focus - listeners alone leave the frame visibly lagging behind the keyboard's open/close animation). With the shell's own geometry always matching what's actually visible, everything inside it - header, sticky toolbars - can use plain normal-flow/sticky positioning with no per-element `transform` or `top` hacks at all: there's nothing to chase, so there's no overlap or stacking-order question to get wrong. Separately, and just as easy to miss: scroll the newly-focused field into view **on focus**, not only once the user starts typing - a field near the bottom of scrollable content can end up hidden under the keyboard the instant it opens, before any keystroke, and no browser does this for you automatically inside a custom scroll container.
- **A persistent bottom bar (bottom nav / tab bar) is hidden while a text field has focus on touch devices, and shown again only when the scroll container is at its very end.** With the on-screen keyboard open, a bar parked between the content and the keyboard just eats scarce visible height; at the end of the content there's nothing left below it to hide, so it comes back. Gate it on `(pointer: coarse)` (on desktop there's no keyboard, so hiding it looks like a glitch). Use *different* reveal/hide distance-from-bottom thresholds (e.g. reveal within 4px, hide beyond 96px) rather than a single toggle point: the bar's own show/hide changes the scroll container's `clientHeight` by its height, which would otherwise flip the "at bottom" check back and forth. Re-check after the keyboard's open animation settles (~350ms after `focusin`), and animate with `max-height` + `opacity`, not `display: none`. Reference: `useHideWhileTyping` in `src/components/BottomNav.tsx`.
- **Don't layer a manual "scroll the caret/focused element into view" correction on top of an auto-scroll mechanism that already exists** (a rich-text editor's own built-in scrollIntoView, or the browser's native reveal-on-focus scrolling) - **two scrollers acting on the same container in the same animation frame is what produces a visible jump/overcorrection, not a missing feature.** This surfaced as: typing in the *last* line of a scrollable editor on iOS Safari made the whole view jump to the top instead of scrolling down slightly to reveal the caret - happened only there, not mid-document, because with no more room to scroll down, the browser's own reveal-scroll escalates the gesture to an ancestor/the whole page instead of the exhausted inner container, and a second corrective `scrollBy` fighting it in the same frame is what turned that into a jump rather than a no-op. Diagnosing this kind of "two scrollers fighting" bug: put a kill switch on each of your own correction mechanisms and disable them all first - if the symptom disappears completely, your code (not the platform) is the thing to fix, and you can binary-search which mechanism and which direction (scrolling up to reveal a caret hidden under sticky top bars, vs. scrolling down to reveal one hidden under the keyboard) is the culprit by re-enabling one branch at a time. The fix that held up: don't add a second scroll call after the fact - find the hook that lets you feed the *existing* mechanism what it doesn't already know (e.g. ProseMirror's `editorProps.scrollThreshold`/`scrollMargin`, which it already applies on every content transaction) so there's still only one scroller. Concretely, for an editor with sticky top bars covering part of the scroll container: set `scrollThreshold.top`/`scrollMargin.top` to the sticky stack's covered height so the editor's own scrollIntoView already treats that height as hidden, and **leave the bottom/keyboard side at its default** - the editor and the browser already handle "caret hidden under the keyboard" correctly on their own, and adding a bottom-side correction is what reintroduces the fight. If the covered height can change (a bar that's conditionally shown, a toolbar that wraps to two lines at narrow widths), make the threshold/margin a live getter, not a value computed once - re-measure the DOM on each read rather than caching a stale number.
- Lean toward centering elements rather than just dumping them against the start edge (the right side in RTL). Empty states, page headers/intros, standalone cards, forms, modals' content, call-to-action buttons and narrow content blocks should be visually centered (in a constrained max-width column where appropriate) unless there's a clear reason for start alignment - e.g. long running text, table/list rows, or form labels inside a field group stay start-aligned for readability.
- No emoji in UI elements - use an icon library or SVG instead.
- Never use native browser dialogs (`alert()`, `confirm()`, `prompt()`) for user-facing interaction - always build a custom in-app modal component instead. Native dialogs can't be styled to match the app, don't respect the page's language/RTL direction or button-label conventions, and (`confirm`/`prompt`) block the JS thread while open.
- Every site needs Open Graph + Twitter Card meta tags in `<head>` (`og:title`, `og:description`, `og:image`, `og:url`, `og:image:width`/`height`, `og:locale` set to the site's actual content language (e.g. `he_IL`, not the visitor's), `og:image:alt` describing what's shown in the image, `twitter:card` set to `summary_large_image`), pointing at an absolute image URL. The preview image (1200x630) is a designed brand card, not a screenshot: the project's logo (from its original source file), the site name, a short tagline, on a clean background in the brand colors, readable at small sizes (e.g. a Slack/WhatsApp link preview). Generate it with a script kept in the repo (e.g. `scripts/generate-og-image.js`) so it can be regenerated from the logo instead of being edited by hand, and mention the script in the README. If the project has no logo yet, ask for one rather than inventing artwork. Keep the card's text in sync with `og:title`/`og:description`.
- **Text editors with mixed Hebrew/English (or any RTL + LTR) multi-line content: give every line its own explicit direction, and an empty line inherits the direction of the line above it.** A single `dir` on the field cannot get both languages right: `dir=rtl` flips English lines (right-aligned, trailing period jumps to the start), and `dir=auto`/`unicode-bidi: plaintext` leave a new empty line with no strong character, so after a Hebrew paragraph the caret lands on the left. An invisible RLM/LRM inserted on Return fixes the caret but then wins over what is typed next (English typed after it stays right-aligned) and pollutes the saved text - don't use it. What held up (verified in Chrome and on a real iPhone; the extra hardening below is what made it hold on iOS): build the editor as a `contenteditable` with one block (`div`) per line; on `input`, `beforeinput` (re-check in a microtask), `compositionstart/update/end`, `keyup`, `focus` and `selectionchange`, set each block's direction from its first strong character, falling back to the previous block's direction for an empty block (and to the page default for the first). Apply it as `data-dir="rtl|ltr"` plus the `dir` attribute, and enforce it in CSS with `!important` (`direction`, `text-align`, `unicode-bidi: isolate`) because **iOS Safari writes its own direction onto the block (a `dir` attribute or inline `direction`/`unicode-bidi`, sometimes on a wrapper span) when the keyboard language is switched**, which otherwise beats yours and leaves the line stuck on the old direction even after typing in the other language. On every sync, strip foreign `direction`/`unicode-bidi`/`text-align` inline styles and nested `dir` attributes, and wrap loose text nodes in their own block. Reference implementation: the `blockdir` behavior in `lab.js` of the `hebrew-caret-lab` branch of the `ios-lab` repo.
- **The same per-line direction rule in a Tiptap/ProseMirror editor: a `dir` node attribute on every paragraph/heading, recomputed in `appendTransaction`** (verified on a real iPhone with Tiptap 2.11.5 StarterKit; `dir=auto` on the editor root has the same problem as on a plain field). Add a global attribute `dir` (`default: null`, `parseHTML: el => el.getAttribute('dir')`, `renderHTML: a => a.dir ? { dir: a.dir, 'data-dir': a.dir } : {}`) on `paragraph` and `heading`, and a ProseMirror `Plugin` whose `appendTransaction` returns `null` unless a transaction has `docChanged`, then computes each top-level block's direction (first strong character of its text, else the previous block's, else the page default) and calls `tr.setNodeMarkup(pos, undefined, { ...node.attrs, dir })` only for blocks whose `dir` differs. **Only touch node types that declare the attribute (`paragraph`, `heading`)**, or `appendTransaction` never settles and loops forever. Seed the initial document with the `dir` values already computed (a plugin that only reacts to `docChanged` does not run on load). Enforce it with the same `!important` CSS on `[data-dir]` as for plain `contenteditable` (`direction`, `text-align`, `unicode-bidi: isolate`), so a direction iOS writes inline when the keyboard language switches cannot win; don't fight ProseMirror by stripping inline styles itself. Set `.ProseMirror p { margin: 0 }` if lines should behave like lines. Import `Plugin` from `@tiptap/pm/state` at the same version as the rest of Tiptap. Reference implementation: `blockDirExtension` in `lab.js` of the `hebrew-caret-lab` branch of the `ios-lab` repo (setup `tt-blockdir`).
