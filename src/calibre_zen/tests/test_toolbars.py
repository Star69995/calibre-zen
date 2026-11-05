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
