#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
A Format column in the list of books on a device.

calibre's device list has six fixed columns (`DeviceBooksModel.__init__`,
`gui2/library/models.py`) and none says what kind of file a book is, though
the reader cares: a Kindle shelf mixes AZW3, MOBI and PDF. The format is the
file's extension, which the model already works out for the Book details
panel (`get_book_display_info`), so nothing new is read from the device.

Three wraps, from outside:

`DeviceBooksModel.__init__`
    Adds `format` to the column map, after Size, with its header.

`DeviceBooksModel.data`
    The cell's text: the extension in capitals, as the library's Formats
    column writes it. Everything else goes to calibre.

`DeviceBooksModel.sort`
    calibre's sort looks the column up in a table of its own and would raise
    on one it does not know, so a sort on this one is done here, with the same
    two orders (`map` for what the search shows, `sorted_map` for all of it).

The column is hidden, moved and resized like the others, and the view keeps
its state under calibre's own key. A saved layout from before this has no
position for it, and `apply_state` leaves it where the map puts it.

Off with `CALIBRE_ZEN_DEVICE_COLUMNS=0`.
"""

import os

from calibre_zen.features import from_env

COLUMN = 'format'
AFTER = 'size'  # the column it follows

_installed = False


def enabled() -> bool:
    return from_env('CALIBRE_ZEN_DEVICE_COLUMNS') is not False


def book_format(path) -> str:
    "A device book's format, from its file name: 'EPUB', or '' when it has no extension."
    ext = os.path.splitext(path or '')[1]
    return ext[1:].upper()


def add_column(column_map: list, headers: dict, title: str) -> None:
    "Put the Format column after Size (or last), once."
    if COLUMN in column_map:
        return
    at = column_map.index(AFTER) + 1 if AFTER in column_map else len(column_map)
    column_map.insert(at, COLUMN)
    headers[COLUMN] = title


def install() -> bool:
    global _installed
    if _installed or not enabled():
        return _installed
    from qt.core import Qt

    from calibre.gui2.library.models import DeviceBooksModel
    from calibre.utils.icu import sort_key
    from calibre.utils.localization import _

    orig_init = DeviceBooksModel.__init__
    orig_data = DeviceBooksModel.data
    orig_sort = DeviceBooksModel.sort
    text_roles = (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole)

    def __init__(self, parent):
        orig_init(self, parent)
        add_column(self.column_map, self.headers, _('Format'))

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role in text_roles and index.isValid() and self.column_map[index.column()] == COLUMN:
            try:
                return book_format(self.db[self.map[index.row()]].path)
            except IndexError, AttributeError:
                return None  # the device went away under the view
        return orig_data(self, index, role)

    def sort(self, column, order=Qt.SortOrder.AscendingOrder, reset=True):
        if self.column_map[column] != COLUMN:
            return orig_sort(self, column, order, reset)
        if not isinstance(order, Qt.SortOrder):
            order = Qt.SortOrder.AscendingOrder if order else Qt.SortOrder.DescendingOrder
        descending = order != Qt.SortOrder.AscendingOrder

        def key(i):
            return sort_key(book_format(getattr(self.db[i], 'path', '')))

        self.map.sort(key=key, reverse=descending)
        self.sorted_map = sorted(range(len(self.db)), key=key, reverse=descending) if len(self.map) != len(self.db) else list(self.map)
        self.sorted_on = (COLUMN, not descending)
        self.sort_history.insert(0, self.sorted_on)
        if reset:
            self.beginResetModel(), self.endResetModel()

    DeviceBooksModel.__init__ = __init__
    DeviceBooksModel.data = data
    DeviceBooksModel.sort = sort
    _installed = True
    return True
