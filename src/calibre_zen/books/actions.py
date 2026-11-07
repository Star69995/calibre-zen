#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The two toolbar buttons: Goodreads Updater and Book Cleanup.

Qt and the window only; the work is in goodreads.py and epub.py. They are
InterfaceActions like calibre's own, so Preferences -> Toolbars & menus places
them and the shortcuts page lists them.
"""

import traceback

from qt.core import QApplication, QIcon, QMenu, QProgressDialog, Qt

from calibre.gui2 import error_dialog, info_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre_zen.books.epub import clean_book
from calibre_zen.books.goodreads import (
    LINKED_COLUMN,
    MissingColumnError,
    WrongColumnTypeError,
    create_linked_column,
    update_goodreads_linked,
)


class GoodreadsUpdaterAction(InterfaceAction):
    name = 'Goodreads Updater'

    action_spec = (_('Goodreads Updater'), None, _('Update the goodreads_linked column from the goodreads identifiers'), None)

    @property
    def title(self) -> str:
        return _('Goodreads Updater')

    def genesis(self) -> None:
        self.qaction.setIcon(QIcon.ic('identifiers.png'))
        self.qaction.triggered.connect(self.update_library)
        self.column_added_in: str | None = None  # the library a column was added to; it needs a restart

    def update_library(self) -> None:
        library = self.gui.current_db.library_path
        if self.column_added_in == library:
            self.offer_restart()
            return
        try:
            changed, total = update_goodreads_linked(self.gui.current_db.new_api)
        except MissingColumnError:
            self.offer_column(library)
            return
        except WrongColumnTypeError as e:
            error_dialog(self.gui, self.title, str(e), show=True)
            return

        if changed:
            self.gui.library_view.model().refresh_ids(list(changed))
            self.gui.tags_view.recount()
        info_dialog(self.gui, self.title, _('Checked {0} book(s), updated {1}.').format(total, len(changed)), show=True)

    def offer_column(self, library: str) -> None:
        asked = _("The library has no yes/no column '{0}' to keep in step with the goodreads identifiers.\n\nAdd it now?").format(LINKED_COLUMN)
        if not question_dialog(self.gui, self.title, asked):
            return
        create_linked_column(self.gui.current_db.new_api)
        self.column_added_in = library
        self.gui.must_restart_before_config = True  # as when Preferences adds a column
        self.offer_restart()

    def offer_restart(self) -> None:
        asked = _('The column is added, but calibre only sees a new column after it restarts. Restart calibre now, then click Goodreads Updater again?')
        if question_dialog(self.gui, self.title, asked):
            self.gui.quit(restart=True)


class BookCleanupAction(InterfaceAction):
    name = 'Book Cleanup'

    action_spec = (_('Book Cleanup'), None, _('Fix headings, broken paragraphs and punctuation in the selected EPUBs'), None)
    action_type = 'current'

    def genesis(self) -> None:
        self.qaction.setIcon(QIcon.ic('wizard.png'))
        self.qaction.triggered.connect(lambda: self.run(dry_run=False))
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)
        self.create_menu_action(self.menu, 'book_cleanup_clean', _('Clean selected books'), triggered=lambda: self.run(dry_run=False))
        self.create_menu_action(self.menu, 'book_cleanup_preview', _('Preview changes (modifies nothing)'), triggered=lambda: self.run(dry_run=True))

    def run(self, dry_run: bool) -> None:
        title = _('Book Cleanup')
        ids = list(self.gui.library_view.get_selected_ids())
        if not ids:
            error_dialog(self.gui, title, _('Select one or more books first.'), show=True)
            return
        if not dry_run and not question_dialog(
            self.gui,
            title,
            _('Clean the EPUB of {0} book(s)?\n\nThe original file is kept as ORIGINAL_EPUB the first time a book is changed.').format(len(ids)),
        ):
            return

        db = self.gui.current_db.new_api
        progress = QProgressDialog('', _('Cancel'), 0, len(ids), self.gui)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        reports, changed_ids, errors = [], [], []
        for i, book_id in enumerate(ids):
            progress.setValue(i)
            progress.setLabelText(db.field_for('title', book_id) or str(book_id))
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            try:
                report = clean_book(db, book_id, dry_run=dry_run)
            except Exception:
                errors.append(f'{db.field_for("title", book_id)}\n{traceback.format_exc()}')
                continue
            reports.append(report)
            if report.changed:
                changed_ids.append(book_id)
        progress.setValue(len(ids))

        if changed_ids and not dry_run:
            self.gui.library_view.model().refresh_ids(changed_ids)
        if dry_run:
            summary = _('Checked {0} book(s), would change {1}.').format(len(reports), len(changed_ids))
        else:
            summary = _('Checked {0} book(s), changed {1}.').format(len(reports), len(changed_ids))
        if errors:
            summary += '\n' + _('{0} book(s) failed, see details.').format(len(errors))
        details = '\n\n'.join([r.format() for r in reports] + errors)
        info_dialog(self.gui, title, summary, det_msg=details, show=True)
