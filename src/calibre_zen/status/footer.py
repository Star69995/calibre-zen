#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The jobs segment in the footer of a dialog that blocks the window.

Preferences is application-modal and hides the status bar, so while it is open
there is no telling whether a conversion has finished. The same segment the bar
has goes into the dialog's button row, built from the same class and reading the
same manager, so nothing is counted twice. It is hidden while there are no jobs
and is clickable, which a separate window would not be above a modal dialog.

One wrap, no upstream file edited:

`Preferences.__init__`
    Runs once the dialog's button row exists; the segment is put at its start.
"""

from __future__ import annotations

import traceback

_installed = False


def add_jobs_strip(dialog, gui):
    "Put a jobs segment at the start of `dialog`'s last row, which is its button row."
    from calibre_zen.status.segments import JobsSegment

    row = dialog.layout().itemAt(dialog.layout().count() - 1).layout()
    segment = JobsSegment(gui, dialog, hide_idle=True)
    row.insertWidget(0, segment)
    segment.attach()
    dialog.zen_jobs = segment
    return segment


def install() -> bool:
    "Wrap the dialog's constructor. Safe to call twice."
    global _installed
    if _installed:
        return True
    from calibre.gui2.preferences.main import Preferences

    orig_init = Preferences.__init__

    def __init__(self, gui, *args, **kwargs):
        orig_init(self, gui, *args, **kwargs)
        try:
            add_jobs_strip(self, gui)
        except Exception:
            # The dialog without the segment is calibre's whole dialog.
            traceback.print_exc()

    Preferences.__init__ = __init__
    _installed = True
    return True
