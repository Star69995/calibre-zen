#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The Update on device button.

Qt and the window only; what is replaced, and how, is in ondevice.py. It acts on
the library's selection, so "select all, update" refreshes every book that is on
the device and leaves the others alone.
"""

from qt.core import QIcon

from calibre.gui2 import FunctionDispatcher, error_dialog, info_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre_zen.books.ondevice import make_plan, replace_files, writer_for

STATUS_MESSAGE_MS = 5000
SHOWN_TITLES = 10  # how many titles a message lists before "and more"


def titles(items) -> str:
    "A few of the books' titles, one per line, for a message."
    shown = [i.title for i in items[:SHOWN_TITLES]]
    if len(items) > SHOWN_TITLES:
        shown.append(_('… and {0} more').format(len(items) - SHOWN_TITLES))
    return '\n'.join(shown)


def plan_notes(plan) -> str:
    "What the selection leaves out, and why."
    notes = []
    if plan.off_device:
        notes.append(_('{0} selected book(s) are not on the device.').format(len(plan.off_device)))
    if plan.no_format:
        notes.append(
            _('{0} file(s) on the device have no copy in the same format in the library, and are left as they are:').format(len(plan.no_format))
            + '\n'
            + titles(plan.no_format)
        )
    return '\n\n'.join(notes)


class UpdateOnDeviceAction(InterfaceAction):
    name = 'Update On Device'

    action_spec = (
        _('Update on device'),
        None,
        _("Replace the selected books' files on the connected device with the library's copy, in the same place on the device"),
        None,
    )
    action_type = 'current'
    default_add_to = frozenset({'toolbar-device'})

    @property
    def title(self) -> str:
        return _('Update on device')

    def genesis(self) -> None:
        self.qaction.setIcon(QIcon.ic('swap.png'))
        self.qaction.triggered.connect(self.run)

    def location_selected(self, loc: str) -> None:
        enabled = loc == 'library'  # it acts on the library's selection
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def connected_device(self):
        manager = self.gui.device_manager
        return manager.connected_device if manager.is_device_connected else None

    def run(self, *args) -> None:
        device = self.connected_device()
        if device is None:
            error_dialog(self.gui, self.title, _('Connect a device first.'), show=True)
            return
        if writer_for(device) is None:
            error_dialog(self.gui, self.title, _('Books cannot be replaced in place on this kind of device.'), show=True)
            return
        ids = list(self.gui.library_view.get_selected_ids())
        if not ids:
            error_dialog(self.gui, self.title, _('Select one or more books first.'), show=True)
            return

        api = self.gui.current_db.new_api
        plan = make_plan(self.gui.booklists(), ids, lambda book_id: {f.upper() for f in api.formats(book_id)})
        if not plan.items:
            info_dialog(self.gui, self.title, _('Nothing to update on the device.'), det_msg=plan_notes(plan), show=True)
            return
        asked = _(
            "Replace {0} file(s) on the device with the library's copy?\n\nEach file stays where it is on the device, in the format it has there."
        ).format(len(plan.items))
        if not question_dialog(self.gui, self.title, asked, det_msg=plan_notes(plan)):
            return

        description = _('Update on device: {0} book(s)').format(len(plan.items))
        self.gui.device_manager.create_job(
            replace_files,
            FunctionDispatcher(self.finished),
            description,
            args=[device, self.gui.current_db, plan.items],
        )
        self.gui.jobs_pointer.start()

    def finished(self, job) -> None:
        if job.failed:
            self.gui.device_job_exception(job)
            return
        outcome = job.result
        if outcome.written:
            self.refresh_listing(job, outcome.written)
        summary = _('Replaced {0} file(s) on the device.').format(len(outcome.written))
        if outcome.errors:
            summary += '\n' + _('{0} book(s) failed, see details.').format(len(outcome.errors))
        if outcome.errors or outcome.notes:  # a failure must not pass unseen
            lines = [f'{item.title}\n{text}' for item, text in outcome.errors + outcome.notes]
            info_dialog(self.gui, self.title, summary, det_msg='\n\n'.join(lines), show=True)
        else:
            self.gui.status_bar.show_message(summary, STATUS_MESSAGE_MS)

    def refresh_listing(self, job, written) -> None:
        "What calibre does once a send has finished (`books_uploaded`), for files that did not move."
        gui = self.gui
        gui.device_manager.add_books_to_metadata([w.location for w in written], [w.metadata for w in written], gui.booklists())
        if not gui.set_books_in_library(gui.booklists(), reset=True, add_as_step_to_job=job, do_device_sync=False):
            gui.upload_booklists(job)
        gui.refresh_ondevice()
        for view in (gui.memory_view, gui.card_a_view, gui.card_b_view):
            view._model.resort(reset=False)
            view._model.research()
