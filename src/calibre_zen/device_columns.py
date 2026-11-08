#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
More columns in the list of books on a device: what a book is there as a file,
and the metadata the library's list shows.

calibre's device list has six fixed columns (`DeviceBooksModel.__init__`,
`gui2/library/models.py`). The model already holds everything below, so
nothing new is read from the device.

Three say what a book is on the device as a file, from its file name, and are
shown from the start:

- **Format**: the extension in capitals, as the library's Formats column
  writes it. The Book details panel works it out the same way
  (`get_book_display_info`).
- **Folder**: the folder directly holding the book (`documents`, `Books`);
  blank for a book at the device's root.
- **Path**: where the book is, from the device's root (`lpath`, which every
  USB driver keeps, with `/` between folders), read root first even when the
  folder names are Hebrew (`display_path`); its tooltip says the same, for a
  path too long for the column. Where the device is mounted is never shown.

Six are the library's own columns, from the metadata each book on the device
carries (what calibre sent with it, or what the driver read from the file), and
start hidden, offered under the header's Show column and in the Columns panel:
**Series** (`Name [2]`), **Tags**, **Publisher**, **Published** (in the
library's `gui_pubdate_display_format`), **Rating** (as stars) and
**Languages** (by name). Each sorts as the library's does: a series by name and
then number, a date and a rating by value.

`COLUMNS` is the one list of them; each is a key, a header, a function from the
book to the cell's text and, where text would sort wrongly, one to its sort key.
Five wraps, from outside:

`DeviceBooksModel.__init__`
    Adds the columns to the column map, after Size, with their headers.

`DeviceBooksModel.data`
    Their cells' text, and Path's tooltip. Everything else goes to calibre.

`DeviceBooksModel.sort`
    calibre's sort looks the column up in a table of its own and would raise
    on one it does not know, so a sort on one of these is done here, with the
    same two orders (`map` for what the search shows, `sorted_map` for all of
    it).

`DeviceBooksView.get_default_state` / `get_old_state`
    The hidden-at-first columns go into the default layout's hidden list, and
    once into a saved layout that has not met them yet, marked as calibre marks
    a column it injects (`<key>_injected`). `get_state` keeps the mark, so a
    column the reader shows stays shown.

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
CALIBRE_DELEGATES = 10  # how many columns DeviceBooksView.__init__ gives a TextDelegate
RATING_MAX = 10  # calibre keeps a rating as 0-10, two per star

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


def series_text(book) -> str:
    "'Name [2]', as the library writes a series and its number; '' for none."
    series = getattr(book, 'series', None)
    if not series:
        return ''
    from calibre.ebooks.metadata import fmt_sidx

    index = getattr(book, 'series_index', None)
    return series if index is None else f'{series} [{fmt_sidx(index)}]'


def series_order(book):
    "Sorts a series by name, then by number within it."
    from calibre.utils.icu import sort_key

    return (sort_key(getattr(book, 'series', None) or ''), float(getattr(book, 'series_index', None) or 0))


def tags_text(book) -> str:
    "The tags, sorted, between commas."
    from calibre.utils.icu import sort_key

    return ', '.join(sorted(getattr(book, 'tags', None) or (), key=sort_key))


def publisher_text(book) -> str:
    return getattr(book, 'publisher', None) or ''


def defined_date(book):
    "The book's publication date, or None when it has none."
    from calibre.utils.date import is_date_undefined

    dt = getattr(book, 'pubdate', None)
    return None if dt is None or is_date_undefined(dt) else dt


def pubdate_text(book) -> str:
    "The publication date, in the library's format for it; '' for none."
    dt = defined_date(book)
    if dt is None:
        return ''
    from calibre.utils.config import tweaks
    from calibre.utils.date import format_date

    return format_date(dt, tweaks['gui_pubdate_display_format'] or 'MMM yyyy')


def pubdate_order(book):
    "Books with no date first, then by date."
    dt = defined_date(book)
    return (0, 0.0) if dt is None else (1, dt.timestamp())


def rating_value(book) -> int:
    "The rating as calibre keeps it, 0 to 10 (two per star)."
    try:
        return max(0, min(RATING_MAX, int(getattr(book, 'rating', None) or 0)))
    except TypeError, ValueError:
        return 0


def rating_text(book) -> str:
    "The rating as stars, half stars included; '' for none."
    from calibre.ebooks.metadata import rating_to_stars

    return rating_to_stars(rating_value(book), allow_half_stars=True)


def languages_text(book) -> str:
    "The languages by name, in the reader's language, between commas."
    from calibre.utils.localization import calibre_langcode_to_name

    return ', '.join(calibre_langcode_to_name(lc) for lc in getattr(book, 'languages', None) or ())


def from_path(fn: Callable[[str], str]) -> Callable[[object], str]:
    "A cell worked out from the book's device path."
    return lambda book: fn(device_path(book))


class DeviceColumn(NamedTuple):
    key: str  # the lookup name, as the column map and saved layouts know it
    title: str  # the header, marked for translation and translated at use
    text: Callable[[object], str]  # the cell, from the book
    shown: Callable[[str], str] = str  # how that text is displayed
    order: Callable[[object], object] | None = None  # the sort key, when it is not the text's
    hidden: bool = False  # hidden until the reader shows it


COLUMNS = (
    DeviceColumn('format', N_('Format'), from_path(book_format)),
    DeviceColumn('folder', N_('Folder'), from_path(book_folder)),
    # Not 'path': calibre's default layout hides a column by that name (it means the library's).
    DeviceColumn('lpath', N_('Path'), from_path(str), display_path),
    DeviceColumn('series', N_('Series'), series_text, order=series_order, hidden=True),
    DeviceColumn('tags', N_('Tags'), tags_text, hidden=True),
    DeviceColumn('publisher', N_('Publisher'), publisher_text, hidden=True),
    DeviceColumn('pubdate', N_('Published'), pubdate_text, order=pubdate_order, hidden=True),
    DeviceColumn('rating', N_('Rating'), rating_text, order=rating_value, hidden=True),
    DeviceColumn('languages', N_('Languages'), languages_text, hidden=True),
)
BY_KEY = {c.key: c for c in COLUMNS}
HIDDEN_AT_FIRST = tuple(c.key for c in COLUMNS if c.hidden)


def injected_mark(key: str) -> str:
    "The key a saved layout carries once it has met column `key`, calibre's own spelling for it."
    return key + '_injected'


def mark_met(state: dict) -> dict:
    "Record in `state` that it has met every hidden-at-first column."
    for key in HIDDEN_AT_FIRST:
        state[injected_mark(key)] = True
    return state


def hide_new(state: dict) -> dict:
    "Hide, in a layout, each hidden-at-first column it has not met yet, and mark it met."
    hidden = state.setdefault('hidden_columns', [])
    for key in HIDDEN_AT_FIRST:
        if not state.get(injected_mark(key)) and key not in hidden:
            hidden.append(key)
    return mark_met(state)


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
    from calibre.gui2.library.views import DeviceBooksView
    from calibre.utils.icu import sort_key
    from calibre.utils.localization import _

    orig_init = DeviceBooksModel.__init__
    orig_data = DeviceBooksModel.data
    orig_sort = DeviceBooksModel.sort
    orig_default_state = DeviceBooksView.get_default_state
    orig_old_state = DeviceBooksView.get_old_state
    orig_get_state = DeviceBooksView.get_state
    orig_view_init = DeviceBooksView.__init__
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
            text = column.text(book)
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
        order_of = ours.order or (lambda book: sort_key(ours.text(book)))

        def key(i):
            return order_of(self.db[i])

        self.map.sort(key=key, reverse=descending)
        self.sorted_map = sorted(range(len(self.db)), key=key, reverse=descending) if len(self.map) != len(self.db) else list(self.map)
        self.sorted_on = (ours.key, not descending)
        self.sort_history.insert(0, self.sorted_on)
        if reset:
            self.beginResetModel(), self.endResetModel()

    def view_init(self, parent):
        orig_view_init(self, parent)
        # calibre gives its first CALIBRE_DELEGATES columns a TextDelegate, which
        # edits Title, Authors and Collections; the columns added push
        # Collections past them.
        from calibre.gui2.library.delegates import TextDelegate

        for i in range(CALIBRE_DELEGATES, self._model.columnCount()):
            self.setItemDelegateForColumn(i, TextDelegate(self))

    def get_default_state(self):
        return hide_new(orig_default_state(self))

    def get_old_state(self):
        state = orig_old_state(self)
        return None if state is None else hide_new(state)

    def get_state(self):
        return mark_met(orig_get_state(self))

    DeviceBooksModel.__init__ = __init__
    DeviceBooksModel.data = data
    DeviceBooksModel.sort = sort
    DeviceBooksView.__init__ = view_init
    DeviceBooksView.get_default_state = get_default_state
    DeviceBooksView.get_old_state = get_old_state
    DeviceBooksView.get_state = get_state
    _installed = True
    return True
