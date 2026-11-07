#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The "Choose your calibre library" dialog, as three plain choices.

calibre's dialog (`dialogs/choose_library.ChooseLibrary`) opens with a sentence
holding the current path, then an empty "New location" field before anything
says what the location is for, a WARNING in red, and three radio buttons whose
wording only makes sense once read together ("a previously existing library at
the chosen new location"). The question it asks -- what do you want to do --
comes last.

Here the same widgets are laid out in the order the question is asked:

1. **Current library**: its name and the folder it is in, in a card.
2. **What do you want to do?**: Switch, Create or Move, each a radio with one
   line under it saying what it does and what happens to this library. Copying
   the structure is offered under Create, and only while Create is chosen.
3. **The folder**: titled for the choice ("Library to open", "Where to create
   it", "Where to move it"), the field and a folder button on one row.
4. The network warning as a muted line with a sign, not a red word.

OK is named for the choice -- Switch, Create, Move.

Nothing calibre reads is replaced: the radios, the checkbox, the field and the
button box are calibre's own, moved into the new layout, so `accept()`,
`check_action()` and `perform_action()` run unchanged. Only calibre's sentence,
label, warning and "..." button are hidden; the folder button calls calibre's
`choose_loc`.

Off with `CALIBRE_ZEN_LIBRARY_DIALOG=0`, or "Library dialog" in the features menu.
"""

from __future__ import annotations

import os
import traceback

from qt.core import QApplication, QButtonGroup, QDialogButtonBox, QHBoxLayout, QLabel, QSize, Qt, QTimer, QVBoxLayout, QWidget

from calibre.utils.localization import _
from calibre_zen import features, forms
from calibre_zen.onboarding import parts
from calibre_zen.theme.tokens import components

EXISTING, NEW, MOVE = 'existing', 'new', 'move'
CHOICES = (EXISTING, NEW, MOVE)
NAS_FAQ = 'https://manual.calibre-ebook.com/faq.html#i-am-getting-errors-with-my-calibre-library-on-a-networked-drive-nas'
# A path is isolated left to right so it keeps its order, and the line is
# marked with the window's direction so it starts on the window's side.
LRI, PDI, LRM, RLM = '\u2066', '\u2069', '\u200e', '\u200f'

_installed = False


def enabled() -> bool:
    return features.enabled('library-dialog')


def at_start(text: str) -> str:
    "Text marked with the window's direction, so a line that opens with English still starts on the window's side."
    return (RLM if QApplication.isRightToLeft() else LRM) + text


def isolated(text: str) -> str:
    "A path as a line of its own: read left to right, aligned at the window's start."
    return at_start(LRI + text + PDI)


def split_path(path: str) -> tuple[str, str]:
    "The library's name and the folder it is in. A path with no name is all folder."
    path = path.rstrip('/\\') or path
    name = os.path.basename(path)
    return (name, os.path.dirname(path)) if name else (path, '')


def texts(choice: str) -> dict:
    "Everything that is worded for one choice. Translated when asked, not at import."
    return {
        EXISTING: {
            'title': _('&Switch to an existing library'),
            'note': _('Open a library that is already in another folder.'),
            'folder': _('Library to open'),
            'ok': _('Switch'),
        },
        NEW: {
            'title': _('&Create a new library'),
            'note': _('Start an empty library in a new or empty folder.'),
            'folder': _('Where to create it'),
            'ok': _('Create'),
        },
        MOVE: {
            'title': _('&Move this library'),
            'note': _('Move this library and all its books to an empty folder.'),
            'folder': _('Where to move it'),
            'ok': _('Move'),
        },
    }[choice]


class Option(QWidget):
    "A choice: the radio, the line under it, and anything else it offers. A click anywhere picks it."

    def __init__(self, button, note: str, parent=None):
        super().__init__(parent)
        self.button = button
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(components.ONBOARDING_OPTION_SPACING)
        button.setParent(self)
        button.show()
        self.column.addWidget(button)
        line = parts.note(self)
        # One line, not wrapped: a wrapping label makes the whole form's height
        # depend on its width, and a dialog sizes such a form short, squeezing
        # this row when the copy box appears under Create.
        line.setWordWrap(False)
        line.setText(at_start(note))
        self.column.addWidget(line)

    def add_extra(self, widget) -> None:
        "Something the choice offers, lined up under its label."
        row = QHBoxLayout()
        row.setContentsMargins(components.ONBOARDING_OPTION_INDENT, components.LIBRARY_EXTRA_GAP, 0, 0)
        widget.setParent(self)
        row.addWidget(widget)
        self.column.addLayout(row)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.button.setChecked(True)
            self.button.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseReleaseEvent(ev)


def glyph_label(parent, glyph: str, size: int) -> QLabel:
    "A glyph as a picture, or an empty label when the icon pack is off."
    from calibre_zen.icons import registry

    label = QLabel(parent)
    icon = registry.glyph_icon(glyph)
    if icon is not None and not icon.isNull():
        label.setPixmap(icon.pixmap(QSize(size, size)))
    label.setAlignment(Qt.AlignmentFlag.AlignTop)
    return label


def current_card(parent, library_path: str) -> QWidget:
    "The current library: a glyph, its name, and under it the folder it is in."
    name, folder = split_path(library_path)
    w = QWidget(parent)
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(components.FORM_LABEL_GAP)
    row.addWidget(glyph_label(w, 'books', components.LIBRARY_GLYPH))
    column = QVBoxLayout()
    column.setSpacing(components.ONBOARDING_OPTION_SPACING)
    title = QLabel(isolated(name), w)
    title.setObjectName('zenLibraryName')
    column.addWidget(title)
    if folder:
        where = QLabel(isolated(folder), w)
        where.setObjectName('zenLibraryFolder')
        where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(where)
    title.setToolTip(library_path)
    row.addLayout(column, 1)
    return w


def warning_line(parent) -> QWidget:
    "Why a library does not belong on a network drive, as a muted line with a sign."
    from calibre.utils.localization import localize_user_manual_link

    w = QWidget(parent)
    row = QHBoxLayout(w)
    row.setContentsMargins(components.FORM_ROW_PAD_X, 0, components.FORM_ROW_PAD_X, 0)
    row.setSpacing(components.LIBRARY_WARNING_GAP)
    row.addWidget(glyph_label(w, 'alert-triangle', components.FORM_SLOT_ICON))
    text = QLabel(w)
    text.setObjectName('zenLibraryWarning')
    text.setWordWrap(True)
    text.setOpenExternalLinks(True)
    link = localize_user_manual_link(NAS_FAQ)
    text.setText(
        _('Keep libraries off network drives and cloud-synced folders (Dropbox, OneDrive and the like): calibre can lose data there. <a href="{}">Why?</a>').format(
            link
        )
    )
    row.addWidget(text, 1)
    return w


class Layout:
    "The rebuilt dialog: what was made, and how it follows the choice."

    def __init__(self, dialog):
        self.dialog = dialog
        self.buttons = {EXISTING: dialog.existing_library, NEW: dialog.empty_library, MOVE: dialog.move_library}
        lp = dialog.db.library_path
        if isinstance(lp, bytes):
            from calibre.constants import filesystem_encoding

            lp = lp.decode(filesystem_encoding)

        body = QWidget(dialog)
        body.setObjectName('zenLibraryDialog')
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(components.FORM_SECTION_GAP)

        form = self.form = forms.Form(body, slots=1, fill=True)
        form.group(_('Current library')).block(current_card(body, lp))

        options = form.group(_('What do you want to do?'))
        self.options = {}
        # Each radio now sits in a row of its own, and auto-exclusive radios are
        # only exclusive among siblings: the group keeps one of them on.
        self.group = QButtonGroup(dialog)
        for choice in CHOICES:
            words = texts(choice)
            button = self.buttons[choice]
            button.setText(words['title'])
            self.group.addButton(button)
            self.options[choice] = option = Option(button, words['note'], body)
            options.block(option)
        copy = dialog.copy_structure
        copy.setText(_('Co&py columns, saved searches and settings from this library'))
        self.options[NEW].add_extra(copy)

        self.where = form.group(' ')
        self.where_title = self.where.findChild(QLabel, 'zenFormGroupTitle')
        location = dialog.location
        location.setMinimumContentsLength(components.LIBRARY_FIELD_CHARS)
        line = location.lineEdit()
        if line is not None:
            line.setPlaceholderText(_('Type a path, or choose a folder'))
        picker = parts.picker(body, dialog.choose_loc, _('Choose a folder'))
        self.where.block(self.field_row(body, location, picker))
        form.finish()
        column.addWidget(form)
        column.addWidget(warning_line(body))
        column.addStretch(1)
        dialog.buttonBox.setParent(body)
        column.addWidget(dialog.buttonBox)
        self.replace_grid(body)

        self.group.buttonToggled.connect(self.follow)
        body.setMinimumWidth(components.LIBRARY_DIALOG_WIDTH)
        self.follow()
        self.refit(dialog.copy_structure)

    @staticmethod
    def field_row(parent, location, picker) -> QWidget:
        w = QWidget(parent)
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(components.LIBRARY_WARNING_GAP)
        location.setParent(w)
        location.show()
        row.addWidget(location, 1)
        row.addWidget(picker)
        return w

    def replace_grid(self, body) -> None:
        """
        Empty calibre's grid -- its spacers, its sentence and label, the warning
        and the "..." button -- and put the new body in it alone. The widgets
        that moved left the grid when they were reparented.
        """
        grid = self.dialog.layout()
        kept = []
        while grid.count():
            item = grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
            kept.append(item)
        # Taken items are the caller's; held here so Python does not free a
        # layout Qt may still point a child at.
        self.dialog._zen_old_layout_items = kept
        grid.addWidget(body, 0, 0)

    def choice(self) -> str:
        return next((c for c, b in self.buttons.items() if b.isChecked()), EXISTING)

    def choose(self, choice: str) -> None:
        self.buttons[choice].setChecked(True)

    def follow(self, *args) -> None:
        "Word the folder and OK for the choice; offer copying only under Create."
        choice = self.choice()
        words = texts(choice)
        if self.where_title is not None:
            self.where_title.setText(words['folder'])
        ok = self.dialog.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(words['ok'])
        copy = self.dialog.copy_structure
        if copy.isHidden() == (choice == NEW):
            copy.setVisible(choice == NEW)
            self.refit(copy)

    def refit(self, changed) -> None:
        """
        Grow or shrink the dialog to its contents after `changed` was shown or
        hidden. Each layout above it caches its size, and a child shown before
        the dialog is on screen does not tell them, so they are told here.
        """
        w = changed.parentWidget()
        while w is not None:
            if w.layout() is not None:
                w.layout().invalidate()
            if w is self.dialog:
                break
            w = w.parentWidget()
        QTimer.singleShot(0, self.fit)

    def fit(self) -> None:
        """
        As tall as the contents need at the dialog's width. The warning wraps,
        so the height depends on the width, and Qt's own minimum and
        adjustSize() leave such a dialog short, squeezing the choices.
        """
        grid = self.dialog.layout()
        grid.activate()
        width = max(self.dialog.width(), grid.totalMinimumSize().width())
        height = grid.totalHeightForWidth(width) if grid.hasHeightForWidth() else grid.totalSizeHint().height()
        self.dialog.setMinimumHeight(height)
        self.dialog.resize(width, height)


def install() -> bool:
    "Wrap ChooseLibrary.__init__. Safe to call twice."
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2.dialogs.choose_library import ChooseLibrary

    orig = ChooseLibrary.__init__

    def __init__(self, db, callback, parent):
        orig(self, db, callback, parent)
        try:
            self.zen_choose_library = Layout(self)
        except Exception:
            # Half a layout is worse than calibre's; but calibre's widgets may
            # already have moved, so this is reported and the dialog left usable.
            traceback.print_exc()

    __init__.__wrapped__ = orig
    ChooseLibrary.__init__ = __init__
    _installed = True
    return True
