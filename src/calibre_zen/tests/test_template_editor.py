#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The template editor in the theme (template_editor.py): separators as tall as
the buttons beside them, a button row that mirrors right to left, code and
its notes left to right, line numbers on the field's colour, result cells
without a field's frame, and a first size that fits the content.
"""

from calibre_zen import template_editor
from calibre_zen.tests.base import ZenTestCase, process_events

NOTES = 'Notes:\n* one\n* two'


class TestTemplateEditor(ZenTestCase):
    def dialog(self, rtl=False, placeholder=True):
        from qt.core import QApplication, Qt

        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.gui2.dialogs.template_dialog import TemplateDialog

        app = QApplication.instance()
        if rtl:
            app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.addCleanup(app.setLayoutDirection, Qt.LayoutDirection.LeftToRight)
        mi = Metadata("Galileo's Ring of Fire", ['Ann Author'])
        d = TemplateDialog(None, NOTES, mi=mi, text_is_placeholder=placeholder)
        self.addCleanup(d.deleteLater)
        self.addCleanup(d.close)
        d.show()
        process_events(50)
        return d

    def test_installed(self):
        self.assertTrue(template_editor.install())

    def test_separators_are_as_tall_as_the_buttons(self):
        from calibre.gui2.widgets2 import Separator

        d = self.dialog()
        seps = d.findChildren(Separator)
        self.assertTrue(seps)
        for s in seps:
            self.assertEqual(s.height(), s.widget_for_height.sizeHint().height())

    def test_the_button_row_mirrors_right_to_left(self):
        def order(d):
            boxes = (d.run_as_you_type_box, d.go_button, d.break_box)
            return [b.mapTo(d, b.rect().topLeft()).x() for b in boxes]

        ltr = order(self.dialog())
        self.assertEqual(ltr, sorted(ltr))
        rtl = order(self.dialog(rtl=True))
        self.assertEqual(rtl, sorted(rtl, reverse=True))

    def test_code_stays_left_to_right(self):
        from qt.core import Qt

        d = self.dialog(rtl=True)
        self.assertEqual(d.textbox.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        self.assertEqual(d.textbox.placeholderText(), NOTES)

    def test_the_notes_are_painted_at_the_left(self):
        from qt.core import QColor

        d = self.dialog(rtl=True)
        img = d.textbox.viewport().grab().toImage()
        inked = [x for x in range(img.width()) for y in range(img.height() // 3) if QColor(img.pixel(x, y)) != QColor(img.pixel(0, 0))]
        self.assertTrue(inked, 'the notes are painted')
        self.assertLess(min(inked), img.width() // 4)

    def test_line_numbers_are_on_the_field(self):
        from qt.core import QPalette

        d = self.dialog()
        tb = d.textbox
        self.assertEqual(tb.line_number_palette.color(QPalette.ColorRole.Base), tb.palette().color(QPalette.ColorRole.Base))

    def test_result_cells_have_no_frame(self):
        d = self.dialog()
        cell = d.template_value.cellWidget(0, 0)
        self.assertLessEqual(cell.minimumSizeHint().height(), d.template_value.rowHeight(0))
        self.assertEqual(cell.cursorPosition(), 0, 'the title is shown from its start')

    def test_first_size_fits_the_content(self):
        d = self.dialog()
        want = d.scroll_area.widget().sizeHint()
        hint = d.sizeHint()
        room = d.screen().availableSize()
        self.assertGreaterEqual(hint.width(), min(want.width(), int(room.width() * template_editor.SCREEN_SHARE)))
        self.assertGreaterEqual(hint.height(), min(want.height(), int(room.height() * template_editor.SCREEN_SHARE)))
