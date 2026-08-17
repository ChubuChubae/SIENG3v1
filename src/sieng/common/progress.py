"""Progress reporting that survives being split across subtasks.

The old code defined update_progress() in three separate files and each one computed
its own percentage, so a pipeline of three steps reported 0-100 three times. scoped()
fixes that: a subtask still counts 0 to 100 in its own terms and the reporter maps it
into the slice of the overall run it was given.

    reporter = ProgressReporter(callback)
    cost = reporter.scoped(0, 40)  # cost model owns 0-40 percent
    coder = reporter.scoped(40, 95)  # stc owns 40-95 percent
    cost.step(50, "computing costs")  # caller sees 20 percent

Annotated in full because the strict layers import it (PROJECT_CONTEXT.md 2.2.1).
"""

from collections.abc import Callable

TOTAL = 100

ProgressCallback = Callable[[int, str], None]


class ProgressReporter:
    """Reports progress into a slice of the overall run."""

    def __init__(
        self, callback: ProgressCallback | None = None, low: float = 0, high: float = TOTAL
    ) -> None:
        if not 0 <= low <= high <= TOTAL:
            raise ValueError(
                f"Invalid progress range low={low} high={high}: "
                f"must satisfy 0 <= low <= high <= {TOTAL}"
            )
        self.callback = callback
        self.low = low
        self.high = high

    def step(self, percent: float, message: str) -> None:
        """Report percent (0-100 within this scope) and map it into the outer range."""
        percent = min(max(percent, 0), TOTAL)
        overall = self.low + (self.high - self.low) * percent / TOTAL
        if self.callback is not None:
            self.callback(int(overall), message)

    def scoped(self, low: float, high: float) -> "ProgressReporter":
        """Return a sub reporter that owns low..high of this reporter's own range."""
        span = self.high - self.low
        return ProgressReporter(
            self.callback,
            low=self.low + span * low / TOTAL,
            high=self.low + span * high / TOTAL,
        )

    def done(self, message: str = "done") -> None:
        """Jump straight to the top of this scope."""
        self.step(TOTAL, message)
