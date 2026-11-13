#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The fork's identity: the names and versions BUILDING.md says a package is
built from, checked before a package is built.
"""

import json
import os
import unittest


def repo_root() -> str:
    import calibre_zen

    return os.path.abspath(os.path.join(os.path.dirname(calibre_zen.__file__), '..', '..'))


def picked_upstream_fixes(root: str) -> list[str]:
    "Upstream commits cherry-picked after the pinned tag, as docs/upstream-sync.json records them."
    with open(os.path.join(root, 'docs', 'upstream-sync.json')) as f:
        return json.load(f)['calibre'].get('picked', [])


def edited_lines(diff: str) -> list[str]:
    "The lines a diff adds and removes, without its headers and positions, so two diffs of one change compare equal."
    return sorted(ln for ln in diff.splitlines() if ln[:1] in '+-' and not ln.startswith(('+++', '---')))


class TestIdentity(unittest.TestCase):
    def test_appname_is_the_fork(self):
        from calibre.constants import __appname__, zen_display_name

        self.assertEqual(__appname__, 'calibre-zen-margin')
        self.assertEqual(zen_display_name, 'Calibre Zen Margin')

    def test_zen_version_is_a_release_version(self):
        from calibre.constants import zen_version

        self.assertRegex(zen_version, r'^\d+\.\d+\.\d+$')

    def test_upstream_pin_matches_the_source(self):
        "packaging/upstream.json names the calibre this Python is for."
        pin = os.path.join(repo_root(), 'packaging', 'upstream.json')
        if not os.path.exists(pin):
            self.skipTest('not a source checkout')
        from calibre.constants import numeric_version

        with open(pin) as f:
            d = json.load(f)
        self.assertEqual(d['version'], '.'.join(map(str, numeric_version)))
        for key, asset in d['assets'].items():
            with self.subTest(asset=key):
                self.assertIn(d['version'], asset['name'])
                self.assertRegex(asset['sha256'], r'^[0-9a-f]{64}$')

    def test_ipc_endpoints_carry_the_name(self):
        "Installing beside calibre depends on these never being calibre's."
        from calibre.constants import __appname__, ismacos
        from calibre.utils.ipc import gui_socket_address, viewer_socket_address
        from calibre_zen.tests.base import endpoint_name

        for addr in (gui_socket_address(), viewer_socket_address()):
            self.assertIn(endpoint_name(), addr)
        if ismacos:
            # Only a lock file has a path: Windows locks on a mutex and Linux on an abstract socket.
            from calibre.utils.lock import singleinstance_path

            self.assertIn(__appname__, singleinstance_path('GUI'))

    def test_bare_asserts_are_not_used(self):
        "The bundle runs -OO: an assert in the overlay is a check that never runs."
        import ast

        root = os.path.join(repo_root(), 'src', 'calibre_zen')
        offenders = []
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if not f.endswith('.py'):
                    continue
                p = os.path.join(dirpath, f)
                with open(p, encoding='utf-8') as fh:
                    tree = ast.parse(fh.read(), p)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assert):
                        offenders.append(f'{os.path.relpath(p, root)}:{node.lineno}')
        self.assertEqual(offenders, [], 'assert statements in the overlay (stripped by -OO): ' + ', '.join(offenders))

    def test_upstream_files_changed_are_only_the_known_ones(self):
        """
        The rule in .claude/CLAUDE.md as a test: against the upstream tag, the
        only files that differ under src/calibre and setup/ are the hook, the
        install copy rule, the fork-identity files, and files whose whole
        change is `.setProperty('zenVariant', ...)` lines. A file that differs
        only by an upstream fix cherry-picked ahead of the next release (listed in
        docs/upstream-sync.json) is allowed too.
        """
        import subprocess

        root = repo_root()
        try:
            subprocess.run(['git', '-C', root, 'rev-parse', '--git-dir'], check=True, capture_output=True)
        except OSError, subprocess.CalledProcessError:
            self.skipTest('not a git checkout')
        with open(os.path.join(root, 'packaging', 'upstream.json')) as f:
            tag = 'v' + json.load(f)['version']
        if subprocess.run(['git', '-C', root, 'rev-parse', '-q', '--verify', tag + '^{commit}'], capture_output=True).returncode:
            self.skipTest(f'upstream tag {tag} is not fetched')

        def git(*args) -> str:
            return subprocess.run(['git', '-C', root, *args], check=True, capture_output=True, text=True).stdout

        allowed = {
            'src/calibre/gui2/__init__.py',  # the hook
            'setup/install.py',  # also copy .qss/.svg/.ttf
            'setup/__init__.py',  # the source tree's name stays 'calibre', so calibre's own CI can build it
            # fork identity, every hunk marked and listed in BUILDING.md
            'src/calibre/constants.py',
            'src/calibre/utils/ipc/__init__.py',
            'src/calibre/linux.py',
            'src/calibre/gui2/update.py',
        }
        picks = picked_upstream_fixes(root)
        if any(subprocess.run(['git', '-C', root, 'cat-file', '-e', sha + '^{commit}'], capture_output=True).returncode for sha in picks):
            self.skipTest('a cherry-picked upstream fix is not fetched')
        changed = [f for f in git('diff', '--name-only', tag, '--', 'src/calibre', 'setup').split('\n') if f]
        offenders = []
        for f in changed:
            if f in allowed:
                continue
            diff = git('diff', '--unified=0', tag, '--', f)
            upstream_fix = edited_lines(''.join(git('show', '--format=', '--unified=0', sha, '--', f) for sha in picks))
            if upstream_fix and edited_lines(diff) == upstream_fix:
                continue  # upstream's own fix, taken ahead of the next release
            added = [ln[1:].strip() for ln in diff.splitlines() if ln.startswith('+') and not ln.startswith('+++')]
            removed = [ln for ln in diff.splitlines() if ln.startswith('-') and not ln.startswith('---')]
            if removed or not added or not all("setProperty('zenVariant'" in ln for ln in added):
                offenders.append(f)
        self.assertEqual(offenders, [], 'upstream files changed for something other than identity or a variant tag: ' + ', '.join(offenders))
