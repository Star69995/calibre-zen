#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Photograph the main window for the website (site/img/), offscreen.

Runs the real GUI from this tree in one process, on the offscreen platform, so
nothing appears on the screen and nothing is clicked. calibre-zen-margin has its
own lock and pipe, so this can never hand over to a running calibre or Calibre
Zen; the lock is bypassed anyway, so two runs do not wait on each other.

    scripts/site-shots.sh                      # every language and theme
    calibre-debug -e scripts/site_shots.py -- <library> <out dir> <en|he> <light|dark>

The caller sets CALIBRE_DEVELOP_FROM, a throwaway CALIBRE_CONFIG_DIRECTORY,
CALIBRE_OVERRIDE_LANG, QT_QPA_PLATFORM=offscreen and QT_QPA_FONTDIR; see
site-shots.sh. Each state below is saved as <name>.png in the out dir.
"""

import os
import sys

LIB, OUT, LANG, MODE = sys.argv[-4:]
# Logical size of the window. The caller's QT_SCALE_FACTOR makes the files sharp.
SIZE = (1600, 1000)
STARTUP_MS = 12000
SETTLE_MS = 1500

import calibre.gui2.main as M


class NoLock:
    def __init__(self, *a):
        pass

    def __enter__(self):
        return True

    def __exit__(self, *a):
        return False


M.SingleInstance = NoLock

from calibre.gui2 import gprefs
from calibre.utils.config import dynamic, prefs

dynamic.set('welcome_wizard_was_run', True)
prefs.set('library_path', LIB)
gprefs['color_palette'] = MODE
gprefs['show_splash_screen'] = False
# Otherwise every fresh config adds calibre's Quick Start Guide to the library again.
gprefs['quick_start_guide_added'] = True

from qt.core import QPainter, Qt, QTimer


def later(ms, fn):
    QTimer.singleShot(ms, fn)


def save(pixmap, name):
    path = os.path.join(OUT, f'{name}.png')
    pixmap.save(path)
    print('saved', path, flush=True)


def with_popup(main, popup):
    "The window with a top-level popup painted where it sits on screen."
    shot = main.grab()
    if popup is not None and popup.isVisible():
        p = QPainter(shot)
        p.drawPixmap(main.mapFromGlobal(popup.mapToGlobal(popup.rect().topLeft())), popup.grab())
        p.end()
    return shot


def select(gui, row):
    view = gui.library_view
    view.set_current_row(row)
    view.select_rows([view.model().id(row)])


def run(app):
    main = next(w for w in app.topLevelWidgets() if w.__class__.__name__ == 'Main')
    if LANG == 'he':
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    main.showNormal()
    main.resize(*SIZE)
    select(main, 2)
    centre = main.zen_centre
    steps = [
        lambda: centre.toolbar.switcher.choose(False),
        lambda: save(main.grab(), 'table'),
        lambda: (centre.toolbar.switcher.choose(True), select(main, 5)),
        lambda: save(main.grab(), 'grid'),
        main.iactions['Find Action'].show_popup,
        lambda: save(with_popup(main, _popup(app)), 'find'),
        lambda: _popup(app) and _popup(app).hide(),
        lambda: centre.toolbar.switcher.choose(False),
        lambda: os._exit(0),
    ]

    def step(i=0):
        try:
            steps[i]()
        except Exception:
            import traceback

            traceback.print_exc()
        if i + 1 < len(steps):
            later(SETTLE_MS, lambda: step(i + 1))

    later(SETTLE_MS, step)


def _popup(app):
    "Find an action's popup while it is open."
    for w in app.topLevelWidgets():
        if w.isVisible() and w.__class__.__name__ == 'ActionSearchPopup':
            return w
    return None


orig = M.run_gui_


def wrapped(opts, args, app, gui_debug=None):
    later(STARTUP_MS, lambda: run(app))
    return orig(opts, args, app, gui_debug)


M.run_gui_ = wrapped
M.main(['calibre'])
