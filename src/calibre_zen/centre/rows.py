#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
How tall a row is, and what follows from it.

One choice for every list drawn as cards -- the library's table and each
device's list -- made from the view switcher's menu and kept in gprefs. The cover
inside a row is the row less a margin, so a tighter row has a smaller cover and
the card never looks stretched or cramped.

Row height is the vertical header's, not the delegate's `sizeHint`
(`views.py:1196-1210`), and `BooksModel` caches it -- `apply` sets both.
"""

from calibre.gui2 import gprefs
from calibre_zen.theme.tokens import components

PREF_KEY = 'zen_row_height'


def levels() -> tuple:
    "The names, roomiest first."
    return tuple(components.TABLE_ROW_HEIGHTS)


def label_for(name: str) -> str:
    return {'roomy': _('Roomy'), 'default': _('Default'), 'compact': _('Compact'), 'tight': _('Tight')}.get(name, name)


def level() -> str:
    "The level in force: the stored choice, else the shipped default."
    chosen = gprefs.get(PREF_KEY)
    return chosen if chosen in components.TABLE_ROW_HEIGHTS else components.TABLE_ROW_HEIGHT_DEFAULT


def height(name: str | None = None) -> int:
    return components.TABLE_ROW_HEIGHTS[name or level()]


def cover_size(name: str | None = None) -> tuple[int, int]:
    "The cover's width and height inside a row of that level, 2:3."
    cover_h = height(name) - components.TABLE_COVER_MARGIN
    return cover_h * 2 // 3, cover_h


def largest_cover() -> tuple[int, int]:
    "The biggest a row's cover gets, which is what the thumbnails are rendered for."
    return cover_size(levels()[0])


def size(view) -> None:
    "Set one view's row height to the level in force, and the model's copy of it."
    header = view.verticalHeader()
    header.setDefaultSectionSize(max(header.minimumSectionSize(), height()))
    view.model().set_row_height(view.rowHeight(0))


def apply(view) -> None:
    "`size`, for a view already on screen: lay the rows out again and repaint."
    size(view)
    view.scheduleDelayedItemsLayout()
    view.viewport().update()


def views(gui) -> list:
    "Every list that is drawn as cards: the library, its pinned columns, and the devices'."
    ans = []
    for name in ('library_view', 'memory_view', 'card_a_view', 'card_b_view'):
        view = getattr(gui, name, None)
        if view is None:
            continue
        ans.append(view)
        if getattr(view, 'is_library_view', False):
            ans.append(view.pin_view)
    return ans


def set_level(name: str, gui=None) -> None:
    "Store the choice and, where the lists exist, resize them now."
    if name not in components.TABLE_ROW_HEIGHTS:
        return
    gprefs.set(PREF_KEY, name)
    if gui is None:
        return
    for view in views(gui):
        apply(view)
