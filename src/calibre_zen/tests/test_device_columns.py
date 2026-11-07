#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The columns this fork adds to the list of books on a device (Format, Folder and
Path from the file name; Series, Tags, Publisher, Published, Rating and
Languages from its metadata): where they go, what a cell says, that sorting on
one orders the books by it, and that the metadata ones start hidden.
"""

from calibre_zen import device_columns
from calibre_zen.tests.base import ZenTestCase, app


class Book:
    def __init__(self, title, lpath, **metadata):
        self.title, self.title_sorter, self.lpath = title, title, lpath
        self.path = '/media/reader/' + lpath
        self.authors, self.size, self.device_collections = ['A'], 1, []
        self.series = self.series_index = self.publisher = self.pubdate = self.rating = None
        self.tags, self.languages = [], []
        self.__dict__.update(metadata)


METADATA = ('series', 'tags', 'publisher', 'pubdate', 'rating', 'languages')


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
        self.assertEqual(cm, ['inlibrary', 'title', 'size', 'format', 'folder', 'lpath', *METADATA, 'collections'])
        self.assertEqual(
            headers,
            {
                'format': 'Format',
                'folder': 'Folder',
                'lpath': 'Path',
                'series': 'Series',
                'tags': 'Tags',
                'publisher': 'Publisher',
                'pubdate': 'Published',
                'rating': 'Rating',
                'languages': 'Languages',
            },
        )

    def test_the_metadata_cells_read_as_the_librarys(self):
        from calibre.utils.date import UNDEFINED_DATE, parse_only_date

        b = Book('Alpha', 'a.epub', series='Saga', series_index=2.0, tags=['b', 'A'], publisher='Pub', rating=7, languages=['heb', 'eng'])
        b.pubdate = parse_only_date('2001-03-15')
        self.assertEqual(device_columns.series_text(b), 'Saga [2]')
        self.assertEqual(device_columns.tags_text(b), 'A, b')
        self.assertEqual(device_columns.publisher_text(b), 'Pub')
        self.assertIn('2001', device_columns.pubdate_text(b))
        self.assertEqual(device_columns.rating_text(b), '★★★⯪'[:3] + device_columns.rating_text(Book('x', 'x', rating=1)))
        self.assertEqual(device_columns.languages_text(b), 'Hebrew, English')
        empty = Book('Beta', 'b.epub', pubdate=UNDEFINED_DATE)
        self.assertEqual([c.text(empty) for c in device_columns.COLUMNS if c.key in METADATA], [''] * len(METADATA))

    def test_a_layout_hides_the_metadata_columns_once(self):
        state = device_columns.hide_new({'hidden_columns': ['authors']})
        self.assertEqual(state['hidden_columns'], ['authors', *METADATA])
        state['hidden_columns'] = ['authors']  # the reader showed them all
        self.assertEqual(device_columns.hide_new(state)['hidden_columns'], ['authors'], 'a column met is left as the reader set it')


class TestDeviceModel(ZenTestCase):
    def setUp(self):
        app()
        from calibre.devices.usbms.books import BookList
        from calibre.gui2.library.models import DeviceBooksModel

        books = BookList(None, None, None)
        from calibre.utils.date import parse_only_date

        for title, lpath, metadata in (
            ('Alpha', 'documents/a.pdf', {'series': 'Saga', 'series_index': 10.0, 'rating': 4, 'pubdate': parse_only_date('2010-01-01')}),
            ('Beta', 'Books/Bob/b.azw3', {'series': 'Saga', 'series_index': 2.0, 'rating': 10}),
            ('Gamma', 'c.epub', {'series': 'Arc', 'series_index': 1.0, 'pubdate': parse_only_date('1999-01-01')}),
        ):
            books.append(Book(title, lpath, **metadata))
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
        self.assertEqual(cm[cm.index('size') + 1 : cm.index('size') + 10], ['format', 'folder', 'lpath', *METADATA])
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
        self.assertEqual(self.cells('lpath', Qt.ItemDataRole.ToolTipRole)[0], '/media/reader/documents/a.pdf')

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

    def test_the_metadata_columns_sort_by_value(self):
        self.sort('series')
        self.assertEqual(self.cells('series'), ['Arc [1]', 'Saga [2]', 'Saga [10]'], 'by name, then by number')
        self.sort('rating', ascending=False)
        self.assertEqual(self.model.data(self.model.index(0, self.model.column_map.index('title'))), 'Beta')
        self.sort('pubdate')
        titles = self.cells('title')
        self.assertEqual(titles, ['Beta', 'Gamma', 'Alpha'], 'no date first, then oldest')

    def test_other_columns_are_still_calibres(self):
        self.sort('title')
        self.assertEqual(self.cells('title')[0], 'Alpha')


class TestDeviceView(ZenTestCase):
    def test_the_metadata_columns_start_hidden_and_collections_keeps_its_editor(self):
        app()
        from calibre.gui2.library.delegates import TextDelegate
        from calibre.gui2.library.views import DeviceBooksView

        view = DeviceBooksView(None)
        hidden = view.get_default_state()['hidden_columns']
        self.assertTrue(set(METADATA) <= set(hidden))
        self.assertFalse({'format', 'folder', 'lpath'} & set(hidden))
        self.assertTrue(all(view.get_state().get(k + '_injected') for k in METADATA))
        col = view.column_map.index('collections')
        self.assertIsInstance(view.itemDelegateForColumn(col), TextDelegate)
