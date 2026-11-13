#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The picture in the install dialog: where the new button will be.

After a plugin is installed calibre asks which toolbars and menus to add it to
and lists ten places by name, "the main toolbar when a device is connected", "the
context menu for the split book list", with no sign of what any of them looks
like. Here each place that is ticked is drawn under the list: a bar for a
toolbar, a short menu for a menu, the buttons that are already there as icons
and the new one picked out. Tick or untick a place and the picture follows.

It is drawn from the same layouts the window reads (`gprefs['action-layout-*']`)
and from `toolbars.with_new_button`, the function the install itself uses, so it
shows what will happen and not an approximation of it. The widgets are laid out,
not painted, so right-to-left mirrors them without a line of code here.

The list above it is calibre's, a multi-selection list whose chosen rows were a
solid block of accent with no room between them. Here each row carries a tick
that mirrors its selection, the chosen ones take a light wash, and
the list is as tall as its rows, so every place is in view at once. The
selection stays what calibre reads (`selected_locations`); the tick only shows it.
"""

from __future__ import annotations

from typing import NamedTuple

from qt.core import QAbstractItemView, QFrame, QHBoxLayout, QIcon, QLabel, QListWidget, Qt, QVBoxLayout, QWidget

from calibre_zen import toolbars
from calibre_zen.theme.tokens import components

# Places drawn as a row of buttons. Every other place is a menu.
BAR_PLACES = frozenset({'toolbar', 'toolbar-device', 'toolbar-child', 'searchbar'})


class Entry(NamedTuple):
    icon: QIcon
    text: str


def layout_of(key: str) -> tuple:
    "The names in place `key`, with None for a separator."
    from calibre.gui2 import gprefs

    return tuple(gprefs.get('action-layout-' + key) or ())


def entry_for(gui, name) -> Entry | None:
    "The icon and text of a button by its action name, or None for one that is not loaded."
    action = (getattr(gui, 'iactions', None) or {}).get(name)
    qaction = getattr(action, 'qaction', None)
    if qaction is None:
        return None
    return Entry(qaction.icon(), qaction.text().replace('&', '') or str(name))


def new_entry(plugin) -> Entry:
    "The new button: its own action when the plugin has made one, else a plain plugin icon."
    qaction = getattr(plugin, 'qaction', None)
    if qaction is not None and not qaction.icon().isNull():
        return Entry(qaction.icon(), qaction.text().replace('&', '') or plugin.name)
    return Entry(QIcon.ic('plugins.png'), plugin.name)


def plan(gui, plugin, key: str) -> tuple[list[Entry | None], int]:
    """
    What to draw for place `key`: its entries in order (None is a separator) and
    the index of the new button among them.
    """
    name = getattr(plugin, 'name', '')
    names = toolbars.with_new_button(layout_of(key), name, key)
    at = len(names) - 1 - names[::-1].index(name)
    entries: list[Entry | None] = []
    index = 0
    for i, n in enumerate(names):
        if i == at:
            index = len(entries)
            entries.append(new_entry(plugin))
        elif n is None:
            entries.append(None)
        else:
            entry = entry_for(gui, n)
            if entry is not None:
                entries.append(entry)
    return entries, index


def window(entries: list, index: int, limit: int) -> tuple[list, int, bool]:
    """
    At most `limit` entries around the new one, so a long bar still shows where
    the button goes. Returns them, the new one's index among them, and whether
    anything was cut off the start.
    """
    start = max(0, min(index - limit // 2, len(entries) - limit))
    shown = entries[start : start + limit]
    return shown, index - start, start > 0


def icon_label(entry: Entry, parent) -> QLabel:
    label = QLabel(parent)
    size = components.PLACE_ICON
    label.setPixmap(entry.icon.pixmap(size, size))
    label.setToolTip(entry.text)
    return label


class NewChip(QFrame):
    "The new button: its icon and its name, in the accent."

    def __init__(self, entry: Entry, parent=None):
        super().__init__(parent)
        self.setObjectName('zenPlaceNew')
        row = QHBoxLayout(self)
        row.setContentsMargins(components.PLACE_CHIP_PAD, 1, components.PLACE_CHIP_PAD, 1)
        row.setSpacing(components.PLACE_GAP)
        row.addWidget(icon_label(entry, self))
        text = QLabel(entry.text, self)
        text.setObjectName('zenPlaceNewText')
        row.addWidget(text)


class Place(QWidget):
    "One ticked place: its name, and a bar or a menu with the new button in it."

    def __init__(self, heading: str, entries: list, index: int, bar: bool, parent=None):
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(components.PLACE_GAP)
        title = QLabel(heading, self)
        title.setObjectName('zenPlaceTitle')
        column.addWidget(title)
        frame = QFrame(self)
        frame.setObjectName('zenPlaceBar' if bar else 'zenPlaceMenu')
        column.addWidget(frame)
        limit = components.PLACE_BAR_MAX if bar else components.PLACE_MENU_ROWS
        shown, at, cut = window(entries, index, limit)
        if bar:
            row = QHBoxLayout(frame)
            row.setContentsMargins(components.PLACE_PAD, components.PLACE_PAD, components.PLACE_PAD, components.PLACE_PAD)
            row.setSpacing(components.PLACE_GAP)
            if cut:
                row.addWidget(QLabel('…', frame))
            for i, entry in enumerate(shown):
                if entry is None:
                    rule = QFrame(frame)
                    rule.setObjectName('zenPlaceSep')
                    rule.setFrameShape(QFrame.Shape.VLine)
                    row.addWidget(rule)
                else:
                    row.addWidget(NewChip(entry, frame) if i == at else icon_label(entry, frame))
            row.addStretch(1)
        else:
            col = QVBoxLayout(frame)
            col.setContentsMargins(components.PLACE_PAD, components.PLACE_PAD, components.PLACE_PAD, components.PLACE_PAD)
            col.setSpacing(components.PLACE_GAP)
            if cut:
                col.addWidget(QLabel('…', frame))
            for i, entry in enumerate(shown):
                if entry is None:
                    continue
                if i == at:
                    col.addWidget(NewChip(entry, frame))
                    continue
                line = QHBoxLayout()
                line.setSpacing(components.PLACE_GAP)
                line.addWidget(icon_label(entry, frame))
                line.addWidget(QLabel(entry.text, frame), 1)
                col.addLayout(line)


class PlacementPicture(QWidget):
    "Everything the dialog draws under its list; rebuilt whenever the ticks change."

    def __init__(self, gui, plugin, parent=None):
        super().__init__(parent)
        self.gui = gui
        self.plugin = plugin
        self.setObjectName('zenPlacement')
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(components.PLACE_SECTION_GAP)
        self.places: list[Place] = []

    def show_for(self, chosen) -> None:
        "Draw each of `chosen`, (key, text) pairs, or say what to do when none is."
        while self.column.count():
            widget = self.column.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.places = []
        if not chosen:
            hint = QLabel(_('Tick a place to see where the button will appear.'), self)
            hint.setObjectName('zenPlaceHint')
            self.column.addWidget(hint)
            return
        for key, text in chosen:
            entries, index = plan(self.gui, self.plugin, key)
            place = Place(toolbars.device_label(key, text), entries, index, key in BAR_PLACES, self)
            self.places.append(place)
            self.column.addWidget(place)


def show_ticks(places: QListWidget) -> None:
    "Give every row a tick that says whether it is selected."
    for row in range(places.count()):
        item = places.item(row)
        if item is not None:
            item.setCheckState(Qt.CheckState.Checked if item.isSelected() else Qt.CheckState.Unchecked)


def fit_rows(places: QListWidget) -> None:
    "As tall as all of its rows, so no place is hidden below a scroll."
    places.ensurePolished()
    rows = sum(places.sizeHintForRow(row) + 2 * places.spacing() for row in range(places.count()))
    places.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    places.setFixedHeight(rows + 2 * (places.frameWidth() + components.PLACE_LIST_PAD))


def tick_list(places: QListWidget) -> None:
    """
    calibre's list of places, as rows to tick. A row is still selected and
    unselected by a click anywhere on it, the tick included: it is not made
    checkable, so there is one state to read and nothing to keep in step but
    the mark.
    """
    places.setObjectName('zenPlaceList')
    # Already polished by calibre's resize(); the sheet's #zenPlaceList rules
    # only reach it once it is polished again under its new name.
    places.style().unpolish(places)
    places.style().polish(places)
    places.setSpacing(components.PLACE_LIST_SPACING)
    places.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    for row in range(places.count()):
        item = places.item(row)
        if item is not None:
            # A list item is user-checkable unless told otherwise, and a click on
            # its box would then flip the tick and leave the selection alone.
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
    show_ticks(places)
    places.itemSelectionChanged.connect(lambda: show_ticks(places))
    fit_rows(places)


def attach(dialog, gui, plugin) -> PlacementPicture:
    "Put the picture under `dialog`'s list of places and keep it in step with the ticks."
    tick_list(dialog._locations_list)
    picture = PlacementPicture(gui, plugin, dialog)
    layout = dialog._layout
    layout.insertWidget(layout.indexOf(dialog._locations_list) + 1, picture)
    refresh = lambda: picture.show_for(dialog.selected_locations())  # ruff: ignore[lambda-assignment]
    dialog._locations_list.itemSelectionChanged.connect(refresh)
    refresh()
    dialog.placement = picture
    dialog.resize(dialog.sizeHint())
    return picture
