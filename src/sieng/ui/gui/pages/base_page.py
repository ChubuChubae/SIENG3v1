"""What every page shares: a scroll area, a status line, and how a job is run.

The run helper is the important part. Every page that does real work has the same four
needs, and they are easy to get subtly wrong in four different ways:

    keep a reference to the job    a QThread with no reference is destroyed mid-run
    disable the button             or a user starts a second embed over the first
    re-enable it on both paths     including the failure path, or the page is stuck
    never touch a widget from the worker thread

`run_job` does all four. A page supplies a function of one argument, the RunContext, and
two callbacks for what to do with the outcome.
"""

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sieng.pipeline.context import RunContext
from sieng.ui.gui.components.widgets import PageHeader, label
from sieng.ui.gui.components.worker import BackgroundJob


class BasePage(QWidget):
    """A scrollable column of cards with a status line under them."""

    def __init__(self, container: Any, title: str = "", subtitle: str = "") -> None:
        super().__init__()
        self.container = container
        self._job: BackgroundJob | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("pageScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        inner = QWidget()
        self.column = QVBoxLayout(inner)
        self.column.setContentsMargins(30, 26, 30, 26)
        self.column.setSpacing(18)
        scroll.setWidget(inner)

        self.header = PageHeader(title, subtitle)
        if title:
            self.column.addWidget(self.header)

        # A 4px strip at the bottom of a scrolling page is not feedback. This one is tall
        # enough to notice, shows its percentage, and sits directly above the status line.
        self.progress = QProgressBar()
        self.progress.setObjectName("workProgress")
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setFixedHeight(18)
        self.progress.hide()
        progress_row = QWidget()
        progress_layout = QVBoxLayout(progress_row)
        progress_layout.setContentsMargins(30, 8, 30, 0)
        progress_layout.addWidget(self.progress)
        outer.addWidget(progress_row)

        self.status = label("", "statusLabel")
        self.status.setContentsMargins(30, 8, 30, 12)
        outer.addWidget(self.status)

    # ---- running work ------------------------------------------------------

    def run_job(
        self,
        job: Callable[[RunContext], Any],
        on_success: Callable[[Any], None],
        on_failure: Callable[[BaseException], None],
        busy_widgets: list[QWidget] | None = None,
    ) -> None:
        """Run `job` off the UI thread and hand the outcome to one of the callbacks."""
        if self._job is not None and self._job.is_running():
            self.say("Something is already running on this page")
            return

        widgets = busy_widgets or []
        for widget in widgets:
            widget.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.job_state_changed(running=True)

        # Held on the page, not in a local, or the QThread is collected while running.
        self._job = BackgroundJob(job)
        self._job.worker.progress.connect(self._on_progress)
        self._job.worker.finished.connect(lambda result: self._done(widgets, on_success, result))
        self._job.worker.failed.connect(lambda error: self._done(widgets, on_failure, error))
        self._job.start()

    def cancel_job(self) -> None:
        if self._job is not None and self._job.is_running():
            self._job.cancel()
            self.say("Stopping at the next step", "busy")

    def job_state_changed(self, running: bool) -> None:
        """Called when work starts and when it ends. Pages override to show a Stop button."""

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.say(message, "busy")

    def _done(
        self,
        widgets: list[QWidget],
        callback: Callable[[Any], None],
        outcome: Any,
    ) -> None:
        self.progress.hide()
        for widget in widgets:
            widget.setEnabled(True)
        self.job_state_changed(running=False)
        callback(outcome)

    # ---- small helpers -----------------------------------------------------

    def say(self, message: str, tone: str = "") -> None:
        """Set the status line. The tone colours it: good, bad, busy, or nothing."""
        self.status.setText(message)
        self.status.setProperty("tone", tone)
        style = self.status.style()
        if style is not None:
            style.unpolish(self.status)
            style.polish(self.status)

    def add(self, widget: QWidget) -> QWidget:
        self.column.addWidget(widget)
        return widget

    def finish(self) -> None:
        """Push the cards to the top. Call once, after the last one is added."""
        self.column.addStretch(1)


def password_field(placeholder: str = "Session password") -> QLineEdit:
    """A password box. Never echoes, never remembers, never has a reveal button.

    A reveal button is a small convenience and a large one for whoever is behind the user,
    and the value here unlocks every message in a session.
    """
    field = QLineEdit()
    field.setObjectName("formInput")
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setPlaceholderText(placeholder)
    field.setAlignment(Qt.AlignmentFlag.AlignLeft)
    return field
