#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The Format, Folder and Path columns in the list of books on a device: where
they go, what a cell says, and that sorting on one orders the books by it.
"""

from calibre_zen import device_columns
from calibre_zen.tests.base import ZenTestCase, app


class Book:
    def __init__(self, title, lpath):
        self.title, self.title_sorter, self.lpath = title, title, lpath
        self.path = '/media/reader/' + lpath
        self.authors, self.size, self.device_collections = ['A'], 1, []


class TestCells(ZenTestCase):
    def test_format_is_the_extension_in_capitals(self):
        self.assertEqual(device_columns.book_format('Books/Alpha - Ann.azw3'), 'AZW3')
        self.assertEqual(device_columns.book_format('documents/x.Epub'), 'EPUB')
        self.assertEqual(device_columns.book_format('documents/README'), '')
        self.assertEqual(device_columns.book_format(None), '')

    def test_folder_is_the_one_directly_holding_the_book(self):
        self.assertEqual(device_columns.book_folder('Books/Ann Author/Alpha.epub'), 'Ann Author')
        self.assertEqual(device_columns.book_folder('documents/x.pdf'), 'documents')
        self.assertEqual(device_columns.book_folder('x.pdf'), '', 'a book at the root has none')
        self.assertEqual(device_columns.book_folder(''), '')

    def test_the_device_path_is_from_the_root_with_slashes(self):
        b = Book('Alpha', 'Books/Alpha.epub')
        self.assertEqual(device_columns.device_path(b), 'Books/Alpha.epub')
        b.lpath = None
        b.path = 'E:\\Books\\Alpha.epub'
        self.assertEqual(device_columns.device_path(b), 'E:/Books/Alpha.epub', 'no lpath: the full path')

    def test_a_path_reads_from_the_root_in_any_script(self):
        shown = device_columns.display_path('ספרים/דפים מן הים.kepub')
        self.assertEqual(shown, '\u2066ספרים/\u200eדפים מן הים.kepub\u2069')
        self.assertEqual(device_columns.display_path(''), '')

    def test_they_follow_size_in_order_once(self):
        cm, headers = ['inlibrary', 'title', 'size', 'collections'], {}
        device_columns.add_columns(cm, headers)
        device_columns.add_columns(cm, headers)
        self.assertEqual(cm, ['inlibrary', 'title', 'size', 'format', 'folder', 'lpath', 'collections'])
        self.assertEqual(headers, {'format': 'Format', 'folder': 'Folder', 'lpath': 'Path'})


class TestDeviceModel(ZenTestCase):
    def setUp(self):
        app()
        from calibre.devices.usbms.books import BookList
        from calibre.gui2.library.models import DeviceBooksModel

        books = BookList(None, None, None)
        for title, lpath in (('Alpha', 'documents/a.pdf'), ('Beta', 'Books/Bob/b.azw3'), ('Gamma', 'c.epub')):
            books.append(Book(title, lpath))
        self.model = DeviceBooksModel(None)
        self.model.set_database(books)

    def cells(self, key, role=None):
        from qt.core import Qt

        col = self.model.column_map.index(key)
        return [self.model.data(self.model.index(r, col), role or Qt.ItemDataRole.DisplayRole) for r in range(self.model.rowCount())]

    def sort(self, key, ascending=True):
        from qt.core import Qt

        self.model.sort(self.model.column_map.index(key), Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder)

    def test_the_columns_are_there_with_their_headers(self):
        from qt.core import Qt

        cm = self.model.column_map
        self.assertEqual(cm[cm.index('size') + 1 : cm.index('size') + 4], ['format', 'folder', 'lpath'])
        headers = [self.model.headerData(cm.index(k), Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) for k in ('format', 'folder', 'lpath')]
        self.assertEqual(headers, ['Format', 'Folder', 'Path'])

    def test_each_cell_says_what_it_should(self):
        from qt.core import Qt

        self.sort('title')
        self.assertEqual(self.cells('format'), ['PDF', 'AZW3', 'EPUB'])
        self.assertEqual(self.cells('folder'), ['documents', 'Bob', ''])
        from qt.core import Qt as _Qt

        self.assertEqual(self.cells('lpath', _Qt.ItemDataRole.EditRole), ['documents/a.pdf', 'Books/Bob/b.azw3', 'c.epub'])
        self.assertEqual(self.cells('lpath')[2], device_columns.display_path('c.epub'))
        self.assertEqual(self.cells('lpath', Qt.ItemDataRole.ToolTipRole)[0], device_columns.display_path('documents/a.pdf'), 'from the root, not where it is mounted')

    def test_sorting_on_one_orders_the_books_by_it(self):
        self.sort('format')
        self.assertEqual(self.cells('format'), ['AZW3', 'EPUB', 'PDF'])
        self.sort('format', ascending=False)
        self.assertEqual(self.cells('format')[0], 'PDF')
        self.assertEqual(self.model.sorted_on, ('format', False))
        self.sort('folder')
        self.assertEqual(self.cells('folder'), ['', 'Bob', 'documents'])
        from qt.core import Qt

        self.sort('lpath')
        self.assertEqual(self.cells('lpath', Qt.ItemDataRole.EditRole), ['Books/Bob/b.azw3', 'c.epub', 'documents/a.pdf'])

    def test_other_columns_are_still_calibres(self):
        self.sort('title')
        self.assertEqual(self.cells('title')[0], 'Alpha')
