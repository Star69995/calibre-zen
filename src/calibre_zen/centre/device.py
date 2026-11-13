#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A device's list, drawn and described the way the library's is.

calibre's device list is a plain table of the files on the device -- title,
author, size, date -- with no cover, no series and nothing a reader tagged, because
a device's own listing has none of it. But a book that was sent from the library, or
that matches one in it, is *linked*: `set_books_in_library` (`gui2/device.py:1857`)
sets its `application_id` to the library book's id and `in_library` to how it
matched. The cover, the series and the rest are all there, in the library, so a
linked row borrows them. A row with no match keeps what the device itself knows,
and a device that has thumbnails (a Kobo, say) still shows those.

Nothing here writes to the library or the device.
"""

from typing import NamedTuple

from qt.core import QPixmap

from calibre.utils.img import image_from_data


class Linked(NamedTuple):
    "The library book a device book stands for."

    db: object  # the library's new-style database
    book_id: int


def library_db():
    "The library the window has open, or None before there is one."
    from calibre.gui2.ui import get_gui

    gui = get_gui()
    model = None if gui is None else gui.library_view.model()
    return getattr(getattr(model, 'db', None), 'new_api', None)


def book_at(index):
    "The device's own record for the row `index` is on."
    model = index.model()
    return model.db[model.map[index.row()]]


def linked(book) -> Linked | None:
    "The library book `book` was matched to, if there is one and it is still there."
    book_id = getattr(book, 'application_id', None)
    if book_id is None or not getattr(book, 'in_library', None):
        return None
    db = library_db()
    if db is None or not db.has_id(book_id):
        return None
    return Linked(db, book_id)


def series_text(book, link: Linked | None) -> str:
    "`Name [2]`, the way the library's series column reads; the device's own series first."
    from calibre.ebooks.metadata import fmt_sidx

    name, index = getattr(book, 'series', None), getattr(book, 'series_index', None)
    if not name and link is not None:
        name = link.db.field_for('series', link.book_id)
        index = link.db.field_for('series_index', link.book_id)
    if not name:
        return ''
    return f'{name} [{fmt_sidx(index or 0)}]'


def fill_from_library(info, link: Linked) -> None:
    """
    Give the Book details panel's record of a device book what the library's record of
    it has and the device's listing lacks: the cover first, then whatever the device
    left empty. What the device says -- title, authors, path, format, date -- stays.
    """
    mi = link.db.get_metadata(link.book_id, get_cover=True, cover_as_data=True)
    if mi.cover_data and mi.cover_data[1]:
        # The panel hands `cover_data[1]` to `QPixmap.fromImage` -- as a device's own
        # record does (`DeviceBooksModel.get_book_display_info`) -- so it is an image,
        # not the file's bytes.
        image = image_from_data(mi.cover_data[1])
        if not image.isNull():
            info.cover_data = (mi.cover_data[0], image)
    for field in ('series', 'series_index', 'comments', 'publisher', 'pubdate', 'rating', 'languages', 'identifiers'):
        if not getattr(info, field, None):
            setattr(info, field, getattr(mi, field, None))
    info.tags = list(info.tags or mi.tags or ())


def cover_pixmap(index, cache) -> QPixmap | None:
    """
    The cover for the row, or None while there is nothing to show yet.

    Through `cache`, the library's thumbnail cache, for a linked book -- the same
    thumbnails and the same disk cache the library's own table uses -- and the
    device's thumbnail otherwise, if it has one.
    """
    link = linked(book_at(index))
    if link is not None:
        return cache.thumbnail_as_pixmap(link.book_id)
    return device_cover(index)


def device_cover(index) -> QPixmap | None:
    "The device's own thumbnail for the row, if it has one."
    model = index.model()
    image = model.cover(index.row())
    if image is model.default_image or image.isNull():
        return None
    return QPixmap.fromImage(image)
