#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The list both search boxes fill: one row per `match.Entry`.

A row is the entry's icon, its title, the place it lives in under the title,
and its shortcut at the far end. Painted rather than laid out of widgets, so a
few hundred results cost nothing to show; the row's background is the style's
(`QStyledItemDelegate.paint` on an empty index, as filters/view.py does), so
hover and selection come from the sheet like every other list.

The search field keeps the keyboard. Up, Down, Page Up, Page Down and Enter
typed into it move and choose in the list (`ResultsView.follow`), so finding a
thing is type, arrow, Enter, without the focus ever leaving the box.
"""

from __future__ import annotations

from qt.core import (
    QAbstractListModel,
    QEvent,
    QFont,
    QKeySequence,
    QListView,
    QModelIndex,
    QObject,
    QPalette,
    QRect,
    QSize,
    QStyle,
    QStyledItemDelegate,
    Qt,
    pyqtSignal,
)

from calibre.gui2 import empty_index
from calibre_zen.theme.tokens import components

ENTRY_ROLE = Qt.ItemDataRole.UserRole


class ResultsModel(QAbstractListModel):
    "The entries on show. Replaced wholesale, never edited in place."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []

    def set_entries(self, entries) -> None:
        self.beginResetModel()
        self.entries = list(entries)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role == ENTRY_ROLE:
            return entry
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.title
        if role == Qt.ItemDataRole.ToolTipRole:
            return entry.where
        return None

    def flags(self, index):
        entry = self.data(index, ENTRY_ROLE)
        if entry is None:
            return Qt.ItemFlag.NoItemFlags
        if not entry.enabled:
            # Selectable, so the arrows walk through it, but greyed: a person
            # sees the action exists and that it is not available right now.
            return Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled


def shortcut_text(shortcut) -> str:
    "A QKeySequence, or its text, as the platform writes it."
    if isinstance(shortcut, QKeySequence):
        return shortcut.toString(QKeySequence.SequenceFormat.NativeText)
    return shortcut or ''


class ResultsDelegate(QStyledItemDelegate):
    "icon -- title over its place -- shortcut, laid out from the start edge."

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), components.FINDER_ROW_HEIGHT)

    def paint(self, painter, option, index) -> None:
        entry = index.data(ENTRY_ROLE)
        if entry is None:
            return super().paint(painter, option, index)
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        self.initStyleOption(option, index)
        painter.save()
        try:
            self._paint(painter, option, entry)
        finally:
            painter.restore()

    def _paint(self, painter, option, entry) -> None:
        rect = option.rect
        direction = option.direction
        pad, gap, icon = components.FINDER_PAD_X, components.FINDER_GAP, components.FINDER_ICON
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        pal = option.palette
        group = QPalette.ColorGroup.Normal if entry.enabled else QPalette.ColorGroup.Disabled
        text_role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        text = pal.color(group, text_role)
        # On the selection fill the second line keeps the fill's own text colour:
        # a muted grey there is the one colour that can vanish into it.
        muted = text if selected else pal.color(QPalette.ColorGroup.Normal, QPalette.ColorRole.PlaceholderText)

        def visual(r: QRect) -> QRect:
            # Laid out as if left to right, then mirrored for a right-to-left window.
            return QStyle.visualRect(direction, rect, r)

        start = rect.left() + pad
        if entry.icon is not None and not entry.icon.isNull():
            r = QRect(start, rect.top() + (rect.height() - icon) // 2, icon, icon)
            mode = entry.icon.Mode.Normal if entry.enabled else entry.icon.Mode.Disabled
            entry.icon.paint(painter, visual(r), Qt.AlignmentFlag.AlignCenter, mode)
        start += icon + gap
        end = rect.right() - pad

        caption = QFont(option.font)
        caption.setPixelSize(components.FONT_SIZE_CAPTION)
        shortcut = shortcut_text(entry.shortcut)
        if shortcut:
            painter.setFont(caption)
            width = painter.fontMetrics().horizontalAdvance(shortcut)
            r = QRect(end - width, rect.top(), width, rect.height())
            painter.setPen(muted)
            # Key names read left to right in any window: Ctrl+K, never K+Ctrl.
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.drawText(visual(r), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter, shortcut)
            painter.setLayoutDirection(direction)
            end -= width + gap

        width = max(0, end - start)
        align = Qt.AlignmentFlag.AlignAbsolute | (Qt.AlignmentFlag.AlignRight if direction == Qt.LayoutDirection.RightToLeft else Qt.AlignmentFlag.AlignLeft)
        line = components.FINDER_LINE_GAP
        title_font = QFont(option.font)
        painter.setFont(title_font)
        title_h = painter.fontMetrics().height()
        painter.setFont(caption)
        where_h = painter.fontMetrics().height() if entry.where else 0
        top = rect.top() + (rect.height() - title_h - (where_h + line if where_h else 0)) // 2

        painter.setFont(title_font)
        painter.setPen(text)
        title = painter.fontMetrics().elidedText(entry.title, Qt.TextElideMode.ElideRight, width)
        painter.drawText(visual(QRect(start, top, width, title_h)), align | Qt.AlignmentFlag.AlignVCenter, title)
        if where_h:
            painter.setFont(caption)
            painter.setPen(muted)
            where = painter.fontMetrics().elidedText(entry.where, Qt.TextElideMode.ElideRight, width)
            painter.drawText(visual(QRect(start, top + title_h + line, width, where_h)), align | Qt.AlignmentFlag.AlignVCenter, where)


class ResultsView(QListView):
    "The list. `chosen` is emitted with the Entry a click or Enter picked."

    chosen = pyqtSignal(object)

    # Keys typed into the search field that belong to the list.
    MOVES = {
        Qt.Key.Key_Down: QListView.CursorAction.MoveDown,
        Qt.Key.Key_Up: QListView.CursorAction.MoveUp,
        Qt.Key.Key_PageDown: QListView.CursorAction.MovePageDown,
        Qt.Key.Key_PageUp: QListView.CursorAction.MovePageUp,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('zenFinderResults')
        self.results = ResultsModel(self)
        self.setModel(self.results)
        self.setItemDelegate(ResultsDelegate(self))
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clicked.connect(self._choose_index)
        self._keys = _FieldKeys(self)

    def show_entries(self, entries) -> None:
        "Fill the list and select its first row, which Enter then chooses."
        self.results.set_entries(entries)
        if self.results.entries:
            self.setCurrentIndex(self.results.index(0))
        self.scrollToTop()

    def current_entry(self):
        return self.results.data(self.currentIndex(), ENTRY_ROLE)

    def choose_current(self) -> bool:
        entry = self.current_entry()
        if entry is None or not entry.enabled:
            return False
        self.chosen.emit(entry)
        return True

    def _choose_index(self, index) -> None:
        if index.isValid():
            self.setCurrentIndex(index)
            self.choose_current()

    def follow(self, field) -> None:
        "Let `field`, the search box, drive this list from the keyboard."
        field.installEventFilter(self._keys)

    def step(self, key) -> bool:
        action = self.MOVES.get(key)
        if action is None or not self.results.entries:
            return False
        self.setCurrentIndex(self.moveCursor(action, Qt.KeyboardModifier.NoModifier))
        return True


class _FieldKeys(QObject):
    "The search field's arrows and Enter, handed to the list."

    def __init__(self, view: ResultsView):
        super().__init__(view)
        self.view = view

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.KeyPress:
            key = ev.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.view.choose_current()
                return True
            if self.view.step(key):
                return True
        return False
