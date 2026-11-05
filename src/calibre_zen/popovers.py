#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Where a small popup panel opens relative to the button that opened it.

The jobs panel (status/jobs_panel.py) opens above its segment and the column
picker (centre/columns.py) below its button, and both want the same two things:
the panel's end edge on the button's end edge, so it grows toward the middle of
the window, and the whole of it kept on the screen. In right-to-left the end edge
is the left one, so the rule is written once, here.
"""

from __future__ import annotations

from qt.core import QApplication, QPoint, Qt


def place(popup, anchor, above: bool, gap: int = 0) -> QPoint:
    """
    Move `popup` next to `anchor` (a widget), above or below it, and return where
    it went. The popup's size is its `sizeHint()`, so call this after it is filled.
    """
    size = popup.sizeHint()
    top_left = anchor.mapToGlobal(QPoint(0, 0))
    rtl = anchor.layoutDirection() == Qt.LayoutDirection.RightToLeft
    x = top_left.x() if rtl else top_left.x() + anchor.width() - size.width()
    y = top_left.y() - size.height() - gap if above else top_left.y() + anchor.height() + gap
    screen = anchor.screen() or QApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        x = max(area.left(), min(x, area.right() - size.width()))
        y = max(area.top(), min(y, area.bottom() - size.height()))
    point = QPoint(x, y)
    popup.move(point)
    return point
