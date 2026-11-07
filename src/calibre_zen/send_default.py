#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What the Send to device button does when it is clicked, chosen in a window.

calibre answers that question with a second copy of the whole send menu hanging
off the first: the same three destinations, the same two submenus, a tick beside
one of nine rows. Nothing says that the copy is a setting and not another way to
send, so the ticks look like a list of things to do and clicking one looks as if
it ought to do it.

Here the entry opens a small window instead, and the nine rows are the two
questions they were always answering: *where* to send (main memory, card A or
card B) and *how* (as it is, a format chosen each time, or sent and then
deleted from the library). The answer is stored exactly as calibre stores it,
`config['default_send_to_device_action']`, through `DeviceMenu.change_default_action`,
so the toolbar button and `trigger_default` read it unchanged.

calibre's checkable actions and its submenu are left alone, only taken off the
menu: they are what the stored choice is looked up in.

Storage cards are shown only when there is one to send to. calibre lists card A
and card B whether or not the device has them, greyed out; here a card's rows
(in the menu and in the window) appear only while the connected device reports
that card, and never with no device. A reader whose device has a card they never
use can also hide them for good with a tick in the window. A card that is the
stored default stays in the window, so what is stored is never invisible.
"""

from __future__ import annotations

import traceback

from qt.core import QAction, QButtonGroup, QDialog, QDialogButtonBox, QIcon, QRadioButton, QVBoxLayout

from calibre.utils.localization import _
from calibre_zen import forms
from calibre_zen.i18n import N_
from calibre_zen.library_dialog import Option
from calibre_zen.onboarding import parts
from calibre_zen.theme.tokens import components

# calibre's own destination keys, in the order its menu lists them. The titles
# are calibre's, so they are translated by its catalog.
DESTINATIONS = (
    ('main:', N_('Main memory')),
    ('carda:0', N_('Storage card A')),
    ('cardb:0', N_('Storage card B')),
)
# (delete, specific) as DeviceAction carries them, with what each does.
PLAIN, SPECIFIC, DELETE = (False, False), (False, True), (True, False)
WAYS = (
    (PLAIN, N_('&Send the book as it is'), N_("In the device's own format order.")),
    (SPECIFIC, N_('&Choose the format each time'), N_('Ask which format to send, for every book.')),
    (DELETE, N_('Send, then &delete from the library'), N_('Removes the book from your library once it is on the device.')),
)

# Which slot of the device's card_prefix each card is.
CARDS = {'carda:0': 0, 'cardb:0': 1}
HIDE_CARDS_KEY = 'zen_send_hide_cards'

_installed = False


def hide_cards() -> bool:
    "The reader's choice to hide cards even when the device has them."
    from calibre.gui2 import gprefs

    return bool(gprefs.get(HIDE_CARDS_KEY, False))


def has_card(menu, dest: str) -> bool:
    "Whether the connected device reports this card. Never, with no device."
    enabled, prefix = menu.zen_device
    return bool(enabled and prefix and prefix[CARDS[dest]] is not None)


def shows(menu, dest: str) -> bool:
    "Whether a destination's rows are offered: main memory always, a card when there is one."
    return dest not in CARDS or (has_card(menu, dest) and not hide_cards())


def show_cards(menu) -> None:
    "Show or hide every card row in the menu and its submenus."
    for action in menu._actions:
        if action.dest in CARDS:
            action.setVisible(shows(menu, action.dest))


def current(menu) -> tuple[str, tuple[bool, bool]]:
    "The stored default as (destination, (delete, specific))."
    action = menu.group.checkedAction()
    return action.dest, (action.delete, action.specific)


def action_for(menu, dest: str, way: tuple[bool, bool]):
    "calibre's checkable action for a choice, the one `change_default_action` stores."
    return next(a for a in menu.group.actions() if (a.dest, (a.delete, a.specific)) == (dest, way))


class DefaultSendDialog(QDialog):
    "Two questions, and OK stores the answer."

    def __init__(self, menu, parent=None):
        super().__init__(parent)
        self.menu = menu
        self.setWindowTitle(_('What Send to device does'))
        dest, way = current(menu)

        column = QVBoxLayout(self)
        column.setSpacing(components.FORM_SECTION_GAP)
        intro = parts.hint(self)
        intro.setText(_('This is what happens when you click the Send to device button itself, not its arrow.'))
        column.addWidget(intro)

        form = forms.Form(self, slots=1, fill=True)
        where = form.group(_('Send to'))
        self.destination_group = QButtonGroup(self)
        self.destinations = {}
        for key, title in DESTINATIONS:
            if key != dest and not shows(menu, key):
                continue
            button = QRadioButton(_(title), self)
            self.destination_group.addButton(button)
            self.destinations[key] = button
            where.block(button)
        self.destinations[dest].setChecked(True)
        self.hide_cards = parts.check(self, _('Hide storage cards from the menu, even if the device has them'), hide_cards())
        where.block(self.hide_cards)
        ways = form.group(_('How'))
        self.ways = QButtonGroup(self)
        self.way_buttons = {}
        for key, title, note in WAYS:
            button = QRadioButton(_(title), self)
            self.ways.addButton(button)
            self.way_buttons[key] = button
            ways.block(Option(button, _(note), self))
        self.way_buttons[way].setChecked(True)
        form.finish()
        column.addWidget(form)
        formats = parts.hint(self)
        formats.setText(_('Which formats a book is sent in, and their order, are set for each device: Device button > Configure this device.'))
        column.addWidget(formats)
        column.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.setMinimumWidth(components.SEND_DEFAULT_WIDTH)

    def showEvent(self, ev) -> None:
        """
        As tall as the contents need at the window's width. The two lines that
        wrap make the height depend on the width, which Qt's minimum
        underestimates, squeezing the choices (the same as library_dialog.Layout.fit).
        """
        super().showEvent(ev)
        grid = self.layout()
        grid.activate()
        width = max(self.width(), grid.totalMinimumSize().width())
        height = grid.totalHeightForWidth(width) if grid.hasHeightForWidth() else grid.totalSizeHint().height()
        self.setMinimumHeight(height)
        self.resize(width, height)

    def chosen(self) -> tuple[str, tuple[bool, bool]]:
        dest = next(k for k, b in self.destinations.items() if b.isChecked())
        way = next(k for k, b in self.way_buttons.items() if b.isChecked())
        return dest, way

    def accept(self) -> None:
        from calibre.gui2 import gprefs

        gprefs[HIDE_CARDS_KEY] = self.hide_cards.isChecked()
        show_cards(self.menu)
        self.menu.change_default_action(action_for(self.menu, *self.chosen()))
        super().accept()


def choose(menu) -> None:
    DefaultSendDialog(menu, menu.parentWidget()).exec()


def replace_submenu(menu) -> QAction:
    "Put a plain entry where calibre's submenu was, and take the submenu off the menu."
    submenu = menu.set_default_menu.menuAction()
    entry = QAction(QIcon.ic('config.png'), _('What clicking Send to device does…'), menu)
    entry.triggered.connect(lambda checked=False: choose(menu))
    menu.insertAction(submenu, entry)
    menu.removeAction(submenu)
    menu.zen_default_entry = entry
    return entry


def install() -> bool:
    "Wrap DeviceMenu.__init__ and enable_device_actions. Safe to call twice."
    global _installed
    if _installed:
        return True
    from calibre.gui2.device import DeviceMenu

    orig = DeviceMenu.__init__
    orig_enable = DeviceMenu.enable_device_actions

    def enable_device_actions(self, enable, card_prefix=(None, None), device=None):
        orig_enable(self, enable, card_prefix, device)
        self.zen_device = (enable, card_prefix)
        show_cards(self)

    def __init__(self, parent=None):
        orig(self, parent)
        try:
            replace_submenu(self)
        except Exception:
            # calibre's submenu is still there if this failed before removing it.
            traceback.print_exc()

    __init__.__wrapped__ = orig
    enable_device_actions.__wrapped__ = orig_enable
    DeviceMenu.__init__ = __init__
    DeviceMenu.enable_device_actions = enable_device_actions
    _installed = True
    return True
