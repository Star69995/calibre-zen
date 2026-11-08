#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Sorting by what is inside the Details column.

Details is the `title` column with `authors` and `series` folded into it and
hidden (`table.FOLDED_COLUMNS`). Left alone, a click on its header sorted by
title and nothing else, and a sort on authors or series -- from the Sort by
menu, the status bar, a saved layout -- put calibre's arrow on a hidden section,
so the header showed no sort at all. Three things here put that right:

- **A click on the header asks.** It opens a menu of the parts the column is
  made of -- Title, Authors, Series, whichever the list has -- and the two
  directions, each ticked for the sort that is on. The choice is calibre's
  `sort_by_named_field`, the same call the Sort by menu makes, so what a sort
  means, its history and its saving stay calibre's.
- **The arrow stays on Details** while the list is sorted on one of its parts,
  wherever the sort came from.
- **The header names the part**: "Details · Authors". Its tooltip says a click
  chooses.

Nothing is stored: the sort is the model's own `sorted_on`.
"""

from __future__ import annotations

from qt.core import QActionGroup, QCursor, QMenu, QPoint, Qt

from calibre_zen.centre import table
from calibre_zen.centre.preview import SEPARATOR

# The parts of Details, first the one the column is.
PARTS = (table.DETAILS_COLUMN, *table.FOLDED_COLUMNS)


def part_title(key: str) -> str:
    "A part's name in the menu and the header: calibre's own words for the field."
    return {'title': _('Title'), 'authors': _('Authors'), 'series': _('Series')}[key]


def parts(view) -> list[str]:
    "The parts of Details this view's model has, Title first. None for a view without Details."
    column_map = getattr(view, 'column_map', None) or ()
    if table.DETAILS_COLUMN not in column_map:
        return []
    return [key for key in PARTS if key in column_map]


def sorted_on(model) -> tuple[str, bool]:
    "The field the model is sorted on and whether ascending, or ('', True) when it cannot say."
    try:
        field, ascending = model.sorted_on
    except AttributeError, TypeError, ValueError:
        return '', True
    return str(field), bool(ascending)


def sorted_part(model) -> str:
    "The part of Details the model is sorted on, or '' when it is sorted on something else."
    field = sorted_on(model)[0]
    return field if field in PARTS and field in (getattr(model, 'column_map', None) or ()) else ''


def header_text(model) -> str:
    "The Details header: the column's name, and the part the list is sorted on."
    part = sorted_part(model)
    return _('Details') + SEPARATOR + part_title(part) if part else _('Details')


def header_tooltip() -> str:
    return _('Click to sort by title, authors or series')


def point_indicator(view) -> None:
    """
    Put the header's sort arrow where the sort is: on Details while the list is
    sorted on any of its parts, else on the sorted column, else nowhere.
    Signals are blocked, as calibre blocks them, so moving the arrow sorts
    nothing. Also undoes the flip Qt gives the arrow on a click that asks.
    """
    model = view.model()
    field, ascending = sorted_on(model)
    column_map = list(getattr(view, 'column_map', None) or ())
    target = table.DETAILS_COLUMN if sorted_part(model) else field
    section = column_map.index(target) if target in column_map else -1
    header = view.horizontalHeader()
    header.blockSignals(True)
    try:
        header.setSortIndicator(section, Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder)
    finally:
        header.blockSignals(False)
    # The arrow may not have moved while the words did ("Details · Title" to
    # "Details · Authors"), and Qt repaints a section only for the arrow.
    header.viewport().update()


def is_details(view, col: int) -> bool:
    "Whether logical column `col` of `view` is Details."
    column_map = getattr(view, 'column_map', None) or ()
    return bool(parts(view)) and 0 <= col < len(column_map) and column_map[col] == table.DETAILS_COLUMN


def menu_position(view) -> QPoint:
    "Under the Details header, at its start edge; at the pointer if the header cannot say."
    header = view.horizontalHeader()
    section = view.column_map.index(table.DETAILS_COLUMN)
    x = header.sectionViewportPosition(section)
    if view.layoutDirection() == Qt.LayoutDirection.RightToLeft:
        x += header.sectionSize(section)
    if x < 0 or x > header.width():
        return QCursor.pos()
    return header.mapToGlobal(QPoint(x, header.height()))


def build_menu(view, parent=None) -> QMenu:
    """
    The parts and the two directions, the current sort ticked. A part is sorted
    A to Z when chosen; a direction turns the sort that is on, and is not
    offered while the list is sorted on something outside Details.
    """
    ascending = sorted_on(view.model())[1]
    current = sorted_part(view.model())
    menu = QMenu(parent or view)
    menu.setObjectName('zenDetailsSortMenu')
    title = menu.addAction(_('Sort by'))
    title.setEnabled(False)

    group = QActionGroup(menu)
    for key in parts(view):
        action = menu.addAction(part_title(key))
        action.setCheckable(True)
        action.setChecked(key == current)
        action.setActionGroup(group)
        action.triggered.connect(lambda _checked=False, key=key: view.sort_by_named_field(key, ascending if key == current else True))

    menu.addSeparator()
    directions = QActionGroup(menu)
    for text, up in ((_('Ascending'), True), (_('Descending'), False)):
        action = menu.addAction(text)
        action.setCheckable(True)
        action.setChecked(bool(current) and up == ascending)
        action.setEnabled(bool(current))
        action.setActionGroup(directions)
        action.triggered.connect(lambda _checked=False, up=up: view.sort_by_named_field(current, up))
    return menu


def choose(view) -> None:
    "Ask what to sort Details by, the header's arrow put back first: Qt has already moved it on the click."
    point_indicator(view)
    menu = build_menu(view)
    menu.exec(menu_position(view))
    menu.deleteLater()
