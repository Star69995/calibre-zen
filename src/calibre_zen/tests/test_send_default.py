#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The default send action as a window (send_default.py): calibre's submenu is off
the menu, the window shows the stored choice, and OK stores it the way calibre
does.
"""

from calibre_zen import send_default
from calibre_zen.tests.base import ZenTestCase


class TestSendDefault(ZenTestCase):
    def menu(self):
        from calibre.gui2.device import DeviceMenu

        m = DeviceMenu(None)
        self.addCleanup(m.deleteLater)
        # The stored default outlives a test; start each from main memory.
        m.change_default_action(send_default.action_for(m, 'main:', send_default.PLAIN))
        return m

    def test_the_submenu_is_replaced_by_an_entry(self):
        m = self.menu()
        menus = [a.menu() for a in m.actions() if a.menu() is not None]
        self.assertNotIn(m.set_default_menu, menus)
        self.assertIn(m.zen_default_entry, m.actions())

    def test_every_choice_has_a_calibre_action(self):
        m = self.menu()
        for dest, _title in send_default.DESTINATIONS:
            for way, _t, _n in send_default.WAYS:
                action = send_default.action_for(m, dest, way)
                self.assertEqual((action.dest, (action.delete, action.specific)), (dest, way))

    def test_the_window_shows_the_stored_choice(self):
        m = self.menu()
        m.change_default_action(send_default.action_for(m, 'carda:0', send_default.SPECIFIC))
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        self.assertEqual(d.chosen(), ('carda:0', send_default.SPECIFIC))

    def test_ok_stores_the_choice_as_calibre_does(self):
        from calibre.gui2.device import config

        m = self.menu()
        m.enable_device_actions(True, ('/card/a', '/card/b'))
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        d.destinations['cardb:0'].setChecked(True)
        d.way_buttons[send_default.DELETE].setChecked(True)
        d.accept()
        self.assertEqual(config['default_send_to_device_action'], repr(send_default.action_for(m, 'cardb:0', send_default.DELETE)))
        self.assertEqual(send_default.current(m), ('cardb:0', send_default.DELETE))

    def test_cancel_changes_nothing(self):
        m = self.menu()
        m.enable_device_actions(True, ('/card/a', '/card/b'))
        before = send_default.current(m)
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        d.destinations['cardb:0'].setChecked(True)
        d.reject()
        self.assertEqual(send_default.current(m), before)

    def visible_cards(self, m):
        return {a.dest for a in m._actions if a.dest in send_default.CARDS and a.isVisible()}

    def test_with_no_device_no_card_is_offered(self):
        m = self.menu()
        self.assertEqual(self.visible_cards(m), set())
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        self.assertEqual(set(d.destinations), {'main:'})

    def test_only_the_cards_the_device_has_are_offered(self):
        m = self.menu()
        m.enable_device_actions(True, ('/card/a', None))
        self.assertEqual(self.visible_cards(m), {'carda:0'})
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        self.assertEqual(set(d.destinations), {'main:', 'carda:0'})
        m.enable_device_actions(False)
        self.assertEqual(self.visible_cards(m), set())

    def test_the_reader_can_hide_cards_the_device_has(self):
        from calibre.gui2 import gprefs

        m = self.menu()
        m.enable_device_actions(True, ('/card/a', '/card/b'))
        self.assertEqual(self.visible_cards(m), {'carda:0', 'cardb:0'})
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        self.addCleanup(gprefs.__setitem__, send_default.HIDE_CARDS_KEY, False)
        d.hide_cards.setChecked(True)
        d.accept()
        self.assertEqual(self.visible_cards(m), set())

    def test_a_card_that_is_the_default_stays_in_the_window(self):
        m = self.menu()
        m.change_default_action(send_default.action_for(m, 'cardb:0', send_default.PLAIN))
        d = send_default.DefaultSendDialog(m)
        self.addCleanup(d.deleteLater)
        self.assertEqual(set(d.destinations), {'main:', 'cardb:0'})
        self.assertEqual(d.chosen()[0], 'cardb:0')
