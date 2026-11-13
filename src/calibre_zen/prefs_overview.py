#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Preferences opens on its overview whole, with nothing to scroll.

The overview is a grid of page icons that should be seen at once. Whatever the
font, the language or the size saved by an earlier dialog, the window grows by
exactly what the grid's scroll bar says is missing, never shrinks, and never
goes past the screen.

One wrap, no upstream file edited:

`Preferences.showEvent`
    Runs once the dialog is laid out for the first time, which is the first
    moment the scroll bar knows how much is missing.
"""

from __future__ import annotations

import traceback

_installed = False


def missing_height(dialog) -> int:
    "How much taller the dialog must be for the overview to need no scroll bar, within the screen."
    if dialog.stack.currentWidget() is not dialog.browser:
        return 0
    screen = dialog.screen()
    missing = dialog.browser.verticalScrollBar().maximum()
    if missing <= 0 or screen is None:
        return 0
    room = screen.availableGeometry().height() - dialog.frameGeometry().height()
    return min(missing, max(0, room))


def grow_to_fit_overview(dialog) -> None:
    dialog.resize(dialog.width(), dialog.height() + missing_height(dialog))


def install() -> bool:
    "Wrap the dialog's showEvent. Safe to call twice."
    global _installed
    if _installed:
        return True
    from calibre.gui2.preferences.main import Preferences

    orig_show = Preferences.showEvent

    def showEvent(self, event):
        orig_show(self, event)
        try:
            grow_to_fit_overview(self)
        except Exception:
            # The dialog at its saved size is calibre's whole dialog.
            traceback.print_exc()

    Preferences.showEvent = showEvent
    _installed = True
    return True
