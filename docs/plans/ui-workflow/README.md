# UI workflow: one toolbar, actions where you need them, the device as a place

Started 2026-11-05. The goal is an interface that is clear, graphic and intuitive:
fewer buttons that do nothing, fewer places to look for an action, and a device
that is something you can see rather than a toolbar swap. This plan also says in
what order it runs against [the code-quality clean-up](../code-quality/README.md),
because the two touch the same files.

Every item below is done only when it meets the checklist at the end, which comes
from "Checking a change" in `CLAUDE.md`: Hebrew and English, and screenshots for
approval.

## What exists

**U0. One main toolbar. Built, not committed, screenshots pending.**
The toolbar a connected device shows is the main toolbar plus what a device adds
(Send to device, the Location manager), put in before the application's own run
at the far end. A plugin can say where its button goes by default with
`default_add_to`, and the install dialog ticks exactly that. Code and tests are in
`src/calibre_zen/toolbars.py`, `tests/test_toolbars.py` and `tests/test_gui.py`;
the design is in the overlay README under "One main toolbar".
Left to do: the Hebrew and English screenshots, with and without a device, that
the new rule asks for.

## Proposed

Numbered as in the mockup shown on 2026-11-05. Each is a separate change, behind
its own `CALIBRE_ZEN_*` switch, and none needs the others to ship.

| | What | Problem it solves | Size | Touches |
| --- | --- | --- | --- | --- |
| U5 | **Plugin placement picture (built, see below).** The install dialog draws each toolbar and puts the plugin's button in it as you tick. Recommended places carry a "Recommended" label. | Ten place names and no idea how any of them looks. | small | `toolbars.py` (dialog wrap) |
| U1 | **Actions on the selection.** The toolbar keeps only what does not depend on a selection (Add, Library, Store, Preferences). Choosing books opens a bar above the list: how many, and Edit, Convert, Send, Remove. `Esc` clears it. | Ten buttons, most of them disabled, and no sign of what they act on. | medium | `centre/layout.py`, the toolbar layout default |
| U3 | **Command palette (built, see below).** `Ctrl+K` opens one box that finds actions (with the selection count and the shortcut), settings and books. Plugin actions appear because they are already registered. | Actions hidden in secondary menus. | medium | a new module; reads `gui.iactions` |
| U4 | **Edit the toolbar in place.** "Customize" turns the live toolbar into an editor: drag to move, a cross to remove, a tray of what can be added, and the "added when a device is connected" group shown beside the rest. | Moving one button means Preferences, the right list and the arrow keys. | large | a new module; Preferences stays as the fallback |
| U2 | **The device as a place.** The sidebar lists the device with a free-space bar, the list gets an "On device" column, selected books offer "Send to Kindle", and books can be dragged onto the device. | After connecting there is no picture of what is on the reader or how much room is left. | large | `status/`, `filters/`, calibre's Location manager |

Two more, added 2026-11-05 from how the program feels to use. They are not in
the mockup yet.

| | What | Problem it solves | Size | Touches |
| --- | --- | --- | --- | --- |
| U6 | **Easy column editing (built, see below).** A "Columns" button on the centre toolbar, beside the Grid/Table switcher and shown for the table. It opens a popover: every column with a switch, drag handles to reorder, a search box for libraries with many custom columns, "Add column" and "Reset". | Today the only way is to right-click a column header, then Hide or Show column one at a time from a submenu (`gui2/library/views.py:735-757`). Nothing on screen says it exists, and reordering is dragging headers blind. | medium | `centre/` |
| U7 | **Open anything while jobs run (first step built, see below), and be told only when a change would clash.** Preferences and the other windows open while a conversion, an add or a device job is running. Only a change that would really interfere with a running job is held back, with the reason and a way forward. | calibre refuses at the door: `PreferencesAction.do_config` shows "Cannot configure while there are running jobs" (`gui2/actions/preferences.py:93-96`) even to look at a page or change a colour, and the dialog is application-modal. | small to start, then a survey | a wrap of `do_config`, a per-page rule |

**U6, built 2026-11-05** (`centre/columns.py`, overlay README "Choosing columns"). A Columns
button beside the Grid/Table switcher opens a popup: a tick per column, search, arrows to move,
Add column (disabled with the reason when a restart is owed) and Reset, all through calibre's own
handlers. Arrows, not drag handles, because a drag inside a popup is lost when the pointer leaves
it; a drag-and-drop version would need a dialog or a side panel. Left over: a switch look for the
ticks. Screenshots: `.calibre-zen\shots\columns\`.

**U6, what is known.** The centre pane's Details column is the `title` column
taken over, with `authors` and `series` hidden because they now live inside it
(overlay README, "The centre pane"). The picker has to show that as one thing, not
offer three switches that do nothing visible. The arrangement is already kept as a
state dict handed to calibre's `apply_state` under a key of our own, so the picker
reads and writes the same dict and adds no preference. Custom columns need
"Add column", which calibre already offers through `CreateNewCustomColumn`; it can
require a restart, and the picker has to say so before the click, as calibre's
menu does by greying the entry.

**U3, built 2026-11-07** (`finder/`, overlay README "Finding an action or a setting"). Two
boxes. **Find an action**: a built-in button at the far end of the main toolbar and `Ctrl+K`, a
popup that finds every action and menu item in `gui.iactions` (and Preferences' pages, its menu),
with its menu, its key and greyed when it cannot run; choosing runs it. **Search settings**: a box
in Preferences' title bar that finds a setting by the words on its page and opens it, with its tab
or list panel chosen, scrolled to and marked. Both find a translated label by its English too.
Left over from the item: the selection count beside an action, and books in the same box; a hint
of the key on the button's tooltip (U11). Screenshots: `.calibre-zen\shots\finder\`.

**U7, built so far (2026-11-05, `busy.py`).** Preferences opens while jobs run, and
a changed page that clashes is held back at Save with a notice naming the reason and
the running jobs; the Plugins page and any page that restarts the program clash.
Still to do from this item: the survey that settles the table, a clearer way forward
than "Back to the page" (apply the rest, apply when the jobs finish, which you have
not yet answered), the same message for changing library and export/import, and
Hebrew and English screenshots of the whole flow (the notice itself was shown).

**U7, the rule.** Open first, object only when it matters. This is the principle
for every guard of this kind, not only Preferences: a window opens and works
while jobs run; the program says "not right now" at the moment a change would
really clash with a running job, says why, and says what can be done instead.

How it fits calibre, so nothing upstream is edited:

- **Opening.** A wrap of `PreferencesAction.do_config` skips the
  `has_jobs()` refusal (`gui2/actions/preferences.py:93`). Jobs run in worker
  processes with their options taken when they were queued, so most changes
  cannot reach a running job at all.
- **Objecting.** Each page's `commit()` already has a way to say no:
  `raise AbortCommit` (`gui2/preferences/__init__.py:38`), which `Preferences.accept`
  catches (`preferences/main.py:535`) and answers by leaving the user on the page
  with their edits intact. Nothing is lost by being told no. The wrap of
  `Preferences.commit` asks a small table, "does this page clash with a running
  job?", and when it does, shows a message inside the dialog, in the user's words:
  which page, which job (name and progress, from the job manager), and the
  choices: **apply the other changes**, **apply when the job finishes**, or
  **discard**. It is not the error pop-up calibre uses today.
- **The table** has an entry per page and is data, not code, so changing a rule is
  one line, with a reason beside it. Starting guess, to be confirmed by the survey:
  looks, toolbars, search, shortcuts, fonts and most conversion defaults are safe;
  anything that restarts the program (`restart_critical`, or a commit that returns
  true), the plugins page, and the pages whose values a running save or send job
  reads while it runs are held back.
- **A restart** does not refuse; it goes through the question calibre already asks
  when quitting with jobs running (`ui.py:1408`), so the user decides.
- **Kept as calibre has them.** Changing library (`choose_library.py:873`) and
  export/import (`choose_library.py:436`) still refuse, because a job belongs to
  its library. They get the same kind of message, with the job named, at the
  click, instead of a bare error.

The survey comes before any code, and has two parts. First, classify every
Preferences page as safe or clashing, with the reason. Second, list every action
that blocks the whole window while it runs (about a hundred `exec()` and modal
progress or wait dialogs under `gui2/actions/`) and decide for each whether it
should become a background job shown in the Jobs button instead of a window you
have to wait for. Preferences is the first of them, not the only one.

Decided 2026-11-05: U6 is accepted as shown, with the footer buttons centred;
the variant is the small panel on the toolbar unless you say otherwise. U5, the
plugin placement picture, was liked and keeps its place at the front of the order.

Open questions for you:

- Should the Preferences dialog also stop blocking the main window? It is
  application-modal, so nothing else can be clicked while it is open. Making it
  non-modal is larger, because the pages assume nobody else is using the library.
  With the rule above it is no longer needed to solve the problem you described,
  so it can wait.
- "Apply when the job finishes" needs somewhere to hold the change until then.
  Is that wanted, or are "apply the rest" and "discard" enough?
- Is the column picker a popover on the toolbar, a side panel, or a dialog?

Three more, added the same day.

| | What | Problem it solves | Size | Touches |
| --- | --- | --- | --- | --- |
| U8 | **Job status in the status bar (built, see below).** A small segment: a spinner, "3 jobs · 64%" and a thin bar. Clicking it opens a small panel above it with each job, its percent and a cancel button, and a link to the full jobs list. Nothing stays open on its own. | With Preferences or any other dialog open, the status bar is hidden behind it and you cannot tell whether a conversion has finished. | small to medium | `status/segments.py`, a footer segment for modal dialogs |
| U9 | **Offer the plugins you already have at first install.** A step in the first-run wizard finds the plugins of the original calibre and offers them, ticked, with select all and none. They stay ordinary plugins: removable and updating. | Each new install or machine means finding, downloading and configuring them again. | small to medium | the onboarding importer (`plugin_entries`) and a wizard page |
| U10 | **A plugin manager that is not awful.** Replace the Plugins page and the "Get new plugins" dialog with one place: cards instead of a tree, grouped by what a plugin does for you, with an on/off switch, settings, and where its button appears. | calibre's page is a tree of internal plugin types ("Interface action plugins", "File type plugins") with Customize, Enable, Disable and Remove buttons beside it, and a separate window for finding new ones. | large | Preferences, `toolbars.py` (placement) |

One more, from the same day.

| | What | Problem it solves | Size | Touches |
| --- | --- | --- | --- | --- |
| U11 | **Short descriptions everywhere.** Each toolbar button says in a sentence what it does and its shortcut; a disabled one says why ("choose a book first"). The text comes from the registered action, the same source the command palette (U3) shows. Fields in Preferences and the metadata editor get a short description where calibre has one. | Most buttons and fields explain themselves only by name, and a disabled button is just grey. | small to medium | `toolbars.py` and the settings pages, with U3 |
| U12 | **Plugins that fit the interface, including your own versions.** A short contract of optional attributes a plugin can set so it behaves like part of the interface, a template plugin that shows them, and a per-plugin choice for the ones you already have: keep the original, or use your own version. | A plugin written for plain calibre knows nothing about the selection bar, the command palette, the job status, descriptions or placement, so it never fits. | small for the contract, then per plugin | `books/`, `toolbars.py`, the first-run step |

Function search is U3. It now also understands Hebrew and English names, so
"המר" and "convert" reach the same action.

**U12, what is known and proposed.** Written 2026-11-05 after you said you may
make versions of the plugins that suit the interface better.

The contract is a set of optional class attributes and conventions. Zen reads
them with `getattr`, plain calibre ignores them, so one plugin can still load in
both. None of them is new machinery; each is read by an item above:

| a plugin says | read by |
| --- | --- |
| `default_add_to`, the places its button starts in (built) | U5, U10 |
| a one-line description and a shortcut, the same text as its tooltip | U11, U3 |
| search words, in Hebrew and English, for the command palette | U3 |
| that it acts on the selection, and what to tell the user when nothing is selected | U1, U11 |
| progress and a name through calibre's job manager, not its own window | U8 |
| a settings entry, so the card's "Settings" button has something to open | U10 |
| strings through `_()`, with its own Hebrew `.po` when it ships one | the Checking-a-change rule |

A **template plugin** is one small folder in the repo that uses all of it and has a
test, so a new plugin is a copy of it. That is standard rule 7 (add a thing in
one place) applied to plugins.

For each plugin you already have there are three choices, recorded in the
survey: **keep the original** (offered at first install, as decided), **your own
version** (built in, replacing the original by name), or **drop it**. The
`books/` pattern already does the replacing: a plugin of the same name that
someone installed is dropped when the built-in registers. The first-run step reads
the same list, so it shows "replaced by Zen's version" instead of offering the
original twice.

Two things to settle before anything is built:

- **One source per plugin.** `books/` and the plugins repo (`books\`, outside this
  repository) today hold the same code twice (`cleanup.py`, `epub.py`/`main.py`,
  `actions.py`/`ui.py`), and a rule changed in one has to be changed in the other,
  which is the duplication the code standard rules out. Either the repository here
  is the only source and the plain-calibre zip is built from it, or the plain-calibre
  copies are retired. This is your decision.
- **Licences.** A version written from scratch is yours to license. One derived from
  an original keeps that plugin's licence and credit, and the survey records each
  licence first. Nothing is copied before it is checked.

Which of the plugins would you rewrite, and which are fine as they are? That list
is the input to the survey.

**U5, built 2026-11-05** (`placement.py`, `toolbars.py`; overlay README, "Where a plugin's
button goes"). The install dialog draws each ticked place as a bar or a short menu with the
new button picked out, and labels the places the plugin asked for "Recommended". It also
fixes where an install puts a button on the main toolbar (before Help and Preferences, not
after). Left over: the same picture on the plugin's card in U10, and the menus' picture
shows only the last few entries. Screenshots: `.calibre-zen\shots\placement\`.

**U8, built 2026-11-05.** The segment opens a popup with a row per job (name, thin
bar, percent, Stop) and a last line that opens calibre's Jobs window, and the same
segment sits in Preferences' button row (`status/jobs_panel.py`, `status/footer.py`;
overlay README, "The status bar"). Left over: the spinner, and the footer in dialogs
other than Preferences (the helper `add_jobs_strip` takes any dialog whose last row
is its button row). Hebrew and English screenshots are in
`.calibre-zen\shots\jobs\`.

**U9, what is known.** The plugins folder of your original calibre
(`%APPDATA%\calibre\plugins`) holds these, by file name only:

- Action Chains, CalibreSpy, Consolidate All Library Metadata, Count Pages,
  DOC Input, Extract ISBN, Fantastic Fiction, Find Duplicates, Goodreads (the
  metadata source), Goodreads More Tags, Goodreads Sync, Hyphenate This!, ISFDB3,
  Job Spy, Modern Theme, Reformat plugin, SF-Leihbuch, Search The Internet,
  Wikidata gui.
- Goodreads Updater and Book Cleanup are already built in (`books/`), so they are
  left out.
- The `.json` files beside them are each plugin's settings, and a few folders
  (`job_spy`, `calibrespy_cli`, `worddumb-*`) are libraries those plugins brought
  with them.

**Decided 2026-11-05: offer, do not embed.** The plugins are offered in the first
installation, ticked, and installed as ordinary plugins. That is the "provisioned"
route: nothing of theirs is copied into the fork's source, they can be removed and
they keep updating from their authors, and the question of each plugin's licence
only arises if a plugin is ever shipped inside a public build. The two that are
already built in (`books/`) stay as they are.

A finding from the folder: three of the entries (Action Chains, CalibreSpy,
Consolidate All Library Metadata) are only the plugin's settings file, with no
plugin beside it. The step lists them separately, says so, and offers to look them
up in Discover instead of failing to install them.

The survey, before any code, records for each plugin: its type (button, metadata
source, file type, Preferences page), size, any libraries it needs, and whether it
still works on this calibre version, so the step can warn about one that does not. The
existing importer already brings a plugins folder across as it is
(`onboarding/importer.py`, `plugin_entries`); U9 is the step beyond it, for
someone who has never run the original.

**U10, what is known and proposed.**

- **Cards, grouped by what they do for you**: Buttons, Metadata sources, Formats,
  Appearance, Other. calibre's internal plugin types are not shown.
- **Each card has**: name, one line of what it does, version, author, an on/off
  switch, a settings button when it has any, "needs a restart" said in words, and
  an update badge.
- **Where it appears** is on the card, as the chips from U5, so placing a plugin is
  not a separate trip to Toolbars & menus. A plugin's `default_add_to` is the
  starting point.
- **One place to find new ones**: "Discover" is a tab on the same page with search
  and the same cards, not a second window.
- **Where it came from** is shown: built in, bundled, or installed by you.
- Preferences keeps calibre's page as a fallback behind a link, so nothing that a
  plugin author relies on disappears.

The mockup is in the proposals page (sections 9 and 10), with the same components as
the others. The plugin manager is the interface you most want changed, so it is
scheduled right after U5, whose placement picker its cards use.

Design notes that carry across items:

- U1 decides which buttons stay on the toolbar, so U4 (the editor) is worth doing
  after it, and U2's "Send" goes into the bar U1 creates.
- U5 and U1 both change what a plugin's default placement means. Keep
  `default_add_to` as the one declaration, and let U1 add `'selection'` as a
  location only if a plugin needs it.
- Block late, explain, offer a way forward: a guard sits at the moment of
  conflict, not at the door, and says which job is in the way (U7 is the first;
  the same applies to anything else that refuses today).
- Nothing here edits an upstream file. Everything is a wrap from outside, as the
  overlay README requires.

## One order for both plans

The code-quality plan changes how the overlay is wired; this plan adds to it. New
UI code should be written against the shared helpers, not against the copies the
clean-up is about to remove, so the helpers come first. A refactor and a feature
never share a commit.

| Phase | Do | Why here |
| --- | --- | --- |
| 0. Baseline | Code-quality **E1** (Windows tests green) and **A** (defects). Record a clean baseline run. | Every later step is verified against it, and some of the tests fail on Windows before any change. |
| 1. Shared helpers | **I** (one settings registry, which contains B1), **C3** one `wrap` helper (which closes A2), **B2** one `guarded()`, and the plugin contract of **U12** written down (a document, no code), so the items that read it are built to it. | Each new UI item needs a setting, an off switch, a method wrap and fail-soft errors. Written once, they are used by U5, U7, U6, U1, U3 from the start. |
| 2. Toolbar home | **D2**: the toolbar patches in `hooks.py` move to `toolbars.py`, and `onboarding/importer.py` stops importing `hooks` upward. Then sign off **U0** (screenshots), build **U5**, and start **U10** (the plugin manager, which uses U5's placement picture) with **U9** (plugins offered at first install) and the per-plugin choices of **U12** as its last steps. | U0, U5, U1 and U4 all live in `toolbars.py`. Moving the old toolbar code there first means they land in one place. |
| 3. Daily use | **U7** (open anything while jobs run, after its survey) together with **U8** (the progress card, so you can see what is running while a settings window is open), **U6** (columns), **U1**, then **U3** together with **U11** (descriptions, which share its source). In parallel, any time: code-quality **F** (bring `books/` in line and document it) and **G** (docs). | U7 and U6 are the two annoyances you named, and both are small next to U1. U6 lives in `centre/`, so it should come after the centre's duplication is cleaned (C1, C4, C6). U3 needs nothing from U1 and can swap places with it. F and G touch different files. |
| 4. Larger work | the rest of **U10** if it is not done, **U4**, **U2**, then the rest of **C** and **D**. | The biggest diffs, and both need U1's decisions about what stays on the toolbar. D (splits) last, as the clean-up plan already says. |

Files both plans touch, so two people do not step on each other: `toolbars.py`
(D2, C3, F; U0, U5, U4), `hooks.py` (D2, B1, C3), `centre/layout.py` (C6, C7; U1),
`centre/` (C1, C4, C6, D4; U6), `status/` and `filters/` (C1, C6, G; U2),
`locales/he.po` and the settings registry (every item).

## The checklist for each item

1. A `CALIBRE_ZEN_<NAME>=0` switch that gives calibre's own behaviour back,
   declared in the settings registry (code-quality **I**), not parsed inline.
2. Text through `_()`, and the Hebrew in `locales/he.po`.
3. A test, and the existing suite compared with the baseline.
4. Checked in **Hebrew and English**, including the right-to-left layout:
   mirrored order, direction arrows, alignment, truncation, mixed-direction text.
5. **Screenshots for approval**, Hebrew and English, light and dark when the look
   changed. Nothing is called finished before they have been shown.
6. The overlay README and `CLAUDE.md` updated in the same pass, and this file
   ticked or the item removed.

When an item is finished, delete it from here so the file stays a list of what
remains.
