"""Removing a session, and telling the user exactly what was removed.

Deleting a session is not one file. There is the ratchet state, the pool of skipped keys
inside it, and whatever caches the run left behind. If any one of those survives, the
session is not gone, and the user believes it is.

So the report is part of the feature rather than a nicety. A user who has just destroyed a
session in a hurry needs to be able to check, and "done" is not something they can check.
Anything that could not be removed is named, because a silent failure here is the worst
possible outcome: the user acts as though the material is gone when it is still on disk.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DestroyReport:
    """What was removed, and what was not."""

    session_id: bytes
    removed: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """True only when nothing was left behind."""
        return not self.failed

    def summary(self) -> str:
        """One line a user can act on, not a status word they have to trust."""
        name = self.session_id.hex()
        if self.failed:
            names = ", ".join(str(path) for path, _ in self.failed)
            return (
                f"Session {name}: removed {len(self.removed)} file(s), but {len(self.failed)} "
                f"could not be removed and still hold key material: {names}"
            )
        return f"Session {name}: removed {len(self.removed)} file(s), nothing left behind"


def destroy_session(session_id: bytes, paths: list[Path]) -> DestroyReport:
    """Delete every file belonging to a session and report on each one.

    Every path is attempted even after one fails, because stopping at the first error
    would leave more behind than necessary and the report would be misleading about the
    rest.

    The files are overwritten before being unlinked. On a journalling or copy-on-write
    filesystem, or on any SSD, that does not reliably destroy the old blocks: the
    controller may have written the new data elsewhere. It is worth doing because it
    costs nothing and helps on the simple cases, and it is documented as insufficient
    because a user should not believe more than it delivers.
    """
    report = DestroyReport(session_id=session_id)
    for path in paths:
        if not path.exists():
            report.missing.append(path)
            continue
        try:
            _overwrite(path)
            path.unlink()
            report.removed.append(path)
        except OSError as error:
            report.failed.append((path, str(error)))
    return report


def _overwrite(path: Path) -> None:
    """Write zeros over a file's current contents before it is unlinked.

    Best effort, for the same reasons zeroize.py gives about memory. The filesystem
    decides where bytes actually land and this cannot make it put them in the old place.
    """
    size = path.stat().st_size
    with path.open("r+b") as handle:
        handle.write(b"\x00" * size)
        handle.flush()
