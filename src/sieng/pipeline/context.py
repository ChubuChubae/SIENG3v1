"""RunContext: the three things every step of a run needs, carried in one object.

    progress    where to report to, so the ui can show a bar without the pipeline
                knowing a ui exists
    logger      already redacting, so a step cannot accidentally log key material
    cancel      a token the ui sets when the user presses stop

Passing one object rather than three arguments is not tidiness. It means a new concern can
be added later without changing every signature between here and the bottom of the stack,
and it gives one place to say what a step is and is not allowed to do with them.

Cancellation is cooperative. There is no way to interrupt a numpy call partway through, so
a step checks between phases and stops at the next boundary. `check()` raises so a caller
cannot forget to act on the answer.

A cancelled run must leave nothing behind, and for embedding that means the ratchet state
too: a counter handed out and then abandoned is spent, not returned. `session.send()`
already commits before it hands keys over, so cancelling after that point wastes a counter
and nothing worse. Cancelling before it changes nothing at all.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Final

from sieng.common.errors import PipelineError
from sieng.common.logging import get_logger
from sieng.common.progress import ProgressReporter

DEFAULT_LOGGER: Final = "sieng.pipeline"


class Cancelled(PipelineError):
    """The user asked to stop. Not an error in the run, so it is reported as itself."""


class CancelToken:
    """A flag one thread sets and another checks. Nothing more, deliberately.

    Thread safe because the ui sets it from the event loop while the pipeline reads it
    from a worker. `threading.Event` already does exactly this, so it is wrapped rather
    than reimplemented, and the wrapper exists only to give the two operations names that
    say what they mean here.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise if cancellation was requested.

        Raises rather than returning a bool, because a caller that ignores a returned
        False keeps working and a caller that ignores an exception cannot.
        """
        if self._event.is_set():
            raise Cancelled("The run was cancelled")

    def reset(self) -> None:
        """For reusing a token across runs. Never called mid-run."""
        self._event.clear()


@dataclass
class RunContext:
    """Everything a pipeline step needs that is not data."""

    progress: ProgressReporter = field(default_factory=ProgressReporter)
    logger: logging.Logger = field(default_factory=lambda: get_logger(DEFAULT_LOGGER))
    cancel: CancelToken = field(default_factory=CancelToken)

    def step(self, percent: float, message: str) -> None:
        """Report progress and check for cancellation in one call.

        Together because they belong at the same points: the boundaries between phases.
        A step that reports progress without checking is a step that cannot be stopped.
        """
        self.cancel.check()
        self.progress.step(percent, message)

    def scoped(self, low: float, high: float, name: str | None = None) -> "RunContext":
        """A context owning part of this one's progress range.

        So an engine can report 0 to 100 of its own work without knowing it occupies 20 to
        60 of the whole run. The logger and the cancel token are shared, not copied: one
        cancellation must stop everything.
        """
        return RunContext(
            progress=self.progress.scoped(low, high),
            logger=self.logger.getChild(name) if name else self.logger,
            cancel=self.cancel,
        )
