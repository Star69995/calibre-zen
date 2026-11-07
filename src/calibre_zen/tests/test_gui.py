#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
End to end: the real main window, offscreen, on a real library.

This builds `calibre.gui2.ui.Main` the way `GuiRunner.start_gui` does, with the
overlay installed, opens a three-book library and drives it: search, select,
read the preview, read the status bar, quit. It is the closest a headless run
gets to a person using the app, and it is where a change to filters/, centre/
or status/ shows up as behaviour rather than as a look.

One window per class: startup is a few seconds, so the tests share it and
each puts the search box back the way it found it.
"""

import os

from calibre_zen.tests import base
from calibre_zen.tests.base import ZenTestCase, process_events, wait_until


class TestMainWindow(ZenTestCase):
    gui = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from calibre.db.legacy import LibraryDatabase
        from calibre.gui2 import gprefs
        from calibre.gui2.main import option_parser
        from calibre.gui2.ui import Main
        from calibre.utils.config import prefs

        cls.library = base.make_library(os.path.join(cls.tmp, 'library'))
        prefs.set('library_path', cls.library)
        # A first run adds the Quick Start Guide to the library; the tests
        # want exactly the books they made.
        gprefs['quick_start_guide_added'] = True
        gprefs['welcome_wizard_was_run'] = True
        opts, _args = option_parser().parse_args(['calibre-zen-test', '--no-update-check'])
        from calibre.constants import ismacos

        # As run_gui_ does: macOS keeps a native menu bar that the bars
        # manager reads back, so it has to exist before initialize().
        actions = tuple(Main.create_application_menubar() if ismacos else Main.get_menubar_actions())
        db = LibraryDatabase(cls.library)
        cls.gui = Main(opts)
        with gprefs:
            cls.gui.initialize(cls.library, db, actions)
        cls.gui.set_exception_handler()
        # Startup finishes on the event loop: the book list fills, the
        # panels attach, the status bar reads the counts.
        ok = wait_until(lambda: cls.model().count() == len(base.BOOKS), timeout_ms=15000)
        if not ok:
            raise RuntimeError(f'the book list never filled: {cls.model().count()} rows')
        process_events(200)

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.gui is not None:
                cls.gui.shutdown(write_settings=False)
                process_events(200)
        finally:
            super().tearDownClass()

    @classmethod
    def model(cls):
        return cls.gui.library_view.model()

    def tearDown(self):
        self.gui.search.clear()
        wait_until(lambda: self.model().count() == len(base.BOOKS))

    # ------------------------------------------------------------ the shell

    def test_window_shows_the_display_name(self):
        from calibre.constants import __appname__, zen_display_name

        title = self.gui.windowTitle()
        self.assertTrue(title.startswith(zen_display_name), title)
        self.assertFalse(title.startswith(__appname__), title)

    def test_overlay_parts_are_in_place(self):
        from calibre_zen.centre.layout import ZenCentre
        from calibre_zen.filters.panel import FilterPanel
        from calibre_zen.status.bar import ZenStatusBar

        panel = getattr(self.gui.tags_view, 'zen_filter_panel', None)
        self.assertIsInstance(panel, FilterPanel, 'the filter panel did not install')
        self.assertFalse(self.gui.tags_view.isVisibleTo(self.gui), 'the tag browser tree is still visible')
        self.assertIsInstance(getattr(self.gui, 'zen_centre', None), ZenCentre, 'the centre did not install')
        self.assertIsInstance(getattr(self.gui, 'zen_status', None), ZenStatusBar, 'the status bar did not install')

    def test_the_device_toolbar_is_the_main_one_plus_the_device_buttons(self):
        bm = self.gui.bars_manager
        plain, device = bm.main_bars
        names = {ac: name for name, ia in self.gui.iactions.items() for ac in (ia.qaction,)}

        def books(bar):
            return [names[ac] for ac in bar.added_actions if ac in names]

        added = ('Send To Device', 'Add To Library')
        self.assertNotIn('Send To Device', books(plain))
        self.assertEqual([n for n in books(device) if n not in added], books(plain), 'the same buttons, in the same order')
        on_device = books(device)
        self.assertEqual(on_device[on_device.index('Send To Device') + 1], 'Add To Library', 'the two share a place')
        self.assertTrue(any(ac in device.added_actions for ac in self.gui.location_manager.all_actions), 'the Location manager')

    def test_send_to_device_turns_into_add_to_library_on_the_device(self):
        send = self.gui.iactions['Send To Device']
        add = self.gui.iactions['Add To Library']
        self.addCleanup(lambda: [ac.location_selected('library') for ac in (send, add)])
        for ac in (send, add):
            ac.location_selected('main')
        self.assertFalse(send.qaction.isVisible())
        self.assertTrue(add.qaction.isVisible() and add.qaction.isEnabled())
        for ac in (send, add):
            ac.location_selected('library')
        self.assertTrue(send.qaction.isVisible() and send.qaction.isEnabled())
        self.assertFalse(add.qaction.isVisible())

    def test_preferences_calls_the_device_toolbar_what_it_is(self):
        from calibre.gui2.preferences.toolbar import ConfigWidget

        w = ConfigWidget()
        w.genesis(self.gui)
        labels = [w.what.itemText(i) for i in range(w.what.count())]
        self.assertIn('Added to the main toolbar when a device is connected', labels)
        self.assertNotIn('The main toolbar when a device is connected', labels)

    def test_the_built_in_book_tools_are_actions_with_icons(self):
        "books/: Goodreads Updater and Book Cleanup are in the window like calibre's own actions."
        for name in ('Goodreads Updater', 'Book Cleanup'):
            with self.subTest(name):
                self.assertIn(name, self.gui.iactions)
                self.assertFalse(self.gui.iactions[name].qaction.icon().isNull(), 'no icon')
        menu = self.gui.iactions['Book Cleanup'].qaction.menu()
        self.assertEqual([ac.text() for ac in menu.actions()], ['Clean selected books', 'Preview changes (modifies nothing)'])

    def test_connect_share_offers_to_keep_sharing(self):
        menu = self.gui.iactions['Connect Share'].share_conn_menu
        ac = getattr(menu, 'keep_sharing_action', None)
        self.assertIsNotNone(ac, 'Close and keep sharing is not in the Connect/share menu')
        self.assertEqual(ac.text(), 'Close and keep sharing')
        self.assertFalse(ac.icon().isNull(), 'every other item in the menu has an icon')
        items = menu.actions()
        # With the content server's own items, above the wireless device's.
        self.assertEqual(items.index(ac) + 1, items.index(menu.control_smartdevice_action))

    def test_the_test_window_leaves_a_running_window_s_socket_alone(self):
        "tests/main.py isolate_ipc: a run beside an open calibre-zen must not take its socket."
        from calibre.constants import __appname__

        address = self.gui.listener.address
        self.assertIn(__appname__, address)
        if address.startswith('\0'):
            self.assertTrue(address[1:].startswith('zentest'), address)
        elif not address.startswith('\\\\'):
            work = os.environ['CALIBRE_ZEN_TEST_DIR']
            self.assertEqual(os.path.realpath(os.path.dirname(address)), os.path.realpath(work))

    def test_a_window_asks_the_tray_for_its_library(self):
        import calibre.gui2.main as gm

        self.assertIn('wrap_run_gui', gm.run_gui.__qualname__, 'a window opened from the Dock would not ask the tray')

    def test_preferences_offers_to_restart_headless(self):
        menu = self.gui.iactions['Preferences'].qaction.menu()
        ac = getattr(menu, 'restart_headless_action', None)
        self.assertIsNotNone(ac, 'Restart in headless mode is not in the Preferences menu')
        self.assertEqual(ac.text(), 'Restart in headless mode')
        texts = [a.text() for a in menu.actions()]
        # Right after calibre's own restarts.
        self.assertEqual(texts.index(ac.text()) - 1, texts.index('Restart ignoring third party plugins'))

    # ------------------------------------------------- settings while jobs run

    def running_job(self):
        "A job the manager counts as running, removed again when the test ends."
        from calibre_zen.tests.test_busy import Job

        job = Job('Convert Alpha', 40)
        manager = self.gui.job_manager
        manager.jobs.append(job)
        self.addCleanup(manager.jobs.remove, job)
        self.assertTrue(manager.has_jobs())
        return job

    # ------------------------------------------------- the column picker

    def columns_view(self):
        from calibre_zen.centre import table

        view = self.gui.library_view
        self.addCleanup(lambda: view.apply_state(table.arrange(view.get_default_state(), view.column_map)))
        return view

    def test_the_picker_offers_the_columns_that_do_something_and_pins_details(self):
        from calibre_zen.centre import columns

        view = self.columns_view()
        found = columns.columns_for(view)
        keys = [c.key for c in found]
        self.assertNotIn('authors', keys, 'folded into Details')
        self.assertNotIn('series', keys)
        self.assertNotIn('ondevice', keys)
        self.assertEqual(keys[0], 'title', 'the shown ones come first, Details in front')
        self.assertTrue(found[0].locked and found[0].visible)
        self.assertEqual(found[0].title, 'Details')

    def test_a_tick_hides_and_shows_a_column_through_calibre(self):
        from calibre_zen.centre import columns

        view = self.columns_view()
        shown = [c.key for c in columns.columns_for(view) if c.visible and not c.locked]
        self.assertTrue(shown, 'no column to hide')
        key = shown[0]
        columns.set_visible(view, key, False)
        self.assertFalse(next(c for c in columns.columns_for(view) if c.key == key).visible)
        columns.set_visible(view, key, True)
        self.assertTrue(next(c for c in columns.columns_for(view) if c.key == key).visible)

    def test_the_arrows_move_a_column_but_never_in_front_of_details(self):
        from calibre_zen.centre import columns

        view = self.columns_view()
        shown = [c.key for c in columns.columns_for(view) if c.visible]
        self.assertGreaterEqual(len(shown), 3, shown)
        first, second = shown[1], shown[2]
        self.assertTrue(columns.move(view, second, -1))
        now = [c.key for c in columns.columns_for(view) if c.visible]
        self.assertEqual(now[1:3], [second, first])
        self.assertFalse(columns.move(view, now[1], -1), 'Details is in front and stays there')
        self.assertFalse(columns.move(view, 'title', 1), 'and does not move')

    def test_reset_brings_back_the_default_columns(self):
        from calibre_zen.centre import columns

        view = self.columns_view()
        before = [c.key for c in columns.columns_for(view) if c.visible]
        columns.set_visible(view, before[1], False)
        columns.reset(view)
        after = [c.key for c in columns.columns_for(view) if c.visible]
        self.assertIn(before[1], after, 'the column that was hidden is back')
        self.assertEqual(after[0], 'title')

    def device_view(self):
        "The device list, holding three books, as if a reader were connected."
        from calibre.devices.usbms.books import Book, BookList

        books = BookList(None, None, None)
        for title, path in (('Alpha', 'a.pdf'), ('Beta', 'b.azw3'), ('Gamma', 'c.epub')):
            books.append(Book('/dev/', path, other=None))
            # in_library and its date are set by calibre when it matches the device to the library.
            books[-1].title, books[-1].authors, books[-1].in_library, books[-1].datetime = title, ['Ann Author'], None, (2026, 1, 1, 0, 0, 0, 0, 0, 0)
        view = self.gui.memory_view
        view.set_database(books)
        self.addCleanup(lambda: view.apply_state(view.get_default_state()))
        return view

    def test_on_a_device_every_column_is_offered_and_format_is_one(self):
        from calibre_zen.centre import columns

        view = self.device_view()
        found = {c.key: c for c in columns.columns_for(view)}
        for key in ('format', 'folder', 'lpath'):
            self.assertIn(key, found)
            self.assertTrue(found[key].visible, f'{key} is shown from the start')
        self.assertIn('authors', found, 'nothing is folded on a device')
        self.assertNotIn('inlibrary', found)
        self.assertFalse(any(c.locked for c in found.values()))
        self.assertEqual(found['title'].title, 'Title')

    def test_on_a_device_a_column_hides_moves_and_resets(self):
        from calibre_zen.centre import columns

        view = self.device_view()
        columns.set_visible(view, 'format', False)
        self.assertFalse(next(c for c in columns.columns_for(view) if c.key == 'format').visible)
        shown = [c.key for c in columns.columns_for(view) if c.visible]
        self.assertTrue(columns.move(view, shown[1], -1))
        self.assertEqual([c.key for c in columns.columns_for(view) if c.visible][:2], [shown[1], shown[0]])
        columns.reset(view)
        self.assertTrue(next(c for c in columns.columns_for(view) if c.key == 'format').visible)
        self.assertFalse(columns.can_add(view)[0], 'a device list takes no custom columns')

    def test_the_button_acts_on_the_list_in_view(self):
        button = self.gui.zen_centre.toolbar.columns
        view = self.device_view()
        self.addCleanup(lambda: self.gui.location_manager.location_selected.emit('library'))
        self.gui.stack.setCurrentIndex(1)
        self.gui.location_manager.location_selected.emit('main')
        self.assertIs(button.view(), view)
        self.assertTrue(button.isVisibleTo(self.gui.zen_centre))
        button.toggle_panel()
        self.addCleanup(button.panel.close)
        self.assertIs(button.panel.view, view)

    def test_the_panel_searches_and_follows_a_tick(self):
        from calibre_zen.centre import columns

        self.columns_view()
        button = self.gui.zen_centre.toolbar.columns
        button.toggle_panel()
        self.addCleanup(button.panel.close)
        panel = button.panel
        self.assertGreater(len(panel.findChildren(columns.ColumnRow)), 1)
        panel.search.setText('zzzz-nothing')
        self.assertEqual(len(panel.findChildren(columns.ColumnRow)), 0)
        panel.search.setText('')
        rows = {r.column.key: r for r in panel.findChildren(columns.ColumnRow)}
        key = next(k for k, r in rows.items() if r.check.isEnabled())
        rows[key].check.setChecked(not rows[key].column.visible)
        again = {r.column.key: r for r in panel.findChildren(columns.ColumnRow)}
        self.assertNotEqual(again[key].column.visible, rows[key].column.visible)

    def test_the_button_is_there_for_the_table_only(self):
        from unittest import mock

        button = self.gui.zen_centre.toolbar.columns
        with mock.patch.object(self.gui.grid_view_button, 'isChecked', return_value=True):
            button.refresh()
            self.assertTrue(button.isHidden())
        with mock.patch.object(self.gui.grid_view_button, 'isChecked', return_value=False):
            button.refresh()
            self.assertFalse(button.isHidden())

    # ------------------------------------------------- jobs in the status bar

    def test_the_jobs_segment_opens_a_panel_with_each_job(self):
        from calibre_zen.status.jobs_panel import JobRow

        self.running_job()
        segment = self.gui.zen_status.jobs
        segment.refresh()
        segment.toggle_panel()
        self.addCleanup(segment.panel.close)
        panel = segment.panel
        self.assertTrue(panel.isVisible())
        rows = panel.findChildren(JobRow)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].state.text(), '40%')
        self.assertEqual(rows[0].bar.value(), 40)
        self.assertIn('Convert Alpha', rows[0].name.text())
        self.assertTrue(rows[0].stop.isEnabled())
        segment.toggle_panel()
        self.assertFalse(panel.isVisible(), 'a second click puts it away')

    def test_the_panel_follows_a_job_without_being_rebuilt(self):
        job = self.running_job()
        segment = self.gui.zen_status.jobs
        segment.toggle_panel()
        self.addCleanup(segment.panel.close)
        row = segment.panel.rows[0]
        job.percent = 75
        segment.panel.refresh()
        self.assertIs(segment.panel.rows[0], row)
        self.assertEqual(row.state.text(), '75%')

    def test_the_panel_says_so_when_nothing_runs(self):
        from qt.core import QLabel

        segment = self.gui.zen_status.jobs
        segment.toggle_panel()
        self.addCleanup(segment.panel.close)
        self.assertEqual(segment.panel.rows, [])
        self.assertIsNotNone(segment.panel.findChild(QLabel, 'zenJobsNone'))

    def test_preferences_carries_the_same_segment_and_it_shows_with_a_job(self):
        from calibre.gui2.preferences.main import Preferences

        d = Preferences(self.gui)
        self.addCleanup(d.deleteLater)
        strip = d.zen_jobs
        self.assertTrue(strip.isHidden(), 'nothing to see, nothing shown')
        self.running_job()
        strip.refresh()
        self.assertFalse(strip.isHidden())
        self.assertIn('40%', strip.text())

    def test_the_preferences_overview_needs_no_scrolling(self):
        from calibre.gui2 import gprefs
        from calibre.gui2.preferences.main import Preferences

        # A size saved by an earlier, smaller dialog must not leave the grid cut off.
        gprefs.pop('preferences dialog geometry', None)
        d = Preferences(self.gui)
        self.addCleanup(d.deleteLater)
        d.resize(930, 560)
        d.show()
        self.addCleanup(d.close)
        process_events(200)
        self.assertEqual(d.browser.verticalScrollBar().maximum(), 0)

    def test_preferences_opens_while_a_job_runs(self):
        from unittest import mock

        self.running_job()
        opened = []

        class Dialog:
            do_restart = False
            run_wizard_requested = mock.MagicMock()

            def __init__(self, *args, **kwargs):
                opened.append(args)

            def exec(self):
                return 0

        with mock.patch('calibre.gui2.actions.preferences.Preferences', Dialog):
            self.gui.iactions['Preferences'].do_config()
        self.assertEqual(len(opened), 1, 'calibre refused to open Preferences')
        self.assertTrue(self.gui.job_manager.has_jobs(), 'the door was left open for everything else')

    def test_a_page_that_clashes_is_held_back_with_the_job_named(self):
        from unittest import mock

        from calibre.gui2.preferences.main import Preferences

        self.running_job()
        d = Preferences(self.gui, initial_plugin=('Advanced', 'Plugins'))
        self.addCleanup(d.deleteLater)
        d.changed_signal()
        with mock.patch.object(Preferences, 'zen_busy_notice') as notice:
            d.accept()
        notice.assert_called_once()
        self.assertIn('plugin', notice.call_args.args[0])
        self.assertEqual(d.stack.currentIndex(), 1, 'the person was left on the page, edits intact')

    def test_an_unchanged_page_is_never_held_back(self):
        from unittest import mock

        from calibre.gui2.preferences.main import Preferences

        self.running_job()
        d = Preferences(self.gui, initial_plugin=('Advanced', 'Plugins'))
        self.addCleanup(d.deleteLater)
        with mock.patch.object(Preferences, 'zen_busy_notice') as notice:
            d.commit()
        notice.assert_not_called()

    def test_app_sheet_and_palette_are_applied(self):
        from qt.core import QPalette

        sheet = base.app().styleSheet()
        self.assertGreater(len(sheet), 1000)
        # The overlay's palette, not Fusion's: Window and Base are distinct roles in every scheme.
        pal = base.app().palette()
        self.assertNotEqual(pal.color(QPalette.ColorRole.Window).name(), pal.color(QPalette.ColorRole.Base).name())

    # ------------------------------------------------------------ the books

    def test_library_loaded_every_book(self):
        titles = sorted(self.model().db.title(r) for r in range(self.model().count()))
        self.assertEqual(titles, sorted(b[0] for b in base.BOOKS))

    def test_status_bar_reads_the_count(self):
        counts = self.gui.zen_status.counts
        self.assertTrue(wait_until(lambda: str(len(base.BOOKS)) in counts.text()), counts.text())
        self.assertIn('book', counts.text())

    def test_search_narrows_the_list_and_the_status(self):
        self.gui.search.set_search_string('title:Alpha')
        self.assertTrue(wait_until(lambda: self.model().count() == 1), f'{self.model().count()} rows after search')
        self.assertEqual(self.model().db.title(0), 'Alpha')
        counts = self.gui.zen_status.counts
        self.assertTrue(wait_until(lambda: '1 of 3' in counts.text()), counts.text())

    def test_search_by_tag(self):
        self.gui.search.set_search_string('tags:fiction')
        self.assertTrue(wait_until(lambda: self.model().count() == 2), f'{self.model().count()} rows')

    def test_selecting_a_book_fills_the_preview(self):
        view = self.gui.library_view
        preview = self.gui.zen_centre.preview
        view.set_current_row(0)
        expected = self.model().db.title(0)
        self.assertTrue(wait_until(lambda: preview.title.text() == expected), f'preview shows {preview.title.text()!r}, wanted {expected!r}')
        self.assertTrue(preview.authors.text())
        view.set_current_row(1)
        expected = self.model().db.title(1)
        self.assertTrue(wait_until(lambda: preview.title.text() == expected), f'preview did not follow the selection: {preview.title.text()!r}')

    def double_click(self, name: str, x: int | None = None):
        """
        Double-click row 0's `name` cell as a mouse would, and return the editor
        that opened, closed again by the cleanup without writing anything.
        `x` is how far into the cell to click; the middle when not given.
        """
        from qt.core import QAbstractItemDelegate, QAbstractItemView, QCoreApplication, QEvent, QMouseEvent, QPointF, Qt

        view = self.gui.library_view
        self.gui.show()
        self.addCleanup(self.gui.hide)
        process_events(100)
        index = self.model().index(0, view.column_map.index(name))
        view.scrollTo(index)
        rect = view.visualRect(index)
        self.assertTrue(rect.isValid(), f'the {name} column is not on screen')
        viewport = view.viewport()
        pos = QPointF(rect.center()) if x is None else QPointF(rect.left() + x, rect.center().y())
        left, none = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        # What a real double-click delivers: press, release, double-click, release.
        for kind, buttons in (
            (QEvent.Type.MouseButtonPress, left),
            (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
            (QEvent.Type.MouseButtonDblClick, left),
            (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
        ):
            QCoreApplication.sendEvent(viewport, QMouseEvent(kind, pos, QPointF(viewport.mapToGlobal(pos)), left, buttons, none))
        self.assertTrue(wait_until(lambda: view.state() == QAbstractItemView.State.EditingState, timeout_ms=2000), f'no editor opened on {name}')
        editor = view.indexWidget(index) or view.focusWidget()

        def close():
            view.closeEditor(editor, QAbstractItemDelegate.EndEditHint.RevertModelCache)
            process_events(50)

        self.addCleanup(close)
        return editor

    def test_double_click_edits_a_cell(self):
        "A double-click opens the cell's editor; the slow second click no longer does."
        from qt.core import QAbstractItemView

        triggers = self.gui.library_view.editTriggers()
        self.assertTrue(triggers & QAbstractItemView.EditTrigger.DoubleClicked)
        self.assertFalse(triggers & QAbstractItemView.EditTrigger.SelectedClicked)
        self.double_click('tags')

    def test_double_click_opens_the_stars_without_rating(self):
        "The click that opens the star editor must not also land on a star."
        from calibre.gui2.widgets2 import RatingEditor

        db = self.model().db.new_api
        book_id = self.model().id(0)
        before = db.field_for('rating', book_id)
        editor = self.double_click('rating', x=12)  # over the first star
        self.assertIsInstance(editor, RatingEditor)
        process_events(50)
        self.assertEqual(editor.rating_value, before or 0)

    def test_double_click_opens_a_date(self):
        from qt.core import QDateTimeEdit

        self.assertIsInstance(self.double_click('timestamp'), QDateTimeEdit)

    def test_double_click_default_is_ours_but_still_a_tweak(self):
        "The default moved, in the text Preferences reads, so choosing the viewer can be saved."
        from calibre.utils.config_base import default_tweaks_raw, parse_python_tweaks, tweaks
        from calibre_zen.centre import clicks

        self.assertEqual(tweaks[clicks.TWEAK], clicks.OURS)
        self.assertEqual(parse_python_tweaks(default_tweaks_raw())[clicks.TWEAK], clicks.OURS)
        self.assertIn(f'# Default: {clicks.OURS}.', default_tweaks_raw())

    def test_double_click_on_a_cover_still_reads(self):
        "The grid reads the same tweak; with our default a cover still opens the book."
        from unittest import mock

        from calibre.gui2.library import alternate_views

        index = self.model().index(0, 0)
        actions = self.gui.iactions
        with mock.patch.object(actions['View'], 'view_triggered') as view, mock.patch.object(actions['Edit Metadata'], 'edit_metadata') as edit:
            alternate_views.double_click_action(index)
        view.assert_called_once_with(index)
        edit.assert_not_called()

    def test_filter_panel_lists_the_tags(self):
        "The panel reads the same TagsModel as the tree: the library's tags are in it."
        from qt.core import QAbstractItemModel

        panel = self.gui.tags_view.zen_filter_panel
        panel.attach()
        process_events(100)
        model = self.gui.tags_view.model()
        self.assertIsInstance(model, QAbstractItemModel)
        texts = set()

        def walk(parent):
            for r in range(model.rowCount(parent)):
                idx = model.index(r, 0, parent)
                texts.add(idx.data() or '')
                walk(idx)

        from qt.core import QModelIndex

        walk(QModelIndex())
        for tag in ('fiction', 'history'):
            self.assertTrue(any(t.startswith(tag) for t in texts), f'{tag!r} not in the tag model: {sorted(texts)[:20]}')

    # ---------------------------------------------------- the metadata editor

    def editor_dialog(self, rows=None):
        """Open the real editor without entering its blocking exec() loop."""
        from calibre_zen.editor.dialog import MetadataSingleDialogZen

        db = self.gui.current_db
        if rows is None:
            rows = range(self.model().count())
        d = MetadataSingleDialogZen(db, self.gui, editing_multiple=False)

        def cleanup():
            d.done(0)
            d.break_cycles()
            d.deleteLater()
            process_events()

        self.addCleanup(cleanup)
        d.id_list = [db.id(row) for row in rows]
        d.current_row = 0
        d.set_current_callback = None
        d.do_one(apply_changes=False)
        d.show()
        process_events()
        return d

    def test_editor_registration(self):
        from calibre.gui2 import gprefs
        from calibre.gui2.metadata import single
        from calibre_zen.editor.dialog import MetadataSingleDialogZen

        self.assertIs(single.editors['zen'], MetadataSingleDialogZen)
        self.assertEqual(gprefs.defaults['edit_metadata_single_layout'], 'zen')

    def test_editor_tabs_and_default_tab(self):
        d = self.editor_dialog()
        self.assertEqual(d.objectName(), 'zenMetadataEditor')
        self.assertIs(d.zen_tabs, d.central_widget)
        self.assertEqual(d.zen_tabs.count(), 3)
        labels = [' '.join(d.zen_tabs.tabText(i).replace('&', '').split()) for i in range(3)]
        self.assertEqual(labels, ['Details', 'Description', 'Cover files'])
        self.assertEqual(d.zen_tabs.currentIndex(), d.DETAILS)

    def test_editor_every_field_is_on_a_tab(self):
        d = self.editor_dialog()
        fields = (
            'title',
            'authors',
            'series',
            'series_index',
            'tags',
            'rating',
            'publisher',
            'pubdate',
            'languages',
            'identifiers',
            'cover',
            'comments',
            'formats_manager',
            'title_sort',
            'author_sort',
            'timestamp',
        )
        pages = [d.zen_tabs.widget(i) for i in range(d.zen_tabs.count())]
        for name in fields:
            with self.subTest(field=name):
                widget = getattr(d, name)
                self.assertTrue(any(page.isAncestorOf(widget) for page in pages), f'{name} is outside the editor tabs')

    def test_editor_no_stray_widgets_or_clear_buttons(self):
        from qt.core import Qt, QWidget

        d = self.editor_dialog()
        footer = d.findChild(QWidget, 'zenEditorFooter')
        self.assertIsNotNone(footer)
        for widget in d.findChildren(QWidget, '', Qt.FindChildOption.FindDirectChildrenOnly):
            with self.subTest(widget=widget.objectName() or type(widget).__name__):
                if widget.isVisible():
                    self.assertTrue(widget is d.zen_tabs or widget is footer or footer.isAncestorOf(widget))
        for button in (
            d.clear_series_button,
            d.clear_ratings_button,
            d.clear_tags_button,
            d.clear_identifiers_button,
            d.publisher.clear_button,
        ):
            with self.subTest(button=button.toolTip()):
                self.assertFalse(button.isVisible())

    def test_editor_sorts_fold(self):
        d = self.editor_dialog()
        self.assertFalse(d.zen_sorts_body.isVisible())
        self.assertFalse(d.zen_sorts_toggle.isChecked())
        d.zen_sorts_toggle.click()
        process_events()
        self.assertTrue(d.zen_sorts_body.isVisible())

    def test_editor_position_and_navigation(self):
        d = self.editor_dialog()
        titles = [self.gui.current_db.new_api.field_for('title', book_id) for book_id in d.id_list]
        self.assertEqual(d.zen_position.text(), '1 of 3')
        self.assertEqual(d.title.current_val, titles[0])
        d.next_button.click()
        process_events()
        self.assertEqual(d.current_row, 1)
        self.assertEqual(d.title.current_val, titles[1])
        self.assertEqual(d.zen_position.text(), '2 of 3')
        d.prev_button.click()
        process_events()
        self.assertEqual(d.current_row, 0)
        self.assertEqual(d.title.current_val, titles[0])
        self.assertEqual(d.zen_position.text(), '1 of 3')

    def test_editor_cover_files_and_save_button(self):
        from qt.core import QDialogButtonBox

        d = self.editor_dialog(rows=[0])
        self.assertFalse(d.zen_position.isVisible())
        self.assertTrue(d.zen_tabs.widget(d.FILES).isAncestorOf(d.data_files_button))
        self.assertIsNotNone(d.zen_cover_menu_button.menu())
        self.assertIsNotNone(d.zen_formats_label)
        self.assertEqual(d.button_box.button(QDialogButtonBox.StandardButton.Ok).text().replace('&', ''), 'Save')
        hint = d.sizeHint()
        screen_size = d.screen().availableSize()
        self.assertEqual((hint.width(), hint.height()), (min(880, screen_size.width()), min(640, screen_size.height())))

    def test_editor_save_round_trip(self):
        db = self.gui.current_db
        alpha_row = next(row for row in range(self.model().count()) if db.title(row) == 'Alpha')
        d = self.editor_dialog(rows=[alpha_row])
        book_id = d.id_list[0]
        try:
            d.title.current_val = 'Alpha Edited'
            d.accept()
            self.assertEqual(db.new_api.field_for('title', book_id), 'Alpha Edited')
        finally:
            db.new_api.set_field('title', {book_id: 'Alpha'})
            self.model().refresh_ids([book_id])
            process_events()

    def test_editor_preferences_choice(self):
        from qt.core import QComboBox

        from calibre.gui2 import gprefs
        from calibre.gui2.preferences.look_feel_tabs.edit_metadata import EditMetadataTab

        class FakeTab:
            def __init__(self):
                self.opt_edit_metadata_single_layout = QComboBox()
                self.settings = {}

            def register_setting(self, setting):
                self.settings[setting.name] = setting
                return setting

        fake = FakeTab()
        setting = EditMetadataTab.register(fake, 'edit_metadata_single_layout', gprefs, choices=[('Default', 'default')])
        self.assertIs(setting, fake.settings['edit_metadata_single_layout'])
        self.assertIn(('Compact (calibre-zen)', 'zen'), setting.choices)
        self.assertIn(('Default', 'default'), setting.choices)

    def test_view_menu_offers_the_cover_shape(self):
        switcher = self.gui.zen_centre.toolbar.switcher
        switcher.build_menu()
        menus = {a.text(): a.menu() for a in switcher.menu_.actions() if a.menu() is not None}
        self.assertIn('Cover shape', menus)
        self.assertEqual([a.text() for a in menus['Cover shape'].actions()], ['Uniform', 'Natural'])

    def test_a_book_without_a_cover_is_ringed_when_selected(self):
        "Issue #29: a coverless tile drew no fill and no ring, so selecting it showed nothing."
        from unittest import mock

        from qt.core import QItemSelectionModel

        from calibre_zen.centre import tiles

        av = self.gui.library_view.alternate_views
        av.show_view('grid')
        self.addCleanup(av.show_view, None)
        view = self.gui.grid_view
        view.resize(900, 600)
        cache = view.delegate.cover_cache
        db = self.gui.current_db
        ids = [db.id(row) for row in range(self.model().count())]
        # The test library has no covers at all: every thumbnail renders null.
        if not wait_until(lambda: all(cache.thumbnail_as_pixmap(i) is not None for i in ids), timeout_ms=10000):
            self.fail('the grid never rendered its thumbnails')
        sm = view.selectionModel()
        sm.select(view.model().index(0, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.addCleanup(sm.clearSelection)

        rings = []
        real = tiles.draw_ring
        with mock.patch.object(tiles, 'draw_ring', lambda p, rect, selected, hovered: rings.append(selected) or real(p, rect, selected, hovered)):
            view.viewport().grab()
        self.assertIn(True, rings, 'the selected book without a cover has no ring')
        self.assertEqual(rings.count(True), 1, 'only the selected tile is ringed as selected')

    def test_a_book_without_a_cover_gets_a_stand_in(self):
        "In a light scheme a coverless tile was near-white text on white: it gets a cover of its own instead."
        from qt.core import QPalette

        from calibre.gui2 import qapplication_or_fail

        av = self.gui.library_view.alternate_views
        av.show_view('grid')
        self.addCleanup(av.show_view, None)
        view = self.gui.grid_view
        cache = view.delegate.cover_cache
        db = self.gui.current_db.new_api
        book_id = self.gui.current_db.id(0)
        if not wait_until(lambda: cache.thumbnail_as_pixmap(book_id) is not None, timeout_ms=10000):
            self.fail('the grid never rendered the thumbnail')

        pixmap = cache.thumbnail_as_pixmap(book_id)
        self.assertFalse(pixmap.isNull(), 'a book without a cover still has no thumbnail')
        self.assertEqual((pixmap.width(), pixmap.height()), tuple(cache.thumbnail_size), 'the stand-in is not the size of a cover')
        self.assertEqual(cache.thumbnail_as_pixmap(book_id).cacheKey(), pixmap.cacheKey(), 'the stand-in is redrawn on every paint')

        title = db.field_for('title', book_id)
        self.addCleanup(db.set_field, 'title', {book_id: title})
        db.set_field('title', {book_id: 'A New Title'})
        self.assertNotEqual(cache.thumbnail_as_pixmap(book_id).cacheKey(), pixmap.cacheKey(), 'an edited title kept the old stand-in')

        # calibre's own text on the grid -- the title under each cover -- is in
        # the theme's text colour, not one picked for calibre's grey background.
        text = qapplication_or_fail().palette().color(QPalette.ColorRole.Text)
        self.assertEqual(view.palette().color(QPalette.ColorRole.Text), text)
        self.assertEqual(view.delegate.highlight_color, text)

    # ------------------------------------------------ Preferences -> Look & feel

    def look_and_feel_dialog(self):
        from calibre.gui2.preferences.main import Preferences

        d = Preferences(self.gui, initial_plugin=('Interface', 'Look & Feel'))
        self.addCleanup(d.deleteLater)
        return d

    def test_look_and_feel_opens_on_the_notice(self):
        from calibre_zen import lookfeel

        d = self.look_and_feel_dialog()
        page = d.showing_widget
        notice = page.zen_notice
        self.assertIsInstance(notice, lookfeel.Notice)
        self.assertIn('clash', notice.text.text())
        self.assertIn('Calibre Zen', notice.reset.text())
        grid = page.layout()
        row, column, _rows, columns = grid.getItemPosition(grid.indexOf(notice))
        self.assertEqual((row, column), (0, 0))
        self.assertEqual(columns, grid.columnCount(), 'across the whole page')
        self.assertEqual(grid.getItemPosition(grid.indexOf(page.tabWidget))[0], 1, 'the page moved down a row')
        self.assertIs(lookfeel.preferences_dialog(page), d)

    def test_look_and_feel_reset_leaves_without_committing(self):
        "After a reset the page still shows the old values; committing it would write them back."
        from unittest import mock

        from calibre_zen import lookfeel

        before = self.gui.must_restart_before_config
        self.addCleanup(setattr, self.gui, 'must_restart_before_config', before)
        d = self.look_and_feel_dialog()
        page = d.showing_widget
        with mock.patch.object(page, 'commit') as commit:
            lookfeel.leave(page, restart=False)
        commit.assert_not_called()
        self.assertTrue(self.gui.must_restart_before_config, 'Preferences stays shut until a restart')
        self.assertFalse(d.do_restart)

        d = self.look_and_feel_dialog()
        page = d.showing_widget
        with mock.patch.object(page, 'commit') as commit:
            lookfeel.leave(page, restart=True)
        commit.assert_not_called()
        self.assertTrue(d.do_restart)

    def test_look_and_feel_reset_backs_up_when_asked(self):
        from unittest import mock

        from calibre_zen import configdir, lookfeel

        with mock.patch.object(configdir, 'backup', return_value='/b') as backup, mock.patch.object(configdir, 'reset_look_and_feel') as reset:
            self.assertEqual(lookfeel.reset(True), '/b')
            self.assertEqual(lookfeel.reset(False), '')
        backup.assert_called_once()
        self.assertEqual(reset.call_count, 2)

    def test_no_unhandled_exception_reached_the_dialog(self):
        "Startup and the tests above raised nothing the app had to report."
        from calibre_zen.report import guard

        self.assertEqual(guard.failed(), [], 'overlay parts that failed to install')


class TestColumnsForm(ZenTestCase):
    """
    The Your columns tab as a grouped form (editor/columns.py, forms/), on a
    library with one custom column of each shape the form treats differently.
    """

    COLUMNS = (
        ('acquired', 'Acquired', 'datetime', False, {}),
        ('moods', 'Moods', 'text', True, {}),
        ('owned', 'Own paper copy', 'bool', False, {}),
        ('price', 'Price', 'float', False, {}),
        ('reading_list', 'Reading list', 'series', False, {}),
        ('times_read', 'Times read', 'int', False, {}),
        ('quote', 'Favourite quote', 'comments', False, {'interpret_as': 'long-text', 'heading_position': 'above'}),
        ('review', 'My review', 'comments', False, {'interpret_as': 'html', 'heading_position': 'side'}),
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from calibre.db.legacy import LibraryDatabase

        path = base.make_library(os.path.join(cls.tmp, 'columns'))
        db = LibraryDatabase(path)
        for label, name, dt, multi, display in cls.COLUMNS:
            db.create_custom_column(label, name, dt, multi, display=display)
        db.close()
        # New columns only exist once the library is opened again.
        cls.db = LibraryDatabase(path)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.close()
        finally:
            super().tearDownClass()

    def dialog(self):
        from calibre_zen.editor.dialog import MetadataSingleDialogZen

        d = MetadataSingleDialogZen(self.db, None, editing_multiple=False)

        def cleanup():
            d.done(0)
            d.break_cycles()
            d.deleteLater()
            process_events()

        self.addCleanup(cleanup)
        d.id_list = [self.db.id(0)]
        d.current_row = 0
        d.set_current_callback = None
        d.do_one(apply_changes=False)
        d.resize(880, 640)
        d.show()
        d.zen_tabs.setCurrentIndex(d.COLUMNS)
        process_events(100)
        return d

    def test_columns_are_rows_in_groups(self):
        from qt.core import QLabel

        d = self.dialog()
        form = getattr(d, 'zen_columns_form', None)
        self.assertIsNotNone(form, 'the columns tab is still calibre grid')
        self.assertEqual([t.text() for t in form.findChildren(QLabel, 'zenFormGroupTitle')], ['Fields', 'Notes'])
        labels = {lab.text() for lab in form.findChildren(QLabel, 'zenFormLabel')}
        for _label, name, *_ in self.COLUMNS:
            self.assertIn(name, labels, f'{name} is not labelled in full')

    def test_fields_end_on_one_line(self):
        from qt.core import QPoint

        d = self.dialog()
        form = d.zen_columns_form
        edges = set()
        for w in d.custom_metadata_widgets:
            if w.col_metadata['datatype'] in ('comments', 'series'):
                continue
            control = {'bool': getattr(w, 'combobox', None), 'datetime': getattr(w, 'dte', None)}.get(w.col_metadata['datatype']) or w.editor
            control = getattr(control, 'edit_widget', control)
            edges.add(control.mapTo(form, QPoint(control.width(), 0)).x())
        self.assertEqual(len(edges), 1, f'fields end at different places: {sorted(edges)}')

    def test_free_text_sits_in_one_column(self):
        from qt.core import QPoint, QWidget

        from calibre_zen.theme.tokens import components

        d = self.dialog()
        form = d.zen_columns_form
        columns = form.findChildren(QWidget, 'zenFormColumn')
        self.assertTrue(columns, 'no free-text row has a control column')
        widths = {c.width() for c in columns}
        lefts = {c.mapTo(form, QPoint(0, 0)).x() for c in columns}
        self.assertEqual(len(widths), 1, f'text fields differ in width: {widths}')
        self.assertEqual(len(lefts), 1, f'text fields start at different places: {lefts}')
        self.assertLessEqual(widths.pop(), components.FIELD_WIDTH_TEXT_MAX)

    def test_details_is_a_grouped_form(self):
        from qt.core import QLabel

        from calibre_zen.forms import Form

        d = self.dialog()
        form = d.findChild(Form, 'zenEditorDetails')
        self.assertIsNotNone(form, 'the Details tab is not a grouped form')
        self.assertTrue(d.zen_tabs.widget(d.DETAILS).isAncestorOf(form))
        titles = [t.text() for t in form.findChildren(QLabel, 'zenFormGroupTitle')]
        self.assertEqual(titles, ['Book', 'Your library', 'Publication'])
        labels = {lab.text().replace('&', '') for lab in form.findChildren(QLabel, 'zenFormLabel')}
        self.assertTrue({'Title', 'Authors', 'Identifiers', 'Published'} <= labels, labels)
        self.assertFalse(any(t.endswith(':') for t in labels), 'a label still has its colon')

    def test_no_tab_scrolls_sideways(self):
        "A vertical scrollbar, or a narrower window, must not push a form wider than its page."
        d = self.dialog()
        d.zen_sorts_toggle.setChecked(True)
        for width in (880, 760, 880):
            d.resize(width, 640)
            for i in (d.DETAILS, d.FILES, d.COLUMNS):
                d.zen_tabs.setCurrentIndex(i)
                process_events(100)
                scroll = d._zen_details_scroll if i == d.DETAILS else d.zen_tabs.widget(i)
                self.assertFalse(scroll.horizontalScrollBar().isVisible(), f'tab {i} scrolls sideways at {width}px')

    def test_cover_follows_the_tab(self):
        from calibre_zen.theme.tokens import components

        d = self.dialog()
        d.zen_tabs.setCurrentIndex(d.FILES)
        process_events(50)
        self.assertTrue(d.zen_tabs.widget(d.FILES).isAncestorOf(d.cover), 'the cover did not come to Cover & files')
        self.assertEqual((d.cover.width(), d.cover.height()), (components.FILES_COVER_W, components.FILES_COVER_H))
        self.assertTrue(d.zen_tabs.widget(d.FILES).isAncestorOf(d.formats_manager.formats))
        d.zen_tabs.setCurrentIndex(d.DETAILS)
        process_events(50)
        self.assertTrue(d.zen_tabs.widget(d.DETAILS).isAncestorOf(d.cover), 'the cover did not go back to Details')
        self.assertEqual(d.cover.width(), components.EDITOR_COVER_W)

    def test_text_areas_start_a_few_lines_tall(self):
        from calibre_zen.theme.tokens import components

        d = self.dialog()
        for w in d.custom_metadata_widgets:
            if w.col_metadata['datatype'] == 'comments':
                tb = w._tb
                area = getattr(tb, 'editor', tb)
                self.assertGreaterEqual(area.height(), components.TEXTAREA_MIN_HEIGHT, w.col_metadata['name'])
                self.assertFalse(w._box.isVisible(), 'the comments group box is still showing')

    def test_today_and_yes_no_buttons_are_gone(self):
        d = self.dialog()
        for w in d.custom_metadata_widgets:
            dt = w.col_metadata['datatype']
            if dt == 'datetime':
                self.assertFalse(w.today_button.isVisible())
            if dt not in ('comments', 'bool'):
                self.assertTrue(w.clear_button.isVisible(), f'{w.col_metadata["name"]} lost its clear button')


class TestPlaceholder(ZenTestCase):
    "The stand-in cover's text, without a window."

    def metrics(self):
        from qt.core import QFont, QFontMetrics

        f = QFont()
        f.setPixelSize(12)
        return QFontMetrics(f)

    def test_a_long_title_stops_at_its_last_line(self):
        from calibre_zen.centre import placeholder

        fm = self.metrics()
        lines = placeholder.wrap('one two three four five six seven eight nine ten', fm, fm.horizontalAdvance('one two three'), 2)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'one two three')
        self.assertTrue(lines[1].endswith('…'), lines[1])

    def test_a_word_too_long_for_a_line_is_elided(self):
        from calibre_zen.centre import placeholder

        fm = self.metrics()
        lines = placeholder.wrap('Supercalifragilisticexpialidocious', fm, fm.horizontalAdvance('Super'), 3)
        self.assertEqual(len(lines), 1)
        self.assertLessEqual(fm.horizontalAdvance(lines[0]), fm.horizontalAdvance('Super'))

    def test_an_empty_title_draws_no_lines(self):
        from calibre_zen.centre import placeholder

        self.assertEqual(placeholder.wrap('', self.metrics(), 100, 3), [])


class TestCoverShape(ZenTestCase):
    "The grid's Uniform/Natural choice, without a window: the cache wrap and the seating."

    def setUp(self):
        from unittest import mock

        from calibre.gui2 import gprefs
        from calibre_zen.centre import grid

        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(grid.CROP_VAR, None)
        before = gprefs.get(grid.SHAPE_KEY)
        self.addCleanup(lambda: gprefs.set(grid.SHAPE_KEY, before) if before else gprefs.__delitem__(grid.SHAPE_KEY))

    def fake_gui(self):
        from types import SimpleNamespace

        from qt.core import QPixmap

        cover = QPixmap(100, 200)
        cache = SimpleNamespace(thumbnail_size=(150, 150), thumbnail_as_pixmap=lambda book_id: cover)
        return SimpleNamespace(grid_view=SimpleNamespace(delegate=SimpleNamespace(cover_cache=cache)))

    def test_the_shape_switches_in_a_running_grid(self):
        from calibre_zen.centre import grid

        gui = self.fake_gui()
        self.assertTrue(grid.attach(gui))
        cache = gui.grid_view.delegate.cover_cache
        self.assertEqual(grid.cover_shape(), 'uniform')
        self.assertEqual(cache.thumbnail_as_pixmap(1).size().width(), 150)
        grid.set_cover_shape('natural')
        pixmap = cache.thumbnail_as_pixmap(1)
        self.assertEqual((pixmap.width(), pixmap.height()), (100, 200), 'a natural cover is whole')
        grid.set_cover_shape('uniform')
        self.assertEqual(cache.thumbnail_as_pixmap(1).size().height(), 150)

    def test_the_environment_pins_the_shape(self):
        from calibre_zen.centre import grid

        os.environ[grid.CROP_VAR] = '0'
        self.assertEqual(grid.cover_shape(), 'natural')
        self.assertTrue(grid.shape_pinned())
        grid.set_cover_shape('uniform')
        self.assertEqual(grid.cover_shape(), 'natural', 'the menu cannot override the environment')

    def test_a_natural_cover_sits_on_the_floor_of_its_box(self):
        from types import SimpleNamespace

        from qt.core import QRect, QSize

        from calibre_zen.centre import grid

        delegate = SimpleNamespace(cover_size=QSize(150, 200))
        # calibre centred a 150x100 cover in a box from y=10 to y=209.
        rect = QRect(10, 60, 150, 100)
        grid.seat(delegate, rect)
        self.assertEqual((rect.top(), rect.bottom()), (110, 209))
        full = QRect(10, 10, 150, 200)
        grid.seat(delegate, full)
        self.assertEqual(full.top(), 10, 'a cover that fills its box stays put')
