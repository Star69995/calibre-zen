#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The two toolbar buttons: Goodreads Updater and Book Cleanup.

Qt and the window only; the work is in goodreads.py and epub.py. They are
InterfaceActions like calibre's own, so Preferences -> Toolbars & menus places
them and the shortcuts page lists them.
"""

from functools import partial

from qt.core import QDialog, QIcon, QMenu

from calibre.gui2 import Dispatcher, error_dialog, info_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_zen.books.epub import ORIGINAL_FORMAT, books_with_original, clean_books, delete_originals
from calibre_zen.books.goodreads import LINKED_COLUMN, MissingColumnError, WrongColumnTypeError, create_linked_column, update_goodreads_linked

JOB_TYPE = 'book_cleanup'  # one at a time: two runs over the same books would race
STATUS_MESSAGE_MS = 5000


def ask_to_clean(parent, title: str, count: int) -> bool | None:
    "Whether to keep the originals, or None when the person backs out. Keeping is the default."
    box = MessageBox(MessageBox.QUESTION, title, _('Clean the EPUB of {0} book(s)?').format(count), parent=parent)
    keep = box.toggle_checkbox
    keep.setText(_('Keep the original file as {0}').format(ORIGINAL_FORMAT))
    keep.setChecked(True)
    keep.setVisible(True)
    box.resize_needed.emit()
    if box.exec() != QDialog.DialogCode.Accepted:
        return None
    return keep.isChecked()


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
        self.menu.addSeparator()
        self.create_menu_action(
            self.menu, 'book_cleanup_delete_originals', _('Delete the originals of selected books'), triggered=self.delete_selected_originals
        )

    def run(self, dry_run: bool) -> None:
        title = _('Book Cleanup')
        ids = list(self.gui.library_view.get_selected_ids())
        if not ids:
            error_dialog(self.gui, title, _('Select one or more books first.'), show=True)
            return
        keep_original = True
        if not dry_run:
            keep_original = ask_to_clean(self.gui, title, len(ids))
            if keep_original is None:
                return

        # One job for the whole selection, so it sits in the Jobs list with a progress
        # bar and a Stop button while the window stays usable. Its log is the report.
        description = _('Book Cleanup preview: {0} book(s)') if dry_run else _('Book Cleanup: {0} book(s)')
        job = ThreadedJob(
            JOB_TYPE,
            description.format(len(ids)),
            clean_books,
            (self.gui.current_db.new_api, ids, dry_run, keep_original),
            {},
            Dispatcher(partial(self.finished, dry_run)),
        )
        self.gui.job_manager.run_threaded_job(job)
        self.gui.jobs_pointer.start()

    def finished(self, dry_run: bool, job: ThreadedJob) -> None:
        title = _('Book Cleanup')
        result = job.result
        if job.failed and not job.killed:
            self.gui.job_exception(job, dialog_title=title)
            return
        if result is None:  # stopped before it began
            return
        if result.changed_ids and not dry_run:
            self.gui.library_view.model().refresh_ids(result.changed_ids)
        done, changed = len(result.reports), len(result.changed_ids)
        if dry_run:
            summary = _('Checked {0} book(s), would change {1}.').format(done, changed)
        else:
            summary = _('Checked {0} book(s), changed {1}.').format(done, changed)
        if job.killed:
            summary += '\n' + _('Stopped before the last books.')
        if result.errors:
            summary += '\n' + _('{0} book(s) failed, see details.').format(len(result.errors))
        if dry_run or result.errors:  # a preview has nothing else to show; a failure must not pass unseen
            details = '\n\n'.join([r.format() for r in result.reports] + result.errors)
            info_dialog(self.gui, title, summary, det_msg=details, show=True)
        else:
            self.gui.status_bar.show_message(summary, STATUS_MESSAGE_MS)

    def delete_selected_originals(self) -> None:
        title = _('Book Cleanup')
        ids = list(self.gui.library_view.get_selected_ids())
        if not ids:
            error_dialog(self.gui, title, _('Select one or more books first.'), show=True)
            return
        db = self.gui.current_db.new_api
        with_original = books_with_original(db, ids)
        if not with_original:
            info_dialog(self.gui, title, _('None of the selected books has an original to delete.'), show=True)
            return
        asked = _('Delete the original file ({0}) of {1} book(s)?\n\nThe cleaned EPUB stays. This cannot be undone.').format(
            ORIGINAL_FORMAT, len(with_original)
        )
        if not question_dialog(self.gui, title, asked, default_yes=False):
            return
        job = ThreadedJob(
            JOB_TYPE,
            _('Delete originals: {0} book(s)').format(len(with_original)),
            delete_originals,
            (db, with_original),
            {},
            Dispatcher(self.originals_deleted),
        )
        self.gui.job_manager.run_threaded_job(job)
        self.gui.jobs_pointer.start()

    def originals_deleted(self, job: ThreadedJob) -> None:
        if job.failed and not job.killed:
            self.gui.job_exception(job, dialog_title=_('Book Cleanup'))
            return
        removed = job.result or []
        if removed:
            self.gui.library_view.model().refresh_ids(removed)
        self.gui.status_bar.show_message(_('Deleted the original of {0} book(s).').format(len(removed)), STATUS_MESSAGE_MS)
