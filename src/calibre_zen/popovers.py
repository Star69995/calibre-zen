#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Where a small popup panel opens relative to the button that opened it.

The jobs panel (status/jobs_panel.py) opens above its segment and the column
picker (centre/columns.py) below its button, and both want the same two things:
the panel's end edge on the button's end edge, so it grows toward the middle of
the window, and the whole of it kept on the screen. In right-to-left the end edge
is the left one, so the rule is written once, here.

They also share how they are painted: `painted_body` gives a popup the frame its
style sheet background goes on, because the popup window itself is see-through.
"""

from __future__ import annotations

from qt.core import QApplication, QFrame, QPoint, Qt, QVBoxLayout


def place(popup, anchor, above: bool, gap: int = 0) -> QPoint:
    """
    Move `popup` next to `anchor` (a widget), above or below it, and return where
    it went. The popup's size is its `sizeHint()`, so call this after it is filled,
    grown to its minimum size: a popup given a fixed width is that wide whatever
    its contents hint, and placing it by the hint puts its end edge past the
    button's.
    """
    size = popup.sizeHint().expandedTo(popup.minimumSize())
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


def painted_body(popup, name: str) -> QFrame:
    """
    Fill `popup` with one frame named `name` and return it; lay the popup's
    contents out on that frame.

    Every popup window is translucent, for its round corners (theme/popups.py),
    and Qt does not paint a style sheet's background on a translucent top-level
    window, so a rule on the popup itself leaves it see-through, its rows
    floating over the window below. A child frame is painted as usual.
    """
    outer = QVBoxLayout(popup)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    body = QFrame(popup)
    body.setObjectName(name)
    body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    outer.addWidget(body)
    return body
