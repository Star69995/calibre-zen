#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Settings open while jobs run; a change is held back only when it would clash.

calibre refuses at the door: with any job running, Preferences answers "Cannot
configure while there are running jobs", even to look at a page or change a
colour. A job runs in a worker process with the options it was queued with, so
most settings cannot reach one at all. Here the door is open, and the refusal
moves to the moment it matters -- saving a page that would interfere -- and says
why, which job is in the way, and what to do.

Two wraps, no upstream file edited:

`PreferencesAction.do_config`
    calibre's own check is `job_manager.has_jobs()`, the first thing the method
    asks. For that one question it is told no, once; everything else in the
    method (the restart owed, the dialog, the restart afterwards) is calibre's.

`Preferences.commit`
    The dialog's save. When a job is running and the page on show is one that
    clashes (CLASHES below, or any page that needs a restart to take effect),
    the save is stopped with `AbortCommit`, which the dialog already answers by
    leaving the person on the page with their edits intact, and a message is
    shown first. A page the person has not changed is never held back.

What clashes is data, not code: `CLASHES` maps a page's module name to the
reason, in the words the person reads. Moving a page in or out is one line.

Off with CALIBRE_ZEN_BUSY=0, which gives calibre's refusal back.
"""

from __future__ import annotations

import traceback

from calibre.utils.localization import _
from calibre_zen import features

_installed = False

# Pages that a running job can be hurt by, keyed by the module name under
# calibre.gui2.preferences. A page that restarts the program (`restart_critical`)
# is held back too, without being listed. To be confirmed by the survey of every
# page that U7 in docs/plans/ui-workflow asks for.
CLASHES = {
    'plugins': lambda: _('Adding, removing or switching off a plugin changes the code a running job is using.'),
}


def enabled() -> bool:
    return features.enabled('busy')


def clash_reason(page) -> str:
    """
    Why saving `page` (a Preferences widget) must wait for the jobs, or '' when
    it need not.
    """
    name = type(page).__module__.rsplit('.', 1)[-1]
    if name in CLASHES:
        return CLASHES[name]()
    if getattr(page, 'restart_critical', False):
        return _('This change only takes effect after a restart, and a restart ends the jobs that are running.')
    return ''


def running_jobs(manager) -> list:
    "The jobs that are running, for the message."
    return [j for j in manager.unfinished_jobs() if j.is_running]


def describe(job) -> str:
    "One line for a job: what it is and how far it has got."
    from calibre_zen.status.jobs_panel import job_title

    percent = getattr(job, 'percent', 0) or 0
    return f'{job_title(job)} ({int(percent)}%)' if percent else job_title(job)


def message(reason: str, jobs: list, limit: int = 5) -> str:
    "The body of the notice: the reason, then the jobs in the way."
    lines = [describe(j) for j in jobs[:limit]]
    if len(jobs) > limit:
        lines.append(_('and {} more').format(len(jobs) - limit))
    return reason + '\n\n' + _('Running now:') + '\n' + '\n'.join('• ' + x for x in lines)


def notice_box(parent, reason: str, jobs: list):
    "The notice that a save has to wait: what, why, and which jobs, with one way back."
    from qt.core import QMessageBox

    box = QMessageBox(QMessageBox.Icon.Information, _('Wait for the running jobs'), '', QMessageBox.StandardButton.Ok, parent)
    box.setText(_('This change has to wait until the jobs are done.'))
    box.setInformativeText(message(reason, jobs))
    box.button(QMessageBox.StandardButton.Ok).setText(_('Back to the page'))
    return box


def open_once(manager) -> None:
    """
    Make the next `has_jobs()` on `manager` answer no, then put it back. It is
    one question that is answered differently, not a switch left on while the
    dialog is open.
    """

    def has_jobs():
        manager.__dict__.pop('has_jobs', None)
        return False

    manager.has_jobs = has_jobs


def install() -> bool:
    "Wrap the two methods. Safe to call twice."
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2.actions.preferences import PreferencesAction
    from calibre.gui2.preferences import AbortCommit
    from calibre.gui2.preferences.main import Preferences

    orig_do_config = PreferencesAction.do_config
    orig_commit = Preferences.commit

    def do_config(self, *args, **kwargs):
        manager = self.gui.job_manager
        if manager.has_jobs():
            open_once(manager)
        try:
            return orig_do_config(self, *args, **kwargs)
        finally:
            manager.__dict__.pop('has_jobs', None)

    def commit(self, *args):
        try:
            hold_back = self.gui.job_manager.has_jobs() and self.bb_apply_enabled()
            reason = clash_reason(self.showing_widget) if hold_back else ''
        except Exception:
            traceback.print_exc()
            reason = ''
        if reason:
            self.zen_busy_notice(reason)
            raise AbortCommit
        return orig_commit(self, *args)

    def bb_apply_enabled(self) -> bool:
        from qt.core import QDialogButtonBox

        button = self.bb.button(QDialogButtonBox.StandardButton.Apply)
        return button is not None and button.isEnabled()

    def zen_busy_notice(self, reason: str) -> None:
        notice_box(self, reason, running_jobs(self.gui.job_manager)).exec()

    PreferencesAction.do_config = do_config
    Preferences.commit = commit
    Preferences.bb_apply_enabled = bb_apply_enabled
    Preferences.zen_busy_notice = zen_busy_notice
    _installed = True
    return True
