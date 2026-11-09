#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Update on device: replace what is on a connected device with the library's copy,
where it is.

Sending a book again is not that. calibre works out a new place for every send
from the device's folder template, so a book the reader has filed by hand lands
in a second folder and the old copy stays. Here the device's own file is the
target: same folder, same name, same format. The library's copy of that format
goes over it, so an edit made in the library (a fixed typo, a Book Cleanup)
reaches the device without anything moving.

No Qt in this module: `make_plan` reads the device's booklists and the library,
`replace_files` runs on the device thread, and actions.py wires them to the window.
"""

from __future__ import annotations

import os
import tempfile
import traceback
from dataclasses import dataclass, field

KEPUB_SUFFIX = '.kepub.epub'  # a Kobo's KEPUB, which is the library's KEPUB format and not its EPUB
KEPUB = 'KEPUB'
CARDS = (None, 'carda', 'cardb')  # the booklists' order: main memory, card A, card B
TEMP_SUFFIX = '.zen-tmp'  # the new file is written beside the old one under this name, then renamed over it


def device_format(lpath: str) -> str:
    "The library format name of a file on the device: 'EPUB' for book.epub, 'KEPUB' for book.kepub.epub."
    lower = lpath.lower()
    if lower.endswith(KEPUB_SUFFIX):
        return KEPUB
    return os.path.splitext(lower)[1][1:].upper()


@dataclass
class Item:
    "One file on the device to be replaced."

    book_id: int
    card: int  # index into CARDS and the booklists
    book: object  # the device's own book entry; its `path` is where the file is, and stays
    fmt: str

    @property
    def title(self) -> str:
        return getattr(self.book, 'title', None) or self.book.lpath


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)  # to replace
    no_format: list[Item] = field(default_factory=list)  # on the device, but the library has no file in that format
    off_device: list[int] = field(default_factory=list)  # selected, with no copy on the device


def make_plan(booklists, book_ids, formats_of) -> Plan:
    """
    What to replace for `book_ids`, from the device's `booklists`: every copy that
    calibre has matched to one of them (`application_id`), in the format it has on
    the device. `formats_of(book_id)` is the set of format names the library holds.
    A book on the device twice is replaced twice.
    """
    wanted = set(book_ids)
    plan, found = Plan(), set()
    for card, booklist in enumerate(booklists):
        for book in booklist or ():
            book_id = getattr(book, 'application_id', None)
            if book_id not in wanted:
                continue
            found.add(book_id)
            item = Item(book_id, card, book, device_format(book.lpath))
            (plan.items if item.fmt in formats_of(book_id) else plan.no_format).append(item)
    plan.off_device = [i for i in book_ids if i not in found]
    return plan


def usbms_writer(device, item: Item, local: str):
    """
    A mass-storage device is a folder: write beside the old file and rename over
    it, so a transfer that fails half way leaves the old file, not half a new one.
    Returns the location `add_books_to_metadata` takes for this device.
    """
    target = device.munge_path(device.normalize_path(item.book.path))
    written = device.put_file(local, target + TEMP_SUFFIX, replace_file=True)
    try:
        os.replace(written, target)
    except OSError:
        os.remove(written)
        raise
    return (target, CARDS[item.card])


def mtp_writer(device, item: Item, local: str):
    "An MTP device is not a folder: put a file over the old one, in the old one's folder."
    old = device.filesystem_cache.resolve_mtp_id_path(item.book.path)
    with open(local, 'rb') as stream:
        placed = device.put_file(old.parent, old.name, stream, os.path.getsize(local))
    return (placed, item.card)


def writer_for(device):
    "The function that puts a file over its old copy on `device`, or None for a kind of device that cannot."
    from calibre.devices.usbms.driver import USBMS

    if isinstance(device, USBMS):
        return usbms_writer
    if hasattr(device, 'filesystem_cache') and hasattr(device, 'put_file'):
        return mtp_writer
    return None


@dataclass
class Written:
    item: Item
    location: object  # what the device's `add_books_to_metadata` takes
    metadata: object  # the library's metadata for the book, which that call puts in the device's listing


@dataclass
class Outcome:
    written: list[Written] = field(default_factory=list)
    errors: list[tuple[Item, str]] = field(default_factory=list)
    notes: list[tuple[Item, str]] = field(default_factory=list)  # replaced, but something was not as it should be


def embed_metadata(path: str, mi, fmt: str) -> str:
    """
    Write the library's metadata into the copy about to be sent, as a send does.
    The book goes as it is when the format cannot take it. Returns why, or ''.
    """
    from calibre.ebooks.metadata.meta import set_metadata

    try:
        with open(path, 'r+b') as stream:
            set_metadata(stream, mi, stream_type=fmt.lower())
    except Exception as e:
        return f'metadata not written into the file: {e}'
    return ''


def replace_one(device, writer, db, item: Item, folder: str, outcome: Outcome) -> None:
    "Copy the library's file out, put the metadata in, write it over the device's. Records the result."
    mi = None
    local = os.path.join(folder, f'{item.book_id}.{item.fmt.lower()}')
    try:
        mi = db.get_metadata(item.book_id, index_is_id=True, get_cover=True)
        if not db.new_api.copy_format_to(item.book_id, item.fmt, local):
            raise FileNotFoundError(f'the library has no {item.fmt} file for this book')
        note = embed_metadata(local, mi, item.fmt)
        location = writer(device, item, local)
    except Exception:
        outcome.errors.append((item, traceback.format_exc()))
        return
    finally:
        for path in (local, getattr(mi, 'cover', None)):  # the cover is a temporary file get_cover made
            if path and os.path.exists(path):
                os.remove(path)
    outcome.written.append(Written(item, location, mi))
    if note:
        outcome.notes.append((item, note))


def replace_files(device, db, items: list[Item]) -> Outcome:
    """
    Run on the device thread (a DeviceJob): replace each item's file with the
    library's. A book that fails is recorded and the rest carry on, so one bad
    file does not stop a hundred.
    """
    writer = writer_for(device)
    outcome = Outcome()
    with tempfile.TemporaryDirectory(prefix='zen-ondevice-') as folder:
        for i, item in enumerate(items):
            device.report_progress(i / len(items), item.title)
            replace_one(device, writer, db, item, folder, outcome)
    device.report_progress(1, '')
    return outcome
