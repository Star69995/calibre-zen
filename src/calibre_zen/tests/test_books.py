#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The built-in Goodreads Updater and Book Cleanup (books/).

Registration is checked against calibre's own plugin lists; the Goodreads
logic against a throwaway library with the custom column; the cleanup rules on
small XHTML documents, then end to end on a tiny epub, ending with
`clean_book` on a library: the EPUB is replaced, the original is kept, a second
run changes nothing.

The bundle runs -OO: nothing here relies on a bare assert.
"""

import os
import re
import shutil
import unittest
import zipfile

from lxml import etree

from calibre_zen import books
from calibre_zen.books.cleanup import Options, clean_document, detect_hyphen_dash
from calibre_zen.books.epub import books_with_original, clean_book, clean_books, clean_epub, delete_originals
from calibre_zen.books.goodreads import (
    LINKED_COLUMN,
    LINKED_COLUMN_HEADING,
    MissingColumnError,
    WrongColumnTypeError,
    create_linked_column,
    update_goodreads_linked,
)
from calibre_zen.tests.base import ZenTestCase, make_library, work_dir

XHTML = 'http://www.w3.org/1999/xhtml'
NAMES = ('Goodreads Updater', 'Book Cleanup')


def document(body: str):
    return etree.fromstring(f'<html xmlns="{XHTML}"><head><title>t</title></head><body>{body}</body></html>'.encode())


def short_library(case: unittest.TestCase, name: str) -> str:
    "A library under the run's directory itself: calibre refuses a path of 75 characters or more."
    path = os.path.join(work_dir(), name)
    case.addCleanup(shutil.rmtree, path, True)
    return make_library(path)


def block_texts(root) -> list[str]:
    return [''.join(e.itertext()) for e in root.iter(f'{{{XHTML}}}p', f'{{{XHTML}}}h2')]


class TestRegistration(ZenTestCase):
    def test_both_are_built_in_and_initialised(self):
        from calibre.customize import ui
        from calibre.customize.builtins import plugins

        self.assertTrue(set(NAMES) <= {p.name for p in plugins})
        self.assertTrue(set(NAMES) <= ui.builtin_names)
        actions = {a.name for a in ui.interface_actions()}
        self.assertTrue(set(NAMES) <= actions, actions)

    def test_the_actions_import_and_name_themselves_like_their_plugins(self):
        from calibre.gui2.actions import InterfaceAction
        from calibre_zen.books import actions

        for base, cls in ((books.GoodreadsUpdaterBase, actions.GoodreadsUpdaterAction), (books.BookCleanupBase, actions.BookCleanupAction)):
            self.assertTrue(issubclass(cls, InterfaceAction))
            self.assertEqual(base.name, cls.name)

    def test_install_twice_adds_nothing(self):
        self.assertTrue(books.install())
        self.assertEqual(books.register(), [])

    def test_an_installed_plugin_of_the_same_name_loses_and_its_file_stays(self):
        from calibre.customize import InterfaceActionBase, ui
        from calibre.customize.builtins import plugins

        class Stub(InterfaceActionBase):
            name = 'Zen Test Stub Action'
            actual_plugin = 'calibre_zen.books.actions:BookCleanupAction'

        zip_path = os.path.join(self.mkdtemp(), 'stub.zip')
        with open(zip_path, 'w') as f:
            f.write('not a real plugin')
        external = Stub(None)
        ui._initialized_plugins.append(external)
        installed = ui.config['plugins']
        installed[Stub.name] = zip_path
        ui.config['plugins'] = installed

        def undo():
            plugins[:] = [p for p in plugins if p is not Stub]
            ui._initialized_plugins[:] = [p for p in ui._initialized_plugins if p.name != Stub.name]
            ui.builtin_names = frozenset(p.name for p in plugins)
            left = ui.config['plugins']
            left.pop(Stub.name, None)
            ui.config['plugins'] = left

        self.addCleanup(undo)

        self.assertEqual(books.register((Stub,)), [Stub.name])
        same_name = [p for p in ui._initialized_plugins if p.name == Stub.name]
        self.assertEqual(len(same_name), 1)
        self.assertIsNot(same_name[0], external)
        self.assertNotIn(Stub.name, ui.config['plugins'])
        self.assertTrue(os.path.exists(zip_path), 'the old plugin file must not be deleted')


class TestGoodreads(ZenTestCase):
    libraries = 0

    def library(self, with_column: bool):
        from calibre.db.legacy import LibraryDatabase

        TestGoodreads.libraries += 1
        path = short_library(self, f'books-g{TestGoodreads.libraries}')
        if with_column:
            db = LibraryDatabase(path)
            db.create_custom_column('goodreads_linked', 'Goodreads linked', 'bool', False)
            db.close()
        db = LibraryDatabase(path)
        self.addCleanup(db.close)
        return db.new_api

    def test_a_library_without_the_column_is_refused(self):
        db = self.library(with_column=False)
        with self.assertRaises(MissingColumnError) as cm:
            update_goodreads_linked(db)
        self.assertIn(LINKED_COLUMN, str(cm.exception))

    def test_the_missing_column_can_be_created(self):
        from calibre.db.legacy import LibraryDatabase

        path = short_library(self, 'books-create')
        db = LibraryDatabase(path)
        create_linked_column(db.new_api)
        db.close()

        db = LibraryDatabase(path)  # calibre sees a new column when the library is opened
        self.addCleanup(db.close)
        meta = db.new_api.field_metadata[LINKED_COLUMN]
        self.assertEqual((meta['datatype'], meta['name']), ('bool', LINKED_COLUMN_HEADING))
        update_goodreads_linked(db.new_api)

    def test_a_column_of_another_type_is_not_replaced(self):
        from calibre.db.legacy import LibraryDatabase

        path = short_library(self, 'books-text')
        db = LibraryDatabase(path)
        db.create_custom_column('goodreads_linked', 'Goodreads linked', 'text', False)
        db.close()
        db = LibraryDatabase(path)
        self.addCleanup(db.close)
        with self.assertRaises(WrongColumnTypeError):
            update_goodreads_linked(db.new_api)

    def test_the_column_follows_the_identifier(self):
        db = self.library(with_column=True)
        ids = sorted(db.all_book_ids())
        db.set_field('identifiers', {ids[0]: {'goodreads': '123'}, ids[1]: {'isbn': '9780000000000'}})

        changed, total = update_goodreads_linked(db)
        self.assertEqual(total, len(ids))
        self.assertEqual(changed, set(ids))  # a new column is unset: every book gets a yes or a no
        values = db.all_field_for(LINKED_COLUMN, ids)
        self.assertIs(values[ids[0]], True)
        self.assertIs(values[ids[1]], False)
        self.assertIs(values[ids[2]], False)

        self.assertEqual(update_goodreads_linked(db), (set(), len(ids)), 'only a change is written')

        db.set_field('identifiers', {ids[1]: {'goodreads': '9'}})
        changed, _total = update_goodreads_linked(db)
        self.assertEqual(changed, {ids[1]})
        self.assertIs(db.all_field_for(LINKED_COLUMN, ids)[ids[1]], True)


class TestCleanupRules(unittest.TestCase):
    def run_rules(self, body: str, **opts):
        root = document(body)
        clean_document(root, Options(**opts))
        return root

    def texts(self, body: str, **opts) -> list[str]:
        return block_texts(self.run_rules(body, **opts))

    def test_punctuation_spacing(self):
        cases = {
            'Focus,I told myself': 'Focus, I told myself',
            'now !” I looked': 'now!” I looked',
            'It was ridiculous.This ship': 'It was ridiculous. This ship',
            '“Moi?”Cherise pressed': '“Moi?” Cherise pressed',
            'on .“David’s coming': 'on. “David’s coming',
            '“ Four?” he said': '“Four?” he said',
            'have been . . . reluctant': 'have been . . . reluctant',  # an ellipsis is left alone
            'Mr. Smith and e.g. Mrs. Jones': 'Mr. Smith and e.g. Mrs. Jones',
        }
        for before, after in cases.items():
            with self.subTest(before):
                self.assertEqual(self.texts(f'<p>{before}</p>'), [after])

    def test_hyphens(self):
        self.assertEqual(self.texts('<p>a crystal- encrusted cell</p>'), ['a crystal-encrusted cell'])
        self.assertEqual(self.texts('<p>pre- and post-war</p>'), ['pre- and post-war'])

    def test_em_dash_follows_the_books_own_style(self):
        self.assertEqual(self.texts('<p>the mark —to remake it.</p><p>No— husband.</p>'), ['the mark—to remake it.', 'No—husband.'])
        self.assertEqual(self.texts('<p>A—B.</p><p>C--D.</p>', dash_style='spaced'), ['A — B.', 'C — D.'])

    def test_a_broken_paragraph_is_joined_and_a_short_one_is_not(self):
        joined = self.texts('<p>“Okay, fine.</p><p>I’ll tell myself it is a costume party.”</p>')
        self.assertEqual(joined, ['“Okay, fine. I’ll tell myself it is a costume party.”'])
        self.assertEqual(self.texts('<p>he gave a half</p><p>wave and left.</p>'), ['he gave a half wave and left.'])
        self.assertEqual(self.texts('<p>It terrified me.</p><p>Focus.</p>'), ['It terrified me.', 'Focus.'])
        # a speech that goes on in a new paragraph opens its quote again
        speech = '<p>“First part of a long speech that is not over yet.</p><p>“Second part.”</p>'
        self.assertEqual(len(self.texts(speech)), 2)

    def test_headings(self):
        root = self.run_rules('<p>Chapter One </p><p>Text goes on and ends the chapter here.” Chapter Two </p><p>More text follows the heading.</p>')
        self.assertEqual([''.join(h.itertext()) for h in root.iter(f'{{{XHTML}}}h2')], ['Chapter One', 'Chapter Two'])
        self.assertEqual(self.texts('<p>She read Chapter Two again and again, slowly</p>'), ['She read Chapter Two again and again, slowly'])

    def test_a_heading_is_never_merged_into_its_neighbour(self):
        # from a real report: "... CHAPTER FOUR ¶ Tazi stood" and "Chapter 1 ¶ WHEN HE LOOKED"
        root = self.run_rules('<p>The long night ended at last, she whispered. CHAPTER FOUR</p><p>Tazi stood in the center of a room.</p>')
        self.assertEqual(block_texts(root), ['The long night ended at last, she whispered.', 'CHAPTER FOUR', 'Tazi stood in the center of a room.'])
        self.assertEqual([''.join(h.itertext()) for h in root.iter(f'{{{XHTML}}}h2')], ['CHAPTER FOUR'])
        for first, second in (
            ('A list of other books by the author Do’Urden Chapter 1', 'WHEN HE LOOKED INSIDE the box'),
            ('The last line of the book is said with a grin', 'about the author'),
            ('A story of the Forgotten Realms, a year of shadows', 'Prologue Three living heroes and a villain'),
            ('Release Date: November, 29th, 2008 and more text', 'Dedication'),
        ):
            with self.subTest(first):
                self.assertEqual(self.texts(f'<p>{first}</p><p>{second}</p>'), [first, second])

    def test_a_quote_the_converter_turned_the_wrong_way_keeps_its_space(self):
        self.assertEqual(self.texts('<p>“And the were-“ the halfling began. “No.”</p>'), ['“And the were-“ the halfling began. “No.”'])
        self.assertEqual(self.texts('<p>it was fastest-“ “No.” she said</p>'), ['it was fastest-“ “No.” she said'])
        self.assertEqual(self.texts('<p>“ Four?” he said</p>'), ['“Four?” he said'])

    def test_a_comma_that_is_a_misread_quote_is_left_alone(self):
        self.assertEqual(self.texts('<p>of escape. ,Come on then, he said</p>'), ['of escape. ,Come on then, he said'])
        self.assertEqual(self.texts('<p>CHAPTER SEVEN, . Later that night</p>'), ['CHAPTER SEVEN, . Later that night'])
        # ...but a comma stuck to the next word moves in one step
        self.assertEqual(self.texts('<p>It was set on ,a raised section</p>'), ['It was set on, a raised section'])

    def test_a_decimal_point_keeps_its_space(self):
        self.assertEqual(self.texts('<p>during the next .04 seconds . No</p>'), ['during the next .04 seconds. No'])

    def test_a_dash_written_as_a_hyphen_is_not_a_split_word(self):
        self.assertEqual(self.texts('<p>he might lead- important information</p>', hyphen_dash=True), ['he might lead- important information'])
        self.assertEqual(self.texts('<p>he might lead- important information</p>'), ['he might lead-important information'])
        quote = ''.join(f'<p>said the-“ {n}.</p>' for n in range(5))
        self.assertTrue(detect_hyphen_dash(block_texts(document(quote))))
        self.assertFalse(detect_hyphen_dash(['a coal- colored mist- filled field, re- entering', 'a word split by a page-']))

    def test_empty_blocks_go_and_images_stay(self):
        root = self.run_rules('<p>one.</p><p/><p> </p><p><img src="o.jpg"/></p><div id="calibre_pb_0"/><p>two.</p>')
        self.assertEqual(block_texts(root), ['one.', '', 'two.'])
        self.assertEqual(len(list(root.iter(f'{{{XHTML}}}img'))), 1, 'an ornament image is part of the design')

    def test_no_double_space_and_a_second_run_changes_nothing(self):
        body = '<p>a  b ,c .  “ d ”  e—  f</p><p>Chapter Three</p><p>x  y ,z</p>'
        root = self.run_rules(body)
        self.assertEqual([t for t in block_texts(root) if '  ' in t or t != t.strip()], [])
        first = etree.tostring(root)
        clean_document(root, Options())
        self.assertEqual(etree.tostring(root), first)

    def test_text_is_never_lost(self):
        body = '<p>Focus,I  told ,myself</p><p>“Okay, fine.</p><p>I’ll go.”</p><p>Chapter Nine</p><p>a crystal- encrusted cell —ok</p>'
        before = block_texts(document(body))
        after = block_texts(self.run_rules(body))
        skeleton = lambda ts: re.sub(r'[-—]+', '—', re.sub(r'\s+', '', ''.join(ts)))
        self.assertEqual(skeleton(before), skeleton(after))


def make_epub(path: str) -> None:
    "A two-chapter epub with the faults of a PDF conversion, and a TOC that knows only chapter one."
    ch1 = (
        f'<html xmlns="{XHTML}"><head><title>��</title></head><body>'
        '<p>Chapter One </p><p/>'
        '<p>I said “Okay,fine .</p><p>It was nothing.”</p>'
        '<p>Then I left the room and closed the door behind me.” Chapter Two </p>'
        '<p>The second chapter starts here and it goes on.</p></body></html>'
    )
    opf = (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Test</dc:title><dc:language>en</dc:language>'
        '<dc:identifier id="id">zen-test-1</dc:identifier></metadata>'
        '<manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
        '<spine toc="ncx"><itemref idref="ch1"/></spine></package>'
    )
    ncx = (
        '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        '<head><meta name="dtb:uid" content="zen-test-1"/></head><docTitle><text>Test</text></docTitle>'
        '<navMap><navPoint id="n1" playOrder="1"><navLabel><text>Chapter One</text></navLabel><content src="ch1.xhtml"/></navPoint></navMap></ncx>'
    )
    container = (
        '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip', zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', container)
        z.writestr('content.opf', opf)
        z.writestr('toc.ncx', ncx)
        z.writestr('ch1.xhtml', ch1.encode('utf-8'))


def epub_blocks(path: str) -> list[list[str]]:
    "Block texts of each html file of an epub, in file-name order."
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.endswith(('.xhtml', '.html')))
        return [block_texts(etree.fromstring(z.read(n))) for n in names]


class TestCleanEpub(ZenTestCase):
    def test_an_epub_end_to_end(self):
        src = os.path.join(self.mkdtemp(), 'in.epub')
        dst = os.path.join(os.path.dirname(src), 'out.epub')
        make_epub(src)

        report = clean_epub(src, dst)
        self.assertTrue(report.changed)
        self.assertIn('file split before chapter heading', report.stats.counts)
        files = epub_blocks(dst)
        self.assertEqual(len(files), 2, 'chapter two has its own file')
        self.assertEqual(files[0][0], 'Chapter One')
        self.assertEqual(files[1][0], 'Chapter Two')
        joined = [t for t in files[0] if t.startswith('I said')]
        self.assertEqual(joined, ['I said “Okay, fine. It was nothing.”'])
        self.assertIn('rebuilt', report.toc_note)
        with zipfile.ZipFile(dst) as z:
            ncx = z.read([n for n in z.namelist() if n.endswith('.ncx')][0]).decode('utf-8')
        self.assertEqual(re.findall(r'<text>(Chapter \w+)</text>', ncx), ['Chapter One', 'Chapter Two'])

        again = clean_epub(dst, os.path.join(os.path.dirname(src), 'again.epub'))
        self.assertFalse(again.changed, again.changed_files)

    def test_a_book_in_the_library_keeps_its_original(self):
        from calibre.db.legacy import LibraryDatabase

        work = self.mkdtemp()
        src = os.path.join(work, 'in.epub')
        make_epub(src)
        db = LibraryDatabase(short_library(self, 'books-clean'))
        self.addCleanup(db.close)
        api = db.new_api
        book_id = sorted(api.all_book_ids())[0]
        self.assertTrue(api.add_format(book_id, 'EPUB', src, run_hooks=False))
        original = api.format(book_id, 'EPUB')

        preview = clean_book(api, book_id, dry_run=True)
        self.assertTrue(preview.changed)
        self.assertEqual(api.format(book_id, 'EPUB'), original)
        self.assertNotIn('ORIGINAL_EPUB', api.formats(book_id))

        clean_book(api, book_id)
        self.assertNotEqual(api.format(book_id, 'EPUB'), original)
        self.assertEqual(api.format(book_id, 'ORIGINAL_EPUB'), original)

        self.assertFalse(clean_book(api, book_id).changed)
        self.assertEqual(api.format(book_id, 'ORIGINAL_EPUB'), original, 'the original is kept once, never overwritten')

        self.assertEqual(clean_book(api, sorted(api.all_book_ids())[1]).skipped, 'no EPUB format')

    def test_the_original_is_kept_only_when_asked_and_can_be_deleted(self):
        from calibre.db.legacy import LibraryDatabase

        src = os.path.join(self.mkdtemp(), 'in.epub')
        make_epub(src)
        db = LibraryDatabase(short_library(self, 'books-orig'))
        self.addCleanup(db.close)
        api = db.new_api
        ids = sorted(api.all_book_ids())[:2]
        for book_id in ids:
            api.add_format(book_id, 'EPUB', src, run_hooks=False)

        self.assertTrue(clean_book(api, ids[0], keep_original=False).changed)
        self.assertNotIn('ORIGINAL_EPUB', api.formats(ids[0]), 'asked not to keep it')
        self.assertTrue(clean_book(api, ids[1]).changed)
        self.assertEqual(books_with_original(api, ids), [ids[1]])

        # an original from an earlier run stays when a later run keeps none
        api.add_format(ids[1], 'EPUB', src, run_hooks=False)
        clean_book(api, ids[1], keep_original=False)
        self.assertEqual(books_with_original(api, ids), [ids[1]])

        cleaned = api.format(ids[1], 'EPUB')
        self.assertEqual(delete_originals(api, ids), ids, 'every id asked about is reported')
        self.assertEqual(books_with_original(api, ids), [])
        self.assertEqual(api.format(ids[1], 'EPUB'), cleaned, 'the cleaned EPUB stays')

    def test_a_job_reports_progress_logs_each_book_and_stops_when_told(self):
        from queue import Queue
        from threading import Event

        from calibre.db.legacy import LibraryDatabase
        from calibre.utils.logging import GUILog

        src = os.path.join(self.mkdtemp(), 'in.epub')
        make_epub(src)
        db = LibraryDatabase(short_library(self, 'books-job'))
        self.addCleanup(db.close)
        api = db.new_api
        ids = sorted(api.all_book_ids())[:2]
        api.add_format(ids[0], 'EPUB', src, run_hooks=False)

        notifications, log = Queue(), GUILog()
        result = clean_books(api, ids, notifications=notifications, abort=Event(), log=log)
        self.assertEqual(result.changed_ids, [ids[0]])
        self.assertEqual(len(result.reports), 2)
        self.assertEqual(result.errors, [])
        self.assertIn('skipped: no EPUB format', log.plain_text)
        fractions = []
        while not notifications.empty():
            fractions.append(notifications.get()[0])
        self.assertEqual(fractions, [0, 0.5, 1])

        stop = Event()
        stop.set()
        stopped = clean_books(api, ids, abort=stop)
        self.assertTrue(stopped.cancelled)
        self.assertEqual(stopped.reports, [])


if __name__ == '__main__':
    unittest.main()
