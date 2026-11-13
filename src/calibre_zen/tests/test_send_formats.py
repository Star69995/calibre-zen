#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
PDF last (send_formats.py): the main window reads a device's format order with
PDF at the end, and nothing else about the device or its saved order changes.
"""

from types import SimpleNamespace

from calibre_zen import send_formats
from calibre_zen.tests.base import ZenTestCase


class Device:
    ORDER = ['pdf', 'epub', 'PDF', 'mobi']

    @classmethod
    def settings(cls):
        return SimpleNamespace(format_map=list(cls.ORDER), use_subdirs=True)


class TestSendFormats(ZenTestCase):
    def manager(self, device):
        from calibre.gui2.device import DeviceManager

        dm = DeviceManager.__new__(DeviceManager)
        dm.connected_device = device
        return dm

    def test_pdf_goes_last_and_the_rest_keep_their_order(self):
        self.assertEqual(send_formats.pdf_last(['pdf', 'epub', 'PDF', 'mobi']), ['epub', 'mobi', 'pdf', 'PDF'])
        self.assertEqual(send_formats.pdf_last(['epub', 'azw3']), ['epub', 'azw3'])
        self.assertEqual(send_formats.pdf_last([]), [])

    def test_the_main_window_sees_pdf_last(self):
        dm = self.manager(Device())
        opts = dm.device.settings()
        self.assertEqual(opts.format_map, ['epub', 'mobi', 'pdf', 'PDF'])
        self.assertTrue(opts.use_subdirs, 'other options pass through')

    def test_the_saved_order_is_untouched(self):
        dm = self.manager(Device())
        self.assertIs(dm.device, dm.connected_device)  # reading it is what adopts the order
        self.assertEqual(Device.settings().format_map, Device.ORDER)

    def test_a_device_is_adopted_once(self):
        dm = self.manager(Device())
        first = dm.device.settings
        self.assertIs(dm.device.settings, first)

    def test_no_device_is_none(self):
        self.assertIsNone(self.manager(None).device)
