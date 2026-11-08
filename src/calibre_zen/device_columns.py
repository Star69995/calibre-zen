#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Format, Folder and Path columns in the list of books on a device.

calibre's device list has six fixed columns (`DeviceBooksModel.__init__`,
`gui2/library/models.py`) and none says what a book is on the device as a
file: what kind (a Kindle shelf mixes AZW3, MOBI and PDF), which folder it sits
in, or where. All three come from the book's file name, which the model already
holds, so nothing new is read from the device:

- **Format**: the extension in capitals, as the library's Formats column
  writes it. The Book details panel works it out the same way
  (`get_book_display_info`).
- **Folder**: the folder directly holding the book (`documents`, `Books`);
  blank for a book at the device's root.
- **Path**: where the book is, from the device's root (`lpath`, which every
  USB driver keeps, with `/` between folders), read root first even when the
  folder names are Hebrew (`display_path`); its tooltip says the same, for a
  path too long for the column. Where the device is mounted is never shown.

`COLUMNS` is the one list of them; each is a key, a header and a function from
a book's paths to the cell's text. Three wraps, from outside:

`DeviceBooksModel.__init__`
    Adds the columns to the column map, after Size, with their headers.

`DeviceBooksModel.data`
    Their cells' text, and Path's tooltip. Everything else goes to calibre.

`DeviceBooksModel.sort`
    calibre's sort looks the column up in a table of its own and would raise
    on one it does not know, so a sort on one of these is done here, with the
    same two orders (`map` for what the search shows, `sorted_map` for all of
    it).

The columns are hidden, moved and resized like the others -- the Columns
button offers them -- and the view keeps its state under calibre's own key. A
saved layout from before this has no position for them, and `apply_state`
leaves them where the map puts them.

Off with `CALIBRE_ZEN_DEVICE_COLUMNS=0`.
"""

import os
import posixpath
from collections.abc import Callable
from typing import NamedTuple

from calibre_zen.features import from_env
from calibre_zen.i18n import N_

AFTER = 'size'  # the column they follow

_installed = False


def enabled() -> bool:
    return from_env('CALIBRE_ZEN_DEVICE_COLUMNS') is not False


def device_path(book) -> str:
    "Where `book` is from the device's root, with '/' between folders; its full path when the driver keeps no `lpath`."
    lpath = getattr(book, 'lpath', None) or getattr(book, 'path', None) or ''
    return lpath.replace('\\', '/')


def book_format(path) -> str:
    "A book's format, from its file name: 'EPUB', or '' when it has no extension."
    ext = os.path.splitext(path or '')[1]
    return ext[1:].upper()


def book_folder(path) -> str:
    "The name of the folder directly holding the file at `path` ('/'-separated), or '' at the root."
    return posixpath.basename(posixpath.dirname((path or '').rstrip('/')))


# Unicode's left-to-right isolate and mark. A '/' between two Hebrew folder
# names is neutral and joins them into one right-to-left run, which shows
# `ספרים/דפים` as `דפים/ספרים`; a mark after each '/' keeps the folders in the
# order they nest, root first, and the isolate keeps the whole path that way in
# a right-to-left window too.
LRI, PDI, LRM = '\u2066', '\u2069', '\u200e'


def display_path(path: str) -> str:
    "`path` as shown: its folders left to right from the root, whatever script they are in."
    return LRI + path.replace('/', '/' + LRM) + PDI if path else path


class DeviceColumn(NamedTuple):
    key: str  # the lookup name, as the column map and saved layouts know it
    title: str  # the header, marked for translation and translated at use
    text: Callable[[str], str]  # the cell, from the book's device path; also the sort key
    shown: Callable[[str], str] = str  # how that text is displayed


COLUMNS = (
    DeviceColumn('format', N_('Format'), book_format),
    DeviceColumn('folder', N_('Folder'), book_folder),
    # Not 'path': calibre's default layout hides a column by that name (it means the library's).
    DeviceColumn('lpath', N_('Path'), str, display_path),
)
BY_KEY = {c.key: c for c in COLUMNS}


def add_columns(column_map: list, headers: dict, translate=lambda s: s) -> None:
    "Put COLUMNS after Size (or last), in their order, each once."
    at = column_map.index(AFTER) + 1 if AFTER in column_map else len(column_map)
    for column in COLUMNS:
        if column.key in column_map:
            at = column_map.index(column.key) + 1
            continue
        column_map.insert(at, column.key)
        headers[column.key] = translate(column.title)
        at += 1


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
        add_columns(self.column_map, self.headers, _)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        column = BY_KEY.get(self.column_map[index.column()]) if index.isValid() else None
        if column is not None and (role in text_roles or (role == Qt.ItemDataRole.ToolTipRole and column.key == 'lpath')):
            try:
                book = self.db[self.map[index.row()]]
            except IndexError:
                return None  # the device went away under the view
            text = column.text(device_path(book))
            if role == Qt.ItemDataRole.ToolTipRole:
                return column.shown(text) or None
            return column.shown(text) if role == Qt.ItemDataRole.DisplayRole else text
        return orig_data(self, index, role)

    def sort(self, column, order=Qt.SortOrder.AscendingOrder, reset=True):
        ours = BY_KEY.get(self.column_map[column])
        if ours is None:
            return orig_sort(self, column, order, reset)
        if not isinstance(order, Qt.SortOrder):
            order = Qt.SortOrder.AscendingOrder if order else Qt.SortOrder.DescendingOrder
        descending = order != Qt.SortOrder.AscendingOrder

        def key(i):
            return sort_key(ours.text(device_path(self.db[i])))

        self.map.sort(key=key, reverse=descending)
        self.sorted_map = sorted(range(len(self.db)), key=key, reverse=descending) if len(self.map) != len(self.db) else list(self.map)
        self.sorted_on = (ours.key, not descending)
        self.sort_history.insert(0, self.sorted_on)
        if reset:
            self.beginResetModel(), self.endResetModel()

    DeviceBooksModel.__init__ = __init__
    DeviceBooksModel.data = data
    DeviceBooksModel.sort = sort
    _installed = True
    return True
