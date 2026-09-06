"""Running pipeline work off the UI thread, and getting progress back safely.

Embedding into a 512x512 JPEG takes seconds: a J-UNIWARD cost map, then a trellis over
tens of thousands of coefficients. Doing that on the UI thread freezes the window, and a
frozen window is one the operating system offers to kill.

So the work runs in a QThread and talks back through signals. That is not a style
preference. Qt widgets may only be touched from the thread that created them, and a
progress callback invoked from a worker is running on the worker's thread. Signals are the
one mechanism that crosses the boundary correctly, so `RunContext`'s callback does nothing
but emit one.

Cancellation goes the other way. The UI sets the token from the main thread, the worker
checks it between phases, and `RunContext.step` raises `Cancelled` at the next boundary.
There is no way to interrupt a numpy call partway through, so "stop" means "stop soon".

What this deliberately does not do is interpret results. It hands back whatever the
pipeline returned, or whatever it raised, and the page decides what to say. Putting that
decision here would mean two places deciding how much an extraction failure may reveal.
"""

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from sieng.common.progress import ProgressReporter
from sieng.pipeline.context import CancelToken, RunContext


class Worker(QObject):
    """Runs one pipeline call and reports what happened.

    finished carries the result, failed carries the exception itself rather than a string,
    so the page can tell a capacity problem from a decryption failure and word each one
    the way that kind of failure should be worded.
    """

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, job: Callable[[RunContext], Any], token: CancelToken) -> None:
        super().__init__()
        self._job = job
        self._token = token

    def run(self) -> None:
        context = RunContext(
            progress=ProgressReporter(self._emit_progress),
            cancel=self._token,
        )
        try:
            self.finished.emit(self._job(context))
        except Exception as error:
            # Caught broadly on purpose. Anything the pipeline raises has to cross back to
            # the UI thread as a value, or it dies in the worker and the page waits forever.
            # What it means is the page's decision, not this file's.
            self.failed.emit(error)

    def _emit_progress(self, percent: int, message: str) -> None:
        """The only thing that crosses the thread boundary. Emit and return."""
        self.progress.emit(percent, message)


class BackgroundJob:
    """A worker and the thread it lives on, kept together so neither is collected early.

    A QThread whose only reference is a local variable is destroyed while it is still
    running, and Qt reports that as a crash rather than an error. Holding both here, and
    keeping a reference to this object on the page, is what prevents it.
    """

    def __init__(self, job: Callable[[RunContext], Any]) -> None:
        self.token = CancelToken()
        self.thread = QThread()
        self.worker = Worker(job, self.token)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._stop)
        self.worker.failed.connect(self._stop)

    def start(self) -> None:
        self.thread.start()

    def cancel(self) -> None:
        """Ask the work to stop. It stops at the next phase boundary, not immediately."""
        self.token.cancel()

    def is_running(self) -> bool:
        return self.thread.isRunning()

    def _stop(self, _result: object) -> None:
        self.thread.quit()
        self.thread.wait()
