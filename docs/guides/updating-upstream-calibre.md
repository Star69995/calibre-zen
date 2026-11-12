# Update the upstream calibre release

calibre-zen ships calibre's release binary with this fork's Python on top. Both must come from the same calibre release.

This guide covers the source merge, installer pin, checks, and pull request. It does not bump `zen_version`, which is the separate calibre-zen release number.

## 1. Start from the current fork branch

Use a clean worktree based on the latest `zen`. In these examples, replace `9.15.0` and `9.17.0` with the old and new releases. Skipping a release is fine: merge the newest tag directly, and read the changelog of every release in between.

```sh
old_version=9.15.0
new_version=9.17.0
git fetch origin zen
git fetch upstream tag "v$new_version"
git worktree add -b "wt/upstream-$new_version" "../calibre-upstream-$new_version" origin/zen
cd "../calibre-upstream-$new_version"
git status --short
```

Merge the **release tag**, never upstream `master`. The source must match the binary that packaging downloads.

```sh
git merge --no-commit --no-ff "v$new_version"
```

## 2. Resolve the fork identity conflict

`src/calibre/constants.py` is expected to conflict. Keep `__appname__ = 'calibre-zen'`, `zen_version`, and `zen_display_name` from the fork. Take the new upstream `numeric_version`. Leave `__version__` derived from `numeric_version`.

Check any other conflicts before staging. Keep the fork's hooks and identity changes, and take upstream's new behavior around them. The rules for files under `src/calibre/` are in [the overlay README](../../src/calibre_zen/README.md). In particular, styling changes stay in `src/calibre_zen/`.

```sh
git diff --name-only --diff-filter=U
git diff "v$new_version" -- src/calibre setup/install.py
```

Upstream may change native code or build inputs. The matching release binary already contains those changes. This fork does not build them or edit upstream `.c` and `.cpp` files.

```sh
git diff --stat "v$old_version" "v$new_version" -- bypy/sources.json setup/extensions.json 'src/calibre/**/*.c' 'src/calibre/**/*.cpp'
```

`packaging/windows/wix-template.xml` and the other files under `packaging/` started as copies of upstream's `bypy/` ones, so a change there does not arrive with the merge. Diff upstream's between the two tags and decide what the fork wants:

```sh
git diff "v$old_version" "v$new_version" -- bypy/windows bypy/macos bypy/linux
```

9.17.0 added `calibre-debug --clear-caches` and `--default-programs=unregister` to the `.msi` uninstall, and `clear_user_caches()` to the Linux uninstaller (that one arrives with `linux.py`). They were not ported to the fork's template: `--default-programs=unregister` works on the `Software\calibre\...` registry keys, which a normally installed calibre shares, and an installer change needs a real install and uninstall to check.

## The overlay's audits of upstream

Two tests exist to fail when upstream adds something the overlay has to decide about. Fix them in `src/calibre_zen/`, never in the upstream file.

- `test_srvfix.Install.test_audit_is_complete`: a new `@read_api` method of `Cache` that touches `self.backend`. If its body runs SQL, add it to `SQL_READ_API` in `src/calibre_zen/host/fixes.py`; if it only reads an attribute, the prefs dict or the file system, add it to `NOT_SQL_READ_API`. Update the "Audited against calibre X" comment above them.
- `test_reader_look.TestReaderLook.test_every_calibre_colour_is_replaced`: a new `--calibre-color-*` in `DEFAULT_COLORS` of `src/pyj/book_list/theme.pyj`. Point it at the zen role it stands for in `src/calibre_zen/reader/look/css/00-variables.css`, deriving from the existing `--zen-*` variables (`color-mix()` works) rather than writing a literal. If the role is missing, add it to both the light and the dark block, and to `theme/tokens/semantic.py` if it comes from the scheme.

## 3. Pin the five installers

Use the repository's `purple-agent` GitHub account. Read each asset's name and `sha256:` digest from the upstream release.

```sh
gh auth switch --user purple-agent
gh release view "v$new_version" -R kovidgoyal/calibre --json assets --jq '.assets[] | [.name, .digest] | @tsv'
```

Update `packaging/upstream.json` with the new version, names, and digests for Linux x86_64, Linux arm64, macOS, Windows x64, and Windows portable. Keep the other fields. If upstream has removed its release assets, read the same digests from this repository's `upstream-<version>` mirror release and its `SHA256SUMS` file.

```sh
gh release view "upstream-$new_version" -R purplecandy/calibre-zen --json assets --jq '.assets[] | [.name, .digest] | @tsv'
```

The `numeric_version` in `src/calibre/constants.py` and the version in `packaging/upstream.json` must agree. Keep `zen_version` as it is unless you are also cutting a calibre-zen release.

## 4. Test with the matching calibre binary

`./zen-test` checks the installed calibre version before it starts. If your installed app is still on the old release, use the new release binary. The source worktree must be writable because calibre generates UI Python files on the first run.

On macOS, download the new image from calibre's archive, check it against the pinned digest, and run the suite from the mounted app:

```sh
runtime_dir=$(mktemp -d)
mkdir "$runtime_dir/mount"
curl -fL "https://download.calibre-ebook.com/$new_version/calibre-$new_version.dmg" -o "$runtime_dir/calibre-$new_version.dmg"
expected=$(python3 -c 'import json; print(json.load(open("packaging/upstream.json"))["assets"]["macos"]["sha256"])')
echo "$expected  $runtime_dir/calibre-$new_version.dmg" | shasum -a 256 -c -
hdiutil attach -nobrowse -readonly -quiet -mountpoint "$runtime_dir/mount" "$runtime_dir/calibre-$new_version.dmg"
debug="$runtime_dir/mount/calibre.app/Contents/MacOS/calibre-debug"
CALIBRE_ZEN_CALIBRE_DEBUG="$debug" ./zen-test
CALIBRE_DEVELOP_FROM="$PWD/src" "$debug" -c 'import compileall, os, sys; sys.exit(0 if compileall.compile_dir(os.environ["CALIBRE_DEVELOP_FROM"], quiet=1, workers=0) else 1)'
hdiutil detach -quiet "$runtime_dir/mount"
rm -r "$runtime_dir"
```

On Windows there is no mount: download `calibre-64bit-$new_version.msi` from calibre's archive into its own empty folder, check the sha256 against `packaging/upstream.json`, and unpack it without installing it. `./zen-test` then takes the `calibre-debug.exe` inside:

```sh
msiexec /a calibre-64bit-$new_version.msi /qn TARGETDIR="C:\path\to\bundle"
CALIBRE_ZEN_CALIBRE_DEBUG="C:/path/to/bundle/PFiles64/Calibre2/calibre-debug.exe" ./zen-test
```

Unpack into a short folder such as `C:\zt\b918`: a long `TARGETDIR` made `msiexec /a` exit with 1603 and unpack nothing, and Git Bash's own `//a` form exited with 67 where PowerShell's `Start-Process msiexec.exe` worked.

On a Windows machine one widget test, `test_widgets.TestToolbarOverflow.test_the_tray_is_a_surface_while_it_is_open`, may never return, on the previous release too, and takes the whole `./zen-test` run with it. Run the suite one module at a time with `timeout 600 ./zen-test <module>` (the module names are in `src/calibre_zen/tests/`) and compare module by module; the hung one still reports the 39 others.

Some tests fail on Windows before any change (see CLAUDE.md), so judge the run against a baseline: run the same suite on the previous `zen` with the previous release's binary (a second worktree), keep the `FAIL:`/`ERROR:` lines of both logs, and compare them with `comm -13`. What is only in the merge's list is yours to fix. 9.17.0 had two, the audits above, and the 18 Windows failures were identical on both sides.

Run the lint and format checks with the Ruff version pinned in `.github/workflows/zen-ci.yml`. At the time of this guide, it is 0.16.8:

```sh
uvx ruff@0.16.8 check .
uvx ruff@0.16.8 format --check --diff src/calibre_zen packaging
```

Upstream rewrites its Ruff configuration in `pyproject.toml` from time to time, and the fork lints under it. 9.17.0 turned on `unused-noqa` and `noqa-comments`, which flagged 50 comments in the fork's own code. Apply the fixes to the fork's paths only, and review the diff, which should be nothing but `noqa` comments and import order:

```sh
uvx ruff@0.16.8 check --fix src/calibre_zen packaging .calibre-zen scripts
```

`ruff format --check` on `src/calibre_zen/i18n.py` already failed before 9.17.0 (it wants Python 3.14's unparenthesised `except A, B:`); leave it unless you are changing that file.

9.18.0 turned on the `ANN` (type annotation) rules for the whole tree, 3,000 findings in the fork's paths. They are switched off for those paths in `pyproject.toml` (a row in the BUILDING.md table) rather than annotating the fork's code; a new release may add other rules, so compare the finding list with the previous `zen` under the same ruff and fix only what is new. It also made `test_tray`'s check of `run_gui`'s signature fail, because upstream annotated it: the test now takes an optional return annotation.

If `git diff --check` reports whitespace introduced by the upstream tag, inspect the file before changing it. The 9.15.0 merge had trailing whitespace in upstream's `local-agent.md`; it was left as upstream shipped it.

## 5. Open the pull request

Review the staged diff, then commit with the required co-author trailer. Push the `wt/` branch. Use `-R` with `gh` because the repository's SSH host alias can keep it from finding the right GitHub repository.

```sh
git status --short
git add -A
git diff --cached --stat
git commit -m "Merge calibre $new_version into calibre-zen" -m "Co-authored-by: Nadeem Siddique <nadeem@kibibyte.in>"
git push -u origin "wt/upstream-$new_version"
```

Fill in `.github/pull_request_template.md` with the visible changes, trade-offs, and what needs a quick check. Open the PR against `zen` and request `purplecandy` as reviewer. Do not merge it yourself.

```sh
gh pr create -R purplecandy/calibre-zen --base zen --head "wt/upstream-$new_version" --title "Update calibre to $new_version" --body-file /path/to/pr-body.md --reviewer purplecandy
```

On the PR, check `zen ci`, CodeQL, and the Linux package jobs. The Linux jobs build archives, install them, and build Flatpaks. macOS and Windows packaging runs after a push to `zen` or a release tag, so those jobs are skipped on a PR.
