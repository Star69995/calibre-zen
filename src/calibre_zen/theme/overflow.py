#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What does not fit on the toolbar, opened as a tray with a surface.

Qt keeps those buttons behind a button at the end of the bar and opens them by
growing the bar itself to more rows. The grown bar is as transparent as the bar
was, so the page showed through the buttons and the text under them read as
part of the page.

The sheet (`09-containers.qss`) draws the tray. The one thing a sheet cannot do
is know the tray is open, which Qt says only by checking the button, so this
marks the bar while it is, and the sheet gives a marked bar a surface.
"""

from qt.core import QToolButton

BUTTON_NAME = 'qt_toolbar_ext_button'  # Qt's own, in QToolBarExtension
OPEN = 'zenOverflowOpen'

_TRACKED = 'zenOverflowTracked'


def repolish(widget) -> None:
    "Re-polishing is what makes a rule keyed on a dynamic property take effect."
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def mark(bar, is_open: bool) -> None:
    bar.setProperty(OPEN, is_open)
    repolish(bar)


def track(bar) -> bool:
    """
    Mark `bar` while its overflow tray is open. Safe to call again for the
    same bar, which calibre rebuilds in place: the button is Qt's and stays.
    """
    button = bar.findChild(QToolButton, BUTTON_NAME)
    if button is None or button.property(_TRACKED):
        return button is not None
    button.setProperty(_TRACKED, True)
    button.toggled.connect(lambda checked: mark(bar, checked))
    return True
