"""An exclusive lock held across the whole read-modify-write, not just the write.

The mistake this file exists to prevent is subtle enough to be worth spelling out. Suppose
the lock were taken only around saving:

    process A   loads state, counter is 5
    process B   loads state, counter is 5
    process A   ratchets to 6, takes the lock, saves, releases
    process B   ratchets to 6, takes the lock, saves, releases

Both processes hand out counter 5. Every write was correctly serialised, and the result is
still two messages sharing a key. The lock has to be held from before the load until after
the save, so the second process reads what the first one wrote.

Under GCM-SIV that is survivable rather than catastrophic: reusing a nonce reveals whether
two plaintexts were identical and nothing more. That is why the AEAD was chosen. It is not
a reason to allow it.

The implementation is `portalocker`, which gives one interface over flock on Unix and
LockFileEx on Windows. Both are advisory: they stop other processes that ask for the same
lock, and do nothing about a process that ignores locking entirely. Since the only program
touching these files is this one, that is enough.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Final

import portalocker

from sieng.common.errors import CryptoError

# How long to wait for another process before giving up. Long enough for a normal embed to
# finish, short enough that a stale lock does not look like a hang.
TIMEOUT_SECONDS: Final = 30.0

# How often to retry while waiting. Short enough not to add noticeable delay, long enough
# not to spin.
POLL_SECONDS: Final = 0.05

LOCK_SUFFIX: Final = ".lock"


def lock_path_for(state_path: Path) -> Path:
    """The lock file beside the state file.

    A separate file rather than locking the state file itself, because the state file is
    replaced by rename on every commit. Locking a file that is about to be unlinked means
    holding a lock on something that no longer has a name.
    """
    return Path(str(state_path) + LOCK_SUFFIX)


@contextmanager
def exclusive(state_path: Path, timeout: float = TIMEOUT_SECONDS) -> Iterator[None]:
    """Hold an exclusive lock for the whole block.

    Wrap the entire sequence in this: load, check, ratchet, save. Wrapping only the save
    is the bug described at the top of this file.
    """
    path = lock_path_for(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle: IO[Any] | None = None
    try:
        handle = path.open("a+b")
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException:
            _wait_for(handle, path, timeout)
        yield
    finally:
        if handle is not None:
            try:
                portalocker.unlock(handle)
            finally:
                handle.close()


def _wait_for(handle: IO[Any], path: Path, timeout: float) -> None:
    """Poll until the lock is free, then say plainly what happened if it never is.

    Polled rather than handed to the library, because `portalocker.lock()` takes only a
    file and flags: the timeout belongs to its higher level `Lock` class, which manages
    the file handle itself and does not fit a context manager that has already opened one.
    Retrying a non-blocking attempt is portable and keeps the error message ours.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException as error:
            if time.monotonic() >= deadline:
                raise CryptoError(
                    f"Another SIENG3 process has held the ratchet state at {path.name} for "
                    f"more than {timeout:.0f} seconds. Two processes cannot share one "
                    f"session: wait for the other one to finish, or if nothing is running, "
                    f"delete the lock file."
                ) from error
            time.sleep(POLL_SECONDS)
        else:
            return


def is_locked(state_path: Path) -> bool:
    """Whether another process holds the lock. For status display, never for control flow.

    Anything that acts on the answer has a race between asking and acting. The only safe
    way to find out is to take the lock.
    """
    path = lock_path_for(state_path)
    if not path.exists():
        return False
    try:
        with path.open("a+b") as handle:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
            portalocker.unlock(handle)
    except portalocker.LockException:
        return True
    return False
