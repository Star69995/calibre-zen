#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The toolbar a connected device shows: the main toolbar, plus what a device adds.
The real bars are checked in test_gui; this is the arithmetic.
"""

from calibre_zen import toolbars
from calibre_zen.tests.base import ZenTestCase

ADD = toolbars.DEVICE_ADDITIONS


class TestDeviceLayout(ZenTestCase):
    def test_the_device_buttons_follow_the_books_and_stay_ahead_of_the_app_buttons(self):
        got = toolbars.device_layout(('Add Books', None, 'View', None, 'Help', 'Preferences'), ADD)
        self.assertEqual(got, ('Add Books', None, 'View', None, 'Send To Device', 'Location Manager', None, 'Help', 'Preferences'))

    def test_a_bar_with_no_app_run_gets_them_at_the_end(self):
        got = toolbars.device_layout(('Add Books', 'View'), ADD)
        self.assertEqual(got, ('Add Books', 'View', None, 'Send To Device', 'Location Manager'))

    def test_what_the_main_bar_has_is_not_added_twice(self):
        got = toolbars.device_layout(('Add Books', 'Send To Device'), ADD)
        self.assertEqual(got, ('Add Books', 'Send To Device', None, 'Location Manager'))
        self.assertEqual(toolbars.device_layout(('Add Books', 'Send To Device'), ('Send To Device',)), ('Add Books', 'Send To Device'))

    def test_a_layout_calibre_saved_for_the_device_adds_only_what_is_new(self):
        saved = ('Add Books', 'Edit Metadata', None, 'View', 'Send To Device', None, None, 'Location Manager', None, 'Remove Books')
        got = toolbars.device_layout(('Add Books', 'Edit Metadata', None, 'View', 'Remove Books'), saved)
        self.assertEqual(got, ('Add Books', 'Edit Metadata', None, 'View', 'Remove Books', None, 'Send To Device', 'Location Manager'))

    def test_nothing_to_add_leaves_the_main_bar_as_it_is(self):
        self.assertEqual(toolbars.device_layout(('Add Books', None), ()), ('Add Books', None))
        self.assertEqual(toolbars.device_layout((), ADD), ('Send To Device', 'Location Manager'))

    def test_an_action_that_cannot_be_on_the_device_bar_is_left_out(self):
        class Action:
            dont_add_to = frozenset({'toolbar-device'})

        got = toolbars.device_layout(('Add Books', 'LLM Book'), ADD, {'LLM Book': Action()})
        self.assertEqual(got, ('Add Books', None, 'Send To Device', 'Location Manager'))


class TestWhereAPluginGoes(ZenTestCase):
    LOCATIONS = [('toolbar', 'The main toolbar'), ('toolbar-device', 'x'), ('toolbar-child', 'Second'), ('searchbar', 'Search bar')]

    def ticked(self, **attrs):
        from calibre.gui2.dialogs.choose_plugin_toolbars import ChoosePluginToolbarsDialog
        from calibre_zen.tests.base import app

        app()
        plugin = type('Plugin', (), {'name': 'Mine', **attrs})()
        d = ChoosePluginToolbarsDialog(None, plugin, list(self.LOCATIONS))
        self.addCleanup(d.deleteLater)
        return sorted(key for key, _text in d.selected_locations()), d

    def test_a_plugin_that_says_nothing_gets_the_main_toolbar_only(self):
        self.assertEqual(self.ticked()[0], ['toolbar'])

    def test_a_plugin_chooses_its_locations(self):
        self.assertEqual(self.ticked(default_add_to=frozenset({'toolbar', 'searchbar'}))[0], ['searchbar', 'toolbar'])
        self.assertEqual(self.ticked(default_add_to='toolbar-device')[0], ['toolbar-device'])

    def test_a_place_it_cannot_go_is_not_ticked_and_none_is_allowed(self):
        got = self.ticked(default_add_to={'toolbar', 'searchbar'}, dont_add_to=frozenset({'searchbar'}))[0]
        self.assertEqual(got, ['toolbar'])
        self.assertEqual(self.ticked(default_add_to=())[0], [])

    def test_the_device_entry_is_worded_as_in_preferences(self):
        _got, d = self.ticked()
        self.assertEqual(d._locations_list.item(1).text(), 'Added to the main toolbar when a device is connected')


class TestWhereANewButtonGoes(ZenTestCase):
    def test_on_the_main_toolbar_it_goes_before_the_application_buttons(self):
        layout = ('Add Books', None, 'View', None, 'Help', 'Preferences')
        self.assertEqual(toolbars.with_new_button(layout, 'Mine', 'toolbar'), ('Add Books', None, 'View', 'Mine', None, 'Help', 'Preferences'))

    def test_a_bar_that_ends_with_books_gets_it_last(self):
        self.assertEqual(toolbars.with_new_button(('Add Books', 'View'), 'Mine', 'toolbar'), ('Add Books', 'View', 'Mine'))
        self.assertEqual(toolbars.with_new_button((), 'Mine', 'toolbar'), ('Mine',))

    def test_any_other_place_appends(self):
        self.assertEqual(toolbars.with_new_button(('A', 'Preferences'), 'Mine', 'searchbar'), ('A', 'Preferences', 'Mine'))
        self.assertEqual(toolbars.with_new_button(('Send To Device',), 'Mine', 'toolbar-device'), ('Send To Device', 'Mine'))

    def test_an_install_that_appended_is_corrected(self):
        before = ('Add Books', None, 'Help', 'Preferences')
        after = before + ('Mine',)
        self.assertEqual(toolbars.placed(before, after, 'toolbar'), ('Add Books', 'Mine', None, 'Help', 'Preferences'))

    def test_a_change_that_is_not_an_append_is_left_alone(self):
        self.assertEqual(toolbars.placed(('A', 'B'), ('B', 'A'), 'toolbar'), ('B', 'A'))
        self.assertEqual(toolbars.placed(('A',), ('A',), 'toolbar'), ('A',))
        self.assertEqual(toolbars.placed(('A', 'Preferences'), ('A', 'Preferences', 'Mine'), 'searchbar'), ('A', 'Preferences', 'Mine'))


class TestThePicture(ZenTestCase):
    LOCATIONS = TestWhereAPluginGoes.LOCATIONS + [('context-menu', 'The context menu')]

    def dialog(self, **attrs):
        from calibre.gui2.dialogs.choose_plugin_toolbars import ChoosePluginToolbarsDialog
        from calibre_zen.tests.base import app

        app()
        plugin = type('Plugin', (), {'name': 'Mine', **attrs})()
        d = ChoosePluginToolbarsDialog(None, plugin, list(self.LOCATIONS))
        self.addCleanup(d.deleteLater)
        return d

    def test_a_place_is_drawn_for_each_tick_and_follows_them(self):
        d = self.dialog()
        self.assertEqual(len(d.placement.places), 1, 'the main toolbar is ticked')
        d._locations_list.item(3).setSelected(True)
        self.assertEqual(len(d.placement.places), 2)
        d._locations_list.item(0).setSelected(False)
        d._locations_list.item(3).setSelected(False)
        self.assertEqual(d.placement.places, [])
        self.assertTrue(d.placement.findChild(type(d._header_label), 'zenPlaceHint'))

    def test_each_place_wears_a_tick_that_follows_its_selection(self):
        from qt.core import Qt

        d = self.dialog()
        places = d._locations_list

        def ticks():
            return [places.item(i).checkState() == Qt.CheckState.Checked for i in range(places.count())]

        self.assertEqual(ticks(), [True, False, False, False, False])
        places.item(3).setSelected(True)
        places.item(0).setSelected(False)
        self.assertEqual(ticks(), [False, False, False, True, False])
        self.assertEqual([key for key, _text in d.selected_locations()], ['searchbar'], 'the selection is still what calibre reads')
        self.assertFalse(places.item(0).flags() & Qt.ItemFlag.ItemIsUserCheckable, 'one state: the tick is only a mark')

    def test_every_place_is_in_view_without_scrolling(self):
        from qt.core import Qt

        places = self.dialog()._locations_list
        self.assertEqual(places.objectName(), 'zenPlaceList')
        self.assertEqual(places.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rows = sum(places.sizeHintForRow(i) for i in range(places.count()))
        self.assertGreaterEqual(places.height(), rows)

    def test_the_new_button_is_picked_out_by_name(self):
        from calibre_zen import placement

        d = self.dialog()
        chips = d.placement.findChildren(placement.NewChip)
        self.assertEqual(len(chips), 1)
        self.assertEqual(chips[0].findChild(type(d._header_label), 'zenPlaceNewText').text(), 'Mine')

    def test_a_menu_is_drawn_as_rows_and_a_bar_as_a_row(self):
        d = self.dialog(default_add_to=frozenset({'toolbar', 'context-menu'}))
        from qt.core import QFrame

        names = sorted(p.findChild(QFrame, 'zenPlaceBar') is not None for p in d.placement.places)
        self.assertEqual(names, [False, True])

    def test_only_a_place_the_plugin_asked_for_is_called_recommended(self):
        asked = self.dialog(default_add_to=frozenset({'searchbar'}))
        self.assertIn('Recommended', asked._locations_list.item(3).text())
        self.assertNotIn('Recommended', asked._locations_list.item(0).text())
        silent = self.dialog()
        self.assertTrue(all('Recommended' not in silent._locations_list.item(i).text() for i in range(silent._locations_list.count())))

    def test_a_long_bar_is_cut_at_the_start_and_keeps_the_new_button(self):
        from calibre_zen import placement

        entries = list(range(20))
        shown, at, cut = placement.window(entries, 19, 9)
        self.assertEqual((len(shown), shown[at], cut), (9, 19, True))
        shown, at, cut = placement.window(entries[:5], 4, 9)
        self.assertEqual((len(shown), shown[at], cut), (5, 4, False))
