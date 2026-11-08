#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What the jobs segment opens: each running job, how far it has got, and a way to
stop it.

A popup, not a window. It closes the moment anything else is clicked, so
nothing stays open on its own, and it works above a modal dialog, which a window
of its own would not: Preferences hides the status bar, and a dialog's footer
carries the same segment (`JobsSegment`, `footer.py`).

It reads the same manager the segment does and counts nothing itself. While it
is showing it re-reads on a timer, because the manager moves a job's percentage
without announcing it. The last line opens calibre's own Jobs window, which stays
the place for the log, the details and the finished jobs.
"""

from __future__ import annotations

from qt.core import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTimer, QToolButton, QVBoxLayout, QWidget, Qt

from calibre.utils.localization import ngettext
from calibre_zen import popovers
from calibre_zen.icons import registry
from calibre_zen.theme.tokens import components


def progress_text(job) -> str:
    "The words beside a job's bar: how far it is, or what it is waiting for."
    if job.run_state == job.RUNNING and (job.percent or 0) > 0:
        return f'{int(job.percent)}%'
    return str(job.status_text)


def can_stop(job) -> bool:
    "Whether Stop works: calibre refuses device jobs and ones that say they cannot be stopped."
    from calibre.gui2.jobs import DeviceJob

    return not isinstance(job, DeviceJob) and bool(getattr(job, 'killable', True)) and job.duration is None


def job_title(job) -> str:
    return (str(job.description).strip() if job.description else '') or _('Unnamed job')


class ElidedLabel(QLabel):
    "A label that shows as much of its text as there is room for, and all of it in the tooltip."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.full = ''
        self.setMinimumWidth(0)

    def set_full(self, text: str) -> None:
        self.full = text
        self.setToolTip(text)
        self.elide()

    def elide(self) -> None:
        self.setText(self.fontMetrics().elidedText(self.full, Qt.TextElideMode.ElideRight, max(0, self.width())))

    def resizeEvent(self, a0) -> None:
        super().resizeEvent(a0)
        self.elide()


class JobRow(QWidget):
    "One job: its name, a thin bar, the reading, and Stop."

    def __init__(self, job, panel):
        super().__init__(panel)
        self.job = job
        self.name = ElidedLabel(self)
        self.name.setObjectName('zenJobName')
        self.state = QLabel(self)
        self.state.setObjectName('zenJobState')
        self.bar = QProgressBar(self)
        self.bar.setObjectName('zenJobBar')
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.stop = QToolButton(self)
        self.stop.setObjectName('zenJobStop')
        self.stop.setAutoRaise(True)
        self.stop.setToolTip(_('Stop this job'))
        self.stop.setCursor(Qt.CursorShape.PointingHandCursor)
        icon = registry.glyph_icon('x', 'text')
        if icon is not None and not icon.isNull():
            self.stop.setIcon(icon)
        else:
            self.stop.setText('✕')
        self.stop.clicked.connect(lambda: panel.stop(job))

        top = QHBoxLayout()
        top.setSpacing(components.JOBS_PANEL_PAD)
        top.addWidget(self.name, 1)
        top.addWidget(self.state)
        top.addWidget(self.stop)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(components.JOBS_PANEL_PAD // 2)
        col.addLayout(top)
        col.addWidget(self.bar)
        self.refresh()

    def refresh(self) -> None:
        job = self.job
        self.name.set_full(job_title(job))
        self.state.setText(progress_text(job))
        self.bar.setValue(int(job.percent or 0))
        self.stop.setEnabled(can_stop(job))


class JobsPanel(QFrame):
    "The popup above a jobs segment."

    def __init__(self, segment):
        super().__init__(segment, Qt.WindowType.Popup)
        self.segment = segment
        self.setObjectName('zenJobsWindow')
        self.setFixedWidth(components.JOBS_PANEL_WIDTH)
        pad = components.JOBS_PANEL_PAD
        self.column = QVBoxLayout(popovers.painted_body(self, 'zenJobsPanel'))
        self.column.setContentsMargins(pad, pad, pad, pad)
        self.column.setSpacing(pad)
        self.rows: list[JobRow] = []
        self.key: tuple = ()
        self.timer = QTimer(self)
        self.timer.setInterval(components.JOBS_PANEL_REFRESH_MS)
        self.timer.timeout.connect(self.refresh)

    @property
    def manager(self):
        return getattr(self.segment.gui, 'job_manager', None)

    def jobs(self) -> list:
        manager = self.manager
        return [] if manager is None else list(manager.unfinished_jobs())

    def refresh(self) -> None:
        "Re-read the jobs: rebuild when the set changed, update the readings when it did not."
        jobs = self.jobs()
        key = (tuple(id(j) for j in jobs[: components.JOBS_PANEL_ROWS]), len(jobs))
        if key != self.key:
            self.key = key
            self.rebuild(jobs)
        else:
            for row in self.rows:
                row.refresh()

    def rebuild(self, jobs: list) -> None:
        while self.column.count():
            widget = self.column.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.rows = []
        if not jobs:
            none = QLabel(_('Nothing is running in the background'), self)
            none.setObjectName('zenJobsNone')
            self.column.addWidget(none)
        for job in jobs[: components.JOBS_PANEL_ROWS]:
            row = JobRow(job, self)
            self.rows.append(row)
            self.column.addWidget(row)
        hidden = len(jobs) - components.JOBS_PANEL_ROWS
        if hidden > 0:
            self.column.addWidget(QLabel(ngettext('and {} more job', 'and {} more jobs', hidden).format(hidden), self))
        rule = QFrame(self)
        rule.setObjectName('zenJobsRule')
        rule.setFrameShape(QFrame.Shape.HLine)
        self.column.addWidget(rule)
        everything = QPushButton(_('Open the Jobs window'), self)
        everything.setObjectName('zenJobsAll')
        everything.setFlat(True)
        everything.setCursor(Qt.CursorShape.PointingHandCursor)
        everything.clicked.connect(self.open_all)
        self.column.addWidget(everything)
        self.adjustSize()

    def stop(self, job) -> None:
        manager = self.manager
        if manager is not None:
            manager.kill_job(job, self.segment.window())
        self.refresh()

    def open_all(self) -> None:
        self.close()
        self.segment.open_list()

    def show_above(self) -> None:
        "Open over the segment, kept on the screen."
        self.key = ()
        self.refresh()
        popovers.place(self, self.segment, above=True, gap=components.STATUS_GAP)
        self.show()

    def showEvent(self, a0) -> None:
        super().showEvent(a0)
        self.timer.start()

    def hideEvent(self, a0) -> None:
        self.timer.stop()
        super().hideEvent(a0)
