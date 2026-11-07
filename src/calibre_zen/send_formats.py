#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
PDF is the last format a book is sent to a device in.

A device has an ordered list of the formats it accepts (Configure this device),
and sending a book uses the first of them the book has. A PDF is rarely what a
reader wants on an e-ink device when the same book also exists as an EPUB, so
whatever order is configured, PDF is taken only when nothing else matches. The
same order picks the format a book is converted to when it has none the device
takes, so a conversion is never to PDF while another format is on the list.

The list itself is not touched: Configure this device still shows, and saves, the
order the reader set. Only the GUI's reading of it changes, in one place: the
connected device's `settings()`, as the main window asks for it, returns the
same options with `format_map` reordered.
"""

from __future__ import annotations

PDF = 'pdf'

_installed = False


def pdf_last(formats) -> list:
    "`formats` in their order, with any PDF moved to the end."
    formats = list(formats)
    return [f for f in formats if f.lower() != PDF] + [f for f in formats if f.lower() == PDF]


class Reordered:
    "A device's options with PDF last in `format_map`; every other option passes through."

    def __init__(self, opts):
        self._opts = opts

    @property
    def format_map(self) -> list:
        return pdf_last(self._opts.format_map)

    def __getattr__(self, name):
        return getattr(self._opts, name)


def adopt(device):
    "Make the main window's `device.settings()` answer with PDF last. Once per device."
    if getattr(device, 'zen_pdf_last', False):
        return device
    settings = device.settings
    device.settings = lambda *args, **kwargs: Reordered(settings(*args, **kwargs))
    device.zen_pdf_last = True
    return device


def install() -> bool:
    "Wrap DeviceManager.device. Safe to call twice."
    global _installed
    if _installed:
        return True
    from calibre.gui2.device import DeviceManager

    def device(self):
        dev = self.connected_device
        if dev is not None:
            try:
                adopt(dev)
            except Exception:
                # The order is a preference; a device that refuses it is sent to as before.
                pass
        return dev

    DeviceManager.device = property(device)
    _installed = True
    return True
