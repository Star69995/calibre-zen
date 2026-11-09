#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Update on device (books/ondevice.py): the plan, and the writes, against a real
mass-storage driver pointed at a folder.

The folder device is calibre's own USBMS driver with a directory for a disk, so
`put_file`, path handling and the booklists are the code a Kindle or a Kobo goes
through. What is checked is that a file lands over its old copy, in the folder it
was filed in, with nothing left beside it.
"""

import os
import zipfile
from types import SimpleNamespace
from unittest import mock

from calibre_zen.books import ondevice
from calibre_zen.books.ondevice import KEPUB, device_format, make_plan, replace_files
from calibre_zen.tests.base import ZenTestCase
from calibre_zen.tests.test_books import make_epub, short_library


class TestPlan(ZenTestCase):
    def book(self, lpath, book_id):
        return SimpleNamespace(lpath=lpath, application_id=book_id, title=lpath)

    def test_a_format_is_named_as_the_library_names_it(self):
        self.assertEqual(device_format('Shelf/Alpha.epub'), 'EPUB')
        self.assertEqual(device_format('Alpha.AZW3'), 'AZW3')
        self.assertEqual(device_format('Alpha.kepub.epub'), KEPUB, 'a Kobo book is the library KEPUB, not its EPUB')
        self.assertEqual(device_format('no-extension'), '')

    def test_a_copy_is_replaced_in_its_own_format_and_the_rest_is_said(self):
        main = [self.book('Shelf/a.epub', 1), self.book('b.azw3', 2), self.book('c.epub', 3), self.book('d.epub', 99)]
        card = [self.book('a.epub', 1)]
        have = {1: {'EPUB'}, 2: {'EPUB'}, 3: {'EPUB', 'PDF'}, 4: {'EPUB'}}

        plan = make_plan([main, card, None], [1, 2, 3, 4], lambda i: have[i])

        self.assertEqual([(i.book_id, i.card, i.fmt) for i in plan.items], [(1, 0, 'EPUB'), (3, 0, 'EPUB'), (1, 1, 'EPUB')], 'a book on two places is replaced in both')
        self.assertEqual([(i.book_id, i.fmt) for i in plan.no_format], [(2, 'AZW3')], 'the device has azw3, the library only an epub: left alone')
        self.assertEqual(plan.off_device, [4])

    def test_a_book_the_selection_does_not_name_is_never_touched(self):
        plan = make_plan([[self.book('a.epub', 1)]], [2], lambda i: {'EPUB'})
        self.assertEqual((plan.items, plan.no_format, plan.off_device), ([], [], [2]))


class TestReplace(ZenTestCase):
    def setUp(self):
        from calibre.db.legacy import LibraryDatabase
        from calibre.devices.folder_device.driver import FOLDER_DEVICE
        from calibre.devices.usbms.books import Book

        self.disk = self.mkdtemp()
        self.device = FOLDER_DEVICE(self.disk)
        self.device.set_progress_reporter(lambda fraction, message: None)
        self.db = LibraryDatabase(short_library(self, 'books-ondevice'))
        self.addCleanup(self.db.close)
        self.api = self.db.new_api
        self.ids = sorted(self.api.all_book_ids())
        self.library_epub = os.path.join(self.mkdtemp(), 'edited.epub')
        make_epub(self.library_epub)
        self.api.add_format(self.ids[0], 'EPUB', self.library_epub, run_hooks=False)
        self.make_book = Book

    def on_device(self, lpath, book_id, content=b'the old copy'):
        "A file the reader filed by hand, and the entry calibre's listing has for it."
        path = os.path.join(self.disk, *lpath.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(content)
        book = self.make_book(self.disk + os.sep, lpath, other=None)
        book.application_id, book.title = book_id, 'Alpha'
        return ondevice.Item(book_id, 0, book, device_format(lpath))

    def files(self):
        return sorted(os.path.relpath(os.path.join(d, f), self.disk).replace(os.sep, '/') for d, _, fs in os.walk(self.disk) for f in fs)

    def test_the_library_copy_goes_over_the_old_one_where_it_is(self):
        item = self.on_device('My shelf/History/Alpha.epub', self.ids[0])

        outcome = replace_files(self.device, self.db, [item])

        self.assertEqual(outcome.errors, [])
        self.assertEqual(self.files(), ['My shelf/History/Alpha.epub'], 'nothing moved, nothing left beside it')
        with zipfile.ZipFile(os.path.join(self.disk, 'My shelf', 'History', 'Alpha.epub')) as z:
            self.assertIn('ch1.xhtml', z.namelist(), 'it is the library book now')
        self.assertEqual(len(outcome.written), 1)
        location, card = outcome.written[0].location
        self.assertEqual((os.path.normcase(location), card), (os.path.normcase(os.path.join(self.disk, 'My shelf', 'History', 'Alpha.epub')), None))

    def test_one_book_that_fails_does_not_stop_the_others(self):
        no_file = self.on_device('Shelf/Beta.epub', self.ids[1])  # the library has no EPUB for Beta
        fine = self.on_device('Shelf/Alpha.epub', self.ids[0])

        outcome = replace_files(self.device, self.db, [no_file, fine])

        self.assertEqual([w.item for w in outcome.written], [fine])
        self.assertEqual([e[0] for e in outcome.errors], [no_file])
        self.assertIn('no EPUB file', outcome.errors[0][1])
        with open(os.path.join(self.disk, 'Shelf', 'Beta.epub'), 'rb') as f:
            self.assertEqual(f.read(), b'the old copy', 'a failed book keeps what it had')

    def test_a_transfer_that_cannot_finish_leaves_the_old_file_and_no_scrap(self):
        item = self.on_device('Shelf/Alpha.epub', self.ids[0])

        with mock.patch('calibre_zen.books.ondevice.os.replace', side_effect=PermissionError('read-only')):
            outcome = replace_files(self.device, self.db, [item])

        self.assertEqual(outcome.written, [])
        self.assertEqual(len(outcome.errors), 1)
        self.assertEqual(self.files(), ['Shelf/Alpha.epub'], 'the half-written copy is removed')
        with open(os.path.join(self.disk, 'Shelf', 'Alpha.epub'), 'rb') as f:
            self.assertEqual(f.read(), b'the old copy')

    def test_the_library_cover_file_made_for_the_metadata_is_not_left_behind(self):
        item = self.on_device('Shelf/Alpha.epub', self.ids[0])
        seen = []
        real = ondevice.embed_metadata
        with mock.patch.object(ondevice, 'embed_metadata', lambda path, mi, fmt: seen.append(getattr(mi, 'cover', None)) or real(path, mi, fmt)):
            replace_files(self.device, self.db, [item])
        self.assertTrue(all(not c or not os.path.exists(c) for c in seen), seen)

    def test_which_kind_of_device_can_be_written_to(self):
        self.assertIs(ondevice.writer_for(self.device), ondevice.usbms_writer)
        mtp_like = SimpleNamespace(filesystem_cache=object(), put_file=lambda *a: None)
        self.assertIs(ondevice.writer_for(mtp_like), ondevice.mtp_writer)
        self.assertIsNone(ondevice.writer_for(SimpleNamespace()), 'a wireless device has no file to write over')

    def test_an_mtp_file_is_put_over_the_old_one_in_the_old_ones_folder(self):
        item = self.on_device('Shelf/Alpha.epub', self.ids[0])
        item.book.path = 'storage/Shelf/Alpha.epub'
        folder = object()
        old = SimpleNamespace(parent=folder, name='Alpha.epub')
        put = mock.Mock(return_value='placed')
        device = SimpleNamespace(filesystem_cache=SimpleNamespace(resolve_mtp_id_path=lambda p: old if p == item.book.path else None), put_file=put)
        local = os.path.join(self.mkdtemp(), 'x.epub')
        with open(local, 'wb') as f:
            f.write(b'12345')

        self.assertEqual(ondevice.mtp_writer(device, item, local), ('placed', 0))
        parent, name, stream, size = put.call_args.args
        self.assertEqual((parent, name, size), (folder, 'Alpha.epub', 5))
