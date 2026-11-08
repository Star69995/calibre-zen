#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
calibre's template editor, in the theme.

`dialogs.template_dialog.TemplateDialog` is one dialog behind many doors: a
template column, a column's tooltip, colouring and icon rules, Save to disk,
the template tester. Under the sheet it came out worse than stock in four
places, and three of them are painted by calibre itself, out of a
stylesheet's reach. Two more were as wrong stock, in Hebrew:

- `widgets2.Separator`, the upright line between groups of buttons in its
  flow layout, asks the button beside it for a height. Built from a .ui file
  it asks before it is told which button, so the layout keeps the 1x1 it got
  and the line is a speck in the text colour. The wrap reads the button's
  size hint, has the layout ask again once the button is named, and draws a
  hairline in the border colour.
- `CodeEditor`, the template text, takes its line-number gutter from the book
  editor's syntax theme: a slate band with yellow numbers inside a field that
  is otherwise the page's base colour. The wrap gives the gutter the field's
  own base and the numbers the muted text colour, the current line's in the
  text colour.
- The dialog opens at its size hint when it has no saved size, and stock that
  is a scroll area's: everything after the first lines is behind a scroll bar.
  The wrap asks for the room the content wants, as much of the screen as
  `SCREEN_SHARE` allows.

- `widgets2.FlowLayout`, which holds the editor's row of buttons (and a few
  other dialogs' rows), places its items left to right whatever the
  direction, so in Hebrew the row reads backwards against the rest of the
  window. The wrap mirrors each item's place in a right-to-left layout.
- The template text is program code and stays left to right, gutter and all,
  as code does in a right-to-left window; stock it is right-aligned with its
  line numbers on the far side.

The fourth is the sheet's: the result table's cells are line edits, which
the field rule gives a border, a radius and a minimum height that a table row
cannot hold. 26-template.qss takes them back off. The title is also shown
from its start rather than its end, which is what a line edit scrolls to.

Off with CALIBRE_ZEN_TEMPLATE=0.
"""

from calibre_zen import features

_installed = False

# How far a separator stops short of the buttons' top and bottom edges.
SEPARATOR_INSET = 6
# The most of the screen's free area the dialog asks for when it opens with no
# saved size; the rest stays behind the scroll bar as it does stock.
SCREEN_SHARE = 0.85


def enabled() -> bool:
    return features.enabled('template-editor')


def install() -> bool:
    "Wrap the editor. Safe to call twice. Needs a QApplication."
    global _installed
    if _installed or not enabled():
        return _installed
    _patch_separator()
    _patch_flow_layout()
    _patch_code_editor()
    _patch_dialog()
    _installed = True
    return True


def _patch_separator() -> None:
    from qt.core import QColor, QPainter, QSize

    from calibre.gui2.widgets2 import Separator
    from calibre_zen.theme import rewrite

    orig_set_buddy = Separator.setBuddy

    def setBuddy(self, widget_for_height):
        orig_set_buddy(self, widget_for_height)
        # A .ui file names the buddy after the layout has already asked.
        self.updateGeometry()

    def sizeHint(self):
        buddy = self.widget_for_height
        height = buddy.sizeHint().height() if buddy is not None else self.fontMetrics().height()
        return QSize(1, height)

    def paintEvent(self, ev):
        r = self.rect().adjusted(0, SEPARATOR_INSET, 0, -SEPARATOR_INSET)
        if r.height() <= 0:
            return
        p = QPainter(self)
        p.fillRect(r, QColor(rewrite.chrome().border))
        p.end()

    Separator.setBuddy = setBuddy
    Separator.sizeHint = sizeHint
    Separator.paintEvent = paintEvent


def _patch_flow_layout() -> None:
    from qt.core import QStyle, Qt

    from calibre.gui2.widgets2 import FlowLayout

    orig_set_geometry = FlowLayout.setGeometry

    def setGeometry(self, rect):
        orig_set_geometry(self, rect)
        owner = self.parentWidget()
        if owner is None or owner.layoutDirection() != Qt.LayoutDirection.RightToLeft:
            return
        for item in self.items:
            item.setGeometry(QStyle.visualRect(Qt.LayoutDirection.RightToLeft, rect, item.geometry()))

    FlowLayout.setGeometry = setGeometry


def _patch_code_editor() -> None:
    from qt.core import QColor, QPainter, QPalette, Qt

    from calibre.gui2.dialogs.template_dialog_code_widget import CodeEditor
    from calibre_zen.theme import rewrite

    ltr = Qt.LayoutDirection.LeftToRight
    orig_init = CodeEditor.__init__
    orig_paint = CodeEditor.paintEvent

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.setLayoutDirection(ltr)
        self.zen_placeholder = ''
        chrome = rewrite.chrome()
        pal = self.line_number_palette
        pal.setColor(QPalette.ColorRole.Base, self.palette().color(QPalette.ColorRole.Base))
        pal.setColor(QPalette.ColorRole.Text, QColor(chrome.muted))
        pal.setColor(QPalette.ColorRole.BrightText, self.palette().color(QPalette.ColorRole.Text))

    # Qt aligns a plain text edit's placeholder by the application's direction,
    # not the widget's, so in Hebrew the notes calibre puts there sit on the
    # right of a left-to-right editor. The editor keeps the text and paints it.
    def setPlaceholderText(self, text):
        self.zen_placeholder = text
        self.viewport().update()

    def placeholderText(self):
        return self.zen_placeholder

    def paintEvent(self, ev):
        orig_paint(self, ev)
        if not self.zen_placeholder or not self.document().isEmpty():
            return
        # Where the first line of text would be, so the notes sit on it.
        first = self.blockBoundingGeometry(self.document().firstBlock()).translated(self.contentOffset())
        margin = int(self.document().documentMargin())
        rect = self.viewport().rect().adjusted(margin, int(first.top()), -margin, 0)
        p = QPainter(self.viewport())
        p.setLayoutDirection(ltr)
        p.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        p.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.zen_placeholder)
        p.end()

    CodeEditor.__init__ = __init__
    CodeEditor.setPlaceholderText = setPlaceholderText
    CodeEditor.placeholderText = placeholderText
    CodeEditor.paintEvent = paintEvent


def _patch_dialog() -> None:
    from qt.core import QApplication, QLineEdit, QSize, QStyle

    from calibre.gui2.dialogs.template_dialog import TemplateDialog

    orig_size_hint = TemplateDialog.sizeHint
    orig_setup = TemplateDialog.setup_result_display_table

    def sizeHint(self):
        hint = orig_size_hint(self)
        area = getattr(self, 'scroll_area', None)
        content = area.widget() if area is not None else None
        if content is None:
            return hint
        # What the dialog adds around the scroll area stays; the area itself
        # is swapped for what its content wants, plus its frame and a scroll
        # bar's width for when the screen cuts it short.
        frame = 2 * area.frameWidth()
        bar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        around = hint - area.sizeHint()
        want = content.sizeHint() + QSize(frame + bar, frame) + around
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return want.expandedTo(hint)
        free = screen.availableSize()
        room = QSize(int(free.width() * SCREEN_SHARE), int(free.height() * SCREEN_SHARE))
        return want.boundedTo(room).expandedTo(hint)

    def setup_result_display_table(self):
        orig_setup(self)
        tv = self.template_value
        for row in range(tv.rowCount()):
            cell = tv.cellWidget(row, 0)
            if isinstance(cell, QLineEdit):
                cell.home(False)

    TemplateDialog.sizeHint = sizeHint
    TemplateDialog.setup_result_display_table = setup_result_display_table
