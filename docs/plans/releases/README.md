# Releases of my own fork, with automatic updates

Started 2026-11-05. Planning only; nothing is built. The goal is to publish
Calibre Zen builds from `Star69995/calibre-zen` on GitHub, and to have installed
copies find and download them on their own, with a way to turn that off.

## What exists already

Most of the machinery is here, and was written for `purplecandy/calibre-zen`:

- **Packaging** (`BUILDING.md`, `packaging/<os>/`): a package is calibre's release
  binary with this fork's Python laid on top, so the same calibre tag as
  `packaging/upstream.json` is required.
- **A release workflow** (`.github/workflows/zen-package.yml`): runs on pushes to
  `zen` and on tags `v*`, one job per platform, and a tag push collects the
  packages into a **draft** release with a `sha256` per file and a `latest.json`
  feed. A manual run with `prerelease` publishes an "Update test" release with its
  own feed, for trying the in-app update on a real install.
- **The update check** (`update.py`): reads `latest.json` from
  `releases/latest/download/` once a day, shows "update available" in the status
  bar, and keeps calibre's plugin-update check. `CALIBRE_ZEN_UPDATE=0` gives
  calibre's own check back and `CALIBRE_ZEN_UPDATE_URL=<url>` points it at another
  feed. The feed address is a constant pointing at `purplecandy/calibre-zen`.
- **The installer** (`upgrade.py`): a dialog downloads the right package for this
  install, checks it against the feed's `sha256` and size, and installs it over
  the current one at the next quit and restart (`restart_after_quit`), with
  staging on macOS and a message when the copy is kept up to date by something
  else (a package manager).

What is **not** there: the download starts when someone clicks "Get update", not on
its own; there is no setting for how updates behave; and every address is the
other repository's.

## Decisions to make first

**1. Identity: the same product as the official build, or a separate one.**
This decides a lot, so it comes before any workflow change.

| | Same identity as the official Calibre Zen | Its own identity |
| --- | --- | --- |
| Installing | upgrades over the official install, shares its settings and library | installs beside it; separate settings, lock and socket, as the fork already is beside calibre |
| Risk | each build's updater would offer the other's releases unless the feed differs; the single-instance lock is shared, so only one can run | none of that |
| Cost | none now | a new name, bundle and installer ids, icon and Store identity (`BUILDING.md`: "fork identity ... is one string" plus what derives from it) |

The fork already derives every identity from one string
(`calibre.constants.__appname__`), so a separate identity is mostly choosing the
string and the ids; it is not a rewrite. It is your decision what the product is
called.

**Update 2026-11-05: you want some separate branding.** That points to the second
column, an identity of its own, and this plan now assumes it. How separate is
still to decide (see "Branding" below).

**2. How automatic.** A setting with three values:

- **off**: no check, no download. Nothing is sent. `CALIBRE_ZEN_UPDATE=0` is the
  hard switch and stays.
- **notify** (what exists): checks daily, says so, you click.
- **automatic**: checks daily, downloads in the background, installs on the next
  quit or restart, and says so in the status bar.

**Decided 2026-11-05: the default is automatic.** A new install checks daily,
downloads in the background and installs on the next quit or restart. It can be
turned off at any time, in Preferences and in the first-run wizard.

Because that sends a request to GitHub every day, the wizard has a step that says
so in one sentence (what is sent, and to whom) and shows the switch, on. Until a
person has passed that step, no request is made, so the default never acts before
they have been told. "Automatic" still never interrupts work: it waits for running
jobs and installs only at quit (R5). A copy kept up to date by a package manager
is left to it, as `upgrade.py` already does.

**3. Public releases.** The feed is fetched without credentials, so releases must
be public. A private repository would need a token inside every install.

## Branding

Where the product's name and look live today (checked by `grep`):

- **The display name** is one constant, `zen_display_name = 'Calibre Zen'` in
  `src/calibre/constants.py`, next to the identity string `__appname__ =
  'calibre-zen'` that config, lock and socket derive from. The identity string
  stays; only the display name is what a person reads.
- **The literal text "Calibre Zen" is spelled out in about 28 files** instead of
  using that constant: the report and consent dialogs, the status bar, the tray,
  the update and upgrade dialogs, onboarding, the Windows and Flatpak packaging, the
  issue template, the README. A rename today is a search through all of them.
- **Installer and store identity**: the Flatpak id (`io.github.purplecandy.calibre-zen`),
  `packaging/windows/msix.json`, the macOS bundle ids and URL scheme, the MSI
  product and upgrade codes.
- **The mark**: one source, `imgsrc/calibre.svg`, from which the `.icns`, `.png`,
  the `.ico` and the Store logos are all produced.
- **The look**: the colour schemes, with `zen` as the odd one out (one blue
  accent), and the welcome page recording under `onboarding/assets`.

What "a bit separate" can mean, smallest first. Pick the level; each includes the
ones before it:

| level | what changes |
| --- | --- |
| **1. Name** | the display name, the window title, the installer and menu names, the update dialog and report texts |
| **2. Mark** | your own icon in every size, from one source file, and a matching splash and About |
| **3. Look** | a default colour scheme and accent of your own, and a welcome page that shows them |
| **4. Home** | your own README, release notes page, issue template and a site or page for the product |

Rules that hold at any level:

- **Credit stays.** About and the README say what it is built on: calibre by Kovid
  Goyal, and Calibre Zen by its maintainer. The licence notices stay.
- **No confusion with the originals.** The name and mark must not suggest that
  this is calibre itself or the official Calibre Zen, and the update feed must be
  yours, so the two never offer each other's releases.
- **One place for the brand.** A small module declares the display name, the short
  name, the repository, releases and issues addresses and the installer ids, and
  every user-visible string reads from it. That is code-quality **I6**; it is done
  before the rename, so the rename is one edit and not a search, and a test
  fails when a literal brand name appears outside it.

OG image rule from `CLAUDE.md`: a change of name, mark or look is a significant
visual change, so the Open Graph preview image is regenerated, with your approval,
when this lands.

## Proposed

| | What | Notes |
| --- | --- | --- |
| R1 | **Releases from your fork.** Enable Actions on `Star69995/calibre-zen`, run `zen-package.yml` on a tag, check the draft release it makes, and publish it. | Needs nothing from `purplecandy`. The macOS signing secrets are optional and the job is gated on them, so without them the macOS build is unsigned. |
| R2 | **Addresses from settings.** `FEED_URL`, `RELEASES_URL` and `NOTES_URL` come from the settings registry (code-quality **I**), defaulting to your repository, with the existing environment override. | One place to change if the repository ever moves. |
| R3 | **The update mode setting** (off, notify, automatic; **automatic is the default**) in Preferences, in the first-run wizard, and shown in the status bar. | Reads the registry. Replaces the per-user choice that is only an environment variable today. |
| R4 | **Download in the background, as a job.** The download is a job in the job manager, so it appears in the status-bar jobs segment (U8) with a progress bar and a cancel button. | Reuses `upgrade.download`, which already verifies the `sha256` and size. |
| R5 | **Install only when it is safe.** Never while jobs run (it waits, and says "update ready, will install when jobs finish"). Applied on the next quit, as now. The previous version is kept until the new one has started once. | The rollback is new; the staging and the restart hook exist. |
| R6 | **Channels.** Stable, and pre-release for the "Update test" kind of release. | `zen-package.yml` already has the pre-release input. |
| R7 | **Release notes** link to your own release page, not `calibrezen.com`. | One constant. |
| R0 | **Brand and identity first.** The brand module (code-quality **I6**), then the chosen level above, then the installer and store ids. | Before R1, so the first release already carries the right name and ids; a rename after people installed means a migration. |
| R8 | **A releasing guide**, `docs/guides/releasing.md`: how to cut a release, and how to merge an upstream calibre tag first (the `update-upstream-calibre` skill already does that part). | `CLAUDE.md` points to it. |

## Things to check, not assume

- **Where the build downloads calibre's installers from.** `upstream.json` names
  `purplecandy/calibre-zen` as the mirror of upstream's installers, then the
  upstream archive, then GitHub. Your builds work without the mirror, but it is a
  dependency on someone else's repository; your own fork can run
  `zen-upstream-mirror.yml` and name itself.
- **Signing.** macOS builds are signed and notarized only with secrets you would
  have to supply (an Apple Developer ID); the Windows `.msi` and installer are
  unsigned, so SmartScreen warns on first run. An update must not bypass the
  system's trust checks, so the macOS staging that already exists stays. Whether
  to pay for signing is a later decision.
- **The trust model.** An automatic update means whoever can push a tag to your
  repository can put code on every installed copy. Turn on two-factor sign-in,
  protect the `zen` branch and the `v*` tags, and consider signed tags. The
  `sha256` in the feed guards against a bad download, not against a bad release.
- **Fork-of-a-fork.** `purplecandy` can change `zen-package.yml` and the
  packaging. Merge from `origin` deliberately, as the guide for upstream calibre
  does, so a change there never publishes something you did not look at.

## Order

1. Decide identity and the branding level. **R0** follows; nothing else is renamed before it.
2. **R1** can happen first and alone: a tagged release from your fork, installed
   by hand, shows the pipeline works. It needs no code.
3. After the settings registry (code-quality **I**): **R2** and **R3**.
4. After U8 (job status in the status bar): **R4**, then **R5**.
5. **R6**, **R7**, **R8** last.

Every item follows "Checking a change" in `CLAUDE.md`: Hebrew and English, and
screenshots of the dialog, the wizard step and the status bar for approval.

## Questions for you

- What should the product be called, and which branding level (1 to 4)? It will
  install beside the official Calibre Zen, since the branding is separate.
- Is GitHub Releases on a public `Star69995/calibre-zen` fine, or do you want to
  host the packages and the feed somewhere else?
