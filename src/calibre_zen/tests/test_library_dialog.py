#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The Choose library dialog laid out as three choices (library_dialog.py): one
choice at a time, the folder and OK worded for it, copying offered only under
Create, and calibre's own accept() still doing the work.
"""

import os

from calibre_zen import library_dialog
from calibre_zen.tests.base import ZenTestCase, process_events


class DB:
    "What ChooseLibrary reads of a library before OK is pressed."

    def __init__(self, path):
        self.library_path = path

    def exists_at(self, loc):
        return os.path.exists(os.path.join(loc, 'metadata.db'))


class TestLibraryDialog(ZenTestCase):
    def dialog(self):
        from calibre.gui2.dialogs.choose_library import ChooseLibrary

        self.called = []
        d = ChooseLibrary(DB(os.path.join(self.tmp, 'Current')), lambda *a, **k: self.called.append((a, k)), None)
        self.addCleanup(d.deleteLater)
        return d

    def ok_text(self, d):
        from qt.core import QDialogButtonBox

        return d.buttonBox.button(QDialogButtonBox.StandardButton.Ok).text()

    def test_it_is_laid_out(self):
        d = self.dialog()
        self.assertIsInstance(getattr(d, 'zen_choose_library', None), library_dialog.Layout)
        from qt.core import QWidget

        self.assertIsNotNone(d.findChild(QWidget, 'zenLibraryDialog'))
        self.assertTrue(d.old_location.isHidden(), "calibre's sentence gives way to the card")
        self.assertTrue(d.nas_warning.isHidden(), "calibre's red warning gives way to the muted line")

    def test_one_choice_at_a_time(self):
        d = self.dialog()
        z = d.zen_choose_library
        for choice in library_dialog.CHOICES:
            z.choose(choice)
            self.assertEqual([c for c, b in z.buttons.items() if b.isChecked()], [choice])

    def test_the_folder_and_ok_are_worded_for_the_choice(self):
        d = self.dialog()
        z = d.zen_choose_library
        for choice in library_dialog.CHOICES:
            z.choose(choice)
            words = library_dialog.texts(choice)
            self.assertEqual(self.ok_text(d), words['ok'])
            self.assertEqual(z.where_title.text(), words['folder'])

    def test_copying_is_offered_only_under_create(self):
        d = self.dialog()
        z = d.zen_choose_library
        self.assertTrue(d.copy_structure.isHidden())
        z.choose(library_dialog.NEW)
        self.assertFalse(d.copy_structure.isHidden())
        self.assertTrue(d.copy_structure.isEnabled(), "calibre's own toggle still enables it")
        z.choose(library_dialog.MOVE)
        self.assertTrue(d.copy_structure.isHidden())

    def test_the_dialog_is_tall_enough_for_the_copy_box(self):
        d = self.dialog()
        d.zen_choose_library.choose(library_dialog.NEW)
        d.show()
        self.addCleanup(d.hide)
        process_events(50)
        self.assertGreaterEqual(d.copy_structure.height(), d.copy_structure.sizeHint().height())

    def test_calibre_still_does_the_work(self):
        d = self.dialog()
        target = self.mkdtemp()
        d.zen_choose_library.choose(library_dialog.NEW)
        d.copy_structure.setChecked(True)
        d.location.setText(target)
        d.accept()
        self.assertEqual(self.called, [((target,), {'copy_structure': True})])

    def test_a_path_keeps_its_order(self):
        self.assertEqual(library_dialog.split_path('/home/me/Calibre Library/'), ('Calibre Library', '/home/me'))
        self.assertEqual(library_dialog.split_path('/'), ('/', ''))
        text = library_dialog.isolated('/home/me')
        self.assertIn(library_dialog.LRI + '/home/me' + library_dialog.PDI, text)
