#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Choosing the book list's columns without hunting for the header.

calibre's way is to right-click a column header, then Hide, or Show column and a
submenu, one column at a time (`views.py`, `column_header_context_menu`). Nothing
on screen says it exists, and putting a column where you want it is dragging
headers blind. The strip above the list has a **Columns** button for the table:
a panel with every column and a tick for each, a search box for a library with
many custom columns, an up and a down arrow to move a shown one, **Add column**
and **Reset**.

It adds no setting and does no sectioning of its own. Every change goes through
what calibre already has: `column_header_context_handler` for show, hide, the
defaults and Add column (so "you must not hide all columns" and the restart that
a new column may need are calibre's, not copies), and `QHeaderView.moveSection`
for order, whose `sectionMoved` calibre already saves from. The arrangement is
the state dict of `table.arrange`, under the key of our own, so the picker reads
and writes the same thing the table does.

Two columns are not offered. `authors` and `series` are folded into the Details
column and hidden (`table.FOLDED_COLUMNS`); a switch for them would do nothing
the reader can see. Details itself stays on and first, which is what the table is
drawn around. `ondevice` and `inlibrary` are calibre's own, and cannot be hidden.

With a device connected and its books in view, the button acts on that list
instead (`gui.current_view()`). The device's list is drawn around Details too
(`device.py`), so it is arranged the same way: `authors` is folded in, Details is
locked, and Reset is the same arrangement. Add column says why it cannot
(calibre's device list takes no custom columns). Its state is kept under a key
of our own, as the library's is.
"""

from __future__ import annotations

from typing import NamedTuple

from qt.core import QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, Qt, QToolButton, QVBoxLayout, QWidget

from calibre.utils.icu import primary_sort_key
from calibre_zen import popovers
from calibre_zen.centre import table
from calibre_zen.icons import registry
from calibre_zen.theme.tokens import components

# calibre's own columns the reader is not given a choice about.
ALWAYS_THERE = frozenset({'ondevice', 'inlibrary'})
NOT_OFFERED = frozenset(table.FOLDED_COLUMNS) | ALWAYS_THERE


class Column(NamedTuple):
    key: str
    title: str
    visible: bool
    locked: bool  # shown and in place, whatever is asked


def is_library(view) -> bool:
    "Whether `view` is the library's table, drawn around Details, rather than a device's list."
    return getattr(view, 'is_library_view', True)


def has_details(view) -> bool:
    "Whether `view` is drawn around the Details column: the library's table and a device's list both are."
    return table.DETAILS_COLUMN in getattr(view, 'column_map', ())


def not_offered(view) -> frozenset:
    "The columns `view` gives no switch for."
    return NOT_OFFERED if has_details(view) else ALWAYS_THERE


def locked(view, key: str) -> bool:
    "Whether `key` stays shown and first in `view`: Details."
    return has_details(view) and key == table.DETAILS_COLUMN


def column_title(view, index: int, key: str) -> str:
    "The header's own words for a column; Details for the one the table is drawn around."
    if locked(view, key):
        return _('Details')
    model = view.model()
    text = model.headerData(index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) if model is not None else None
    return str(text or key)


def columns_for(view) -> list[Column]:
    """
    Every column the reader can choose, the shown ones in the order they are on
    screen and then the hidden ones by name. Two columns with the same title
    carry their lookup name, as calibre's own menu does.
    """
    header = view.column_header
    skip = not_offered(view)
    found = []
    for index, key in enumerate(view.column_map):
        if key in skip:
            continue
        found.append((key, column_title(view, index, key), not header.isSectionHidden(index), header.visualIndex(index)))
    counts: dict[str, int] = {}
    for _key, title, _visible, _pos in found:
        counts[title] = counts.get(title, 0) + 1
    shown = sorted((c for c in found if c[2]), key=lambda c: c[3])
    hidden = sorted((c for c in found if not c[2]), key=lambda c: primary_sort_key(c[1]))
    return [Column(key, f'{title} [{key}]' if counts[title] > 1 else title, visible, locked(view, key)) for key, title, visible, _pos in shown + hidden]


def set_visible(view, key: str, on: bool) -> None:
    "Show or hide a column through calibre's own handler, which says no to hiding the last one."
    view.column_header_context_handler(action='show' if on else 'hide', column=key, view=view)


def move(view, key: str, step: int) -> bool:
    """
    Move a shown column one place toward the start (-1) or the end (+1) among
    the shown ones. Returns whether it moved: the first and last cannot, and
    nothing goes in front of the locked Details column.
    """
    shown = [c for c in columns_for(view) if c.visible]
    keys = [c.key for c in shown]
    if key not in keys:
        return False
    target = keys.index(key) + step
    if not 0 <= target < len(keys) or shown[target].locked or shown[keys.index(key)].locked:
        return False
    header = view.column_header
    here = header.visualIndex(view.column_map.index(key))
    there = header.visualIndex(view.column_map.index(keys[target]))
    header.moveSection(here, there)
    return True


def reset(view) -> None:
    "Back to calibre's default columns, arranged as the table needs them."
    state = view.get_default_state()
    view.apply_state(table.arrange(state, view.column_map))


def can_add(view) -> tuple[bool, str]:
    "Whether Add column works now, and if not, why, so the button can say so before the click."
    if not getattr(view, 'can_add_columns', False):
        return False, _('Columns cannot be added to this list.')
    from calibre.gui2.preferences.create_custom_column import CreateNewCustomColumn

    if CreateNewCustomColumn(view.gui).must_restart():
        return False, _('Restart calibre first: a column was added or changed and has not taken effect yet.')
    return True, _('Create a column of your own')


def add_column(view) -> None:
    view.column_header_context_handler(action='addcustcol', column=table.DETAILS_COLUMN, view=view)


class ColumnRow(QWidget):
    "One column: a tick with its name, and, for a shown one, arrows to move it."

    def __init__(self, column: Column, panel):
        super().__init__(panel)
        self.column = column
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(components.COLUMNS_GAP)
        self.check = QCheckBox(column.title, self)
        self.check.setChecked(column.visible)
        self.check.setEnabled(not column.locked)
        if column.locked:
            self.check.setToolTip(_('The table is drawn around this column, so it stays.'))
        self.check.toggled.connect(lambda on: panel.choose(column.key, on))
        row.addWidget(self.check, 1)
        self.up = self.arrow('chevron-up', _('Move toward the start'), -1, panel)
        self.down = self.arrow('chevron-down', _('Move toward the end'), 1, panel)
        for button in (self.up, self.down):
            row.addWidget(button)
            button.setVisible(column.visible and not column.locked)

    def arrow(self, glyph: str, tip: str, step: int, panel) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName('zenColumnMove')
        button.setAutoRaise(True)
        button.setToolTip(tip)
        icon = registry.glyph_icon(glyph, 'text')
        if icon is not None and not icon.isNull():
            button.setIcon(icon)
        else:
            button.setText('↑' if step < 0 else '↓')
        button.clicked.connect(lambda: panel.shift(self.column.key, step))
        return button


class ColumnsPanel(QFrame):
    "The popup the Columns button opens."

    def __init__(self, button, view):
        super().__init__(button, Qt.WindowType.Popup)
        self.button = button
        self.view = view
        self.setObjectName('zenColumnsWindow')
        self.setFixedWidth(components.COLUMNS_PANEL_WIDTH)
        pad = components.COLUMNS_PAD
        column = QVBoxLayout(popovers.painted_body(self, 'zenColumnsPanel'))
        column.setContentsMargins(pad, pad, pad, pad)
        column.setSpacing(pad)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(_('Find a column'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.rebuild)
        column.addWidget(self.search)

        self.body = QWidget(self)
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(components.COLUMNS_GAP)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName('zenColumnsScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.body)
        self.scroll.setMaximumHeight(components.COLUMNS_PANEL_HEIGHT)
        column.addWidget(self.scroll, 1)

        rule = QFrame(self)
        rule.setObjectName('zenColumnsRule')
        rule.setFrameShape(QFrame.Shape.HLine)
        column.addWidget(rule)
        footer = QHBoxLayout()
        footer.setSpacing(components.COLUMNS_GAP)
        self.add = QPushButton(_('Add column'), self)
        self.add.setObjectName('zenColumnsAdd')
        self.add.setFlat(True)
        self.add.clicked.connect(self.add_column)
        self.reset_button = QPushButton(_('Reset'), self)
        self.reset_button.setObjectName('zenColumnsReset')
        self.reset_button.setFlat(True)
        self.reset_button.setToolTip(_('Back to the default columns'))
        self.reset_button.clicked.connect(self.reset)
        footer.addWidget(self.add)
        footer.addStretch(1)
        footer.addWidget(self.reset_button)
        column.addLayout(footer)

    def wanted(self) -> list[Column]:
        "The columns that match the search box."
        text = self.search.text().strip().casefold()
        return [c for c in columns_for(self.view) if not text or text in c.title.casefold() or text in c.key.casefold()]

    def rebuild(self, *args) -> None:
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        found = self.wanted()
        for column in found:
            self.rows.addWidget(ColumnRow(column, self))
        if not found:
            none = QLabel(_('No column matches.'), self.body)
            none.setObjectName('zenColumnsNone')
            self.rows.addWidget(none)
        self.rows.addStretch(1)
        ok, why = can_add(self.view)
        self.add.setEnabled(ok)
        self.add.setToolTip(why)

    def choose(self, key: str, on: bool) -> None:
        set_visible(self.view, key, on)
        self.rebuild()

    def shift(self, key: str, step: int) -> None:
        move(self.view, key, step)
        self.rebuild()

    def add_column(self) -> None:
        self.close()
        add_column(self.view)

    def reset(self) -> None:
        reset(self.view)
        self.search.clear()
        self.rebuild()

    def show_below(self) -> None:
        self.search.clear()
        self.rebuild()
        self.adjustSize()
        popovers.place(self, self.button, above=False, gap=components.COLUMNS_GAP)
        self.show()
        self.search.setFocus()


class ColumnsButton(QToolButton):
    "Columns, beside the Grid/Table switcher; there for the table only."

    def __init__(self, gui, parent=None):
        super().__init__(parent)
        self.setObjectName('zenColumnsButton')
        self.gui = gui
        self.panel = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setText(_('Columns'))
        self.setToolTip(_('Choose which columns the list shows, and in what order'))
        icon = registry.glyph_icon('columns')
        if icon is not None and not icon.isNull():
            self.setIcon(icon)
        self.clicked.connect(self.toggle_panel)

    def attach(self) -> None:
        "Follow the view switch, since the grid has no columns to choose, and the move to and from a device."
        grid = getattr(self.gui, 'grid_view_button', None)
        if grid is not None:
            grid.toggled.connect(self.refresh)
        locations = getattr(self.gui, 'location_manager', None)
        if locations is not None:
            locations.location_selected.connect(self.refresh)
        self.refresh()

    def view(self):
        "The list the button acts on: the device's when its books are in view, else the library's."
        current = getattr(self.gui, 'current_view', None)
        view = current() if callable(current) else None
        return view if view is not None else self.gui.library_view

    def refresh(self, *args) -> None:
        if self.panel is not None and self.panel.isVisible():
            self.panel.close()
        grid = getattr(self.gui, 'grid_view_button', None)
        on_grid = is_library(self.view()) and grid is not None and grid.isChecked()
        self.setVisible(not on_grid)

    def toggle_panel(self) -> None:
        view = self.view()
        if self.panel is None or self.panel.view is not view:
            if self.panel is not None:
                self.panel.deleteLater()
            self.panel = ColumnsPanel(self, view)
        if self.panel.isVisible():
            self.panel.close()
        else:
            self.panel.show_below()
