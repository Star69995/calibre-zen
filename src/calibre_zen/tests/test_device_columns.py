#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The Format column in the list of books on a device: where it goes, what a cell
says, and that sorting on it orders the books by it.
"""

from calibre_zen import device_columns
from calibre_zen.tests.base import ZenTestCase, app


class Book:
    def __init__(self, title, path):
        self.title, self.title_sorter, self.path = title, title, path
        self.authors, self.size, self.device_collections = ['A'], 1, []


class TestBookFormat(ZenTestCase):
    def test_the_extension_in_capitals(self):
        self.assertEqual(device_columns.book_format('/Books/Alpha - Ann.azw3'), 'AZW3')
        self.assertEqual(device_columns.book_format('documents/x.Epub'), 'EPUB')

    def test_no_extension_is_blank(self):
        self.assertEqual(device_columns.book_format('documents/README'), '')
        self.assertEqual(device_columns.book_format(None), '')

    def test_it_follows_size_once(self):
        cm, headers = ['inlibrary', 'title', 'size', 'collections'], {}
        device_columns.add_column(cm, headers, 'Format')
        device_columns.add_column(cm, headers, 'Format')
        self.assertEqual(cm, ['inlibrary', 'title', 'size', 'format', 'collections'])
        self.assertEqual(headers, {'format': 'Format'})


class TestDeviceModel(ZenTestCase):
    def setUp(self):
        app()
        from calibre.devices.usbms.books import BookList
        from calibre.gui2.library.models import DeviceBooksModel

        books = BookList(None, None, None)
        for title, path in (('Alpha', 'a.pdf'), ('Beta', 'b.azw3'), ('Gamma', 'c.epub')):
            books.append(Book(title, path))
        self.model = DeviceBooksModel(None)
        self.model.set_database(books)

    def test_the_column_is_there_with_its_header(self):
        from qt.core import Qt

        col = self.model.column_map.index('format')
        self.assertEqual(self.model.column_map[col - 1], 'size')
        self.assertEqual(self.model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole), 'Format')

    def test_sorting_on_it_orders_the_books(self):
        from qt.core import Qt

        col = self.model.column_map.index('format')
        self.model.sort(col, Qt.SortOrder.AscendingOrder)
        cells = [self.model.data(self.model.index(r, col), Qt.ItemDataRole.DisplayRole) for r in range(3)]
        self.assertEqual(cells, ['AZW3', 'EPUB', 'PDF'])
        self.model.sort(col, Qt.SortOrder.DescendingOrder)
        self.assertEqual(self.model.data(self.model.index(0, col), Qt.ItemDataRole.DisplayRole), 'PDF')
        self.assertEqual(self.model.sorted_on, ('format', False))

    def test_other_columns_are_still_calibres(self):
        from qt.core import Qt

        col = self.model.column_map.index('title')
        self.model.sort(col, Qt.SortOrder.AscendingOrder)
        self.assertEqual(self.model.data(self.model.index(0, col), Qt.ItemDataRole.DisplayRole), 'Alpha')
