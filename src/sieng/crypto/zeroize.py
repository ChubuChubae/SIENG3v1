"""Wiping secrets from memory, and an honest account of how little that means in Python.

Read this before relying on anything in this file.

Python cannot guarantee a secret is gone. `bytes` is immutable, so overwriting one is not
possible at all; the best that can be done is drop the reference and hope. Even with a
mutable `bytearray`, the interpreter may already have copied the value while slicing,
concatenating or passing it around, and those copies are unreachable. The garbage
collector runs when it feels like it. The operating system may have written the page to
swap or to a hibernation file, where it survives a reboot. A core dump takes the lot.

So: this module reduces the window in which a secret sits in memory. It does not close it.
An attacker who can read the process memory of a running SIENG3 has already won, and no
amount of care here changes that. THREAT_MODEL.md says the same thing, and it is written
down in both places because a reader of either one deserves to know.

What actually protects key material is that it is short-lived and that the long-lived
copies on disk are encrypted. That is the design; this is hygiene.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import ctypes
import sys
from typing import Any


def zeroize(buffer: bytearray) -> None:
    """Overwrite a mutable buffer with zeros, in place.

    Works only on `bytearray`. Passing `bytes` is refused rather than silently doing
    nothing, because a call that appears to wipe a secret and does not is worse than no
    call at all: it makes the reader believe the secret is gone.
    """
    if not isinstance(buffer, bytearray):
        raise TypeError(
            f"zeroize() needs a bytearray, got {type(buffer).__name__}. Immutable bytes "
            f"cannot be overwritten, so wiping one is not possible. Hold secrets that "
            f"need wiping in a bytearray from the moment they are created."
        )
    length = len(buffer)
    if length:
        ctypes.memset((ctypes.c_char * length).from_buffer(buffer), 0, length)


def zeroize_all(*buffers: bytearray) -> None:
    """Wipe several buffers. Every one is attempted even if an earlier one fails."""
    errors: list[BaseException] = []
    for buffer in buffers:
        try:
            zeroize(buffer)
        except (TypeError, BufferError) as error:
            errors.append(error)
    if errors:
        raise errors[0]


def secret_buffer(data: bytes) -> bytearray:
    """A wipeable copy of some bytes.

    Note what this does not do: the original `bytes` is still there and cannot be wiped.
    Use this at the point a secret is created, not after it has been passed around.
    """
    return bytearray(data)


def drop(container: dict[Any, Any] | list[Any]) -> None:
    """Empty a container that held secrets, so the references go before the next GC.

    The values themselves are usually `bytes` and cannot be overwritten. Dropping the
    reference is the only thing available.
    """
    container.clear()


def memory_wiping_is_reliable() -> bool:
    """Always False, and it is a function so callers cannot forget to think about it.

    If a future version runs somewhere with locked pages and guaranteed wiping, this is
    the one place that changes.
    """
    return False


def limitations() -> str:
    """The text the ui shows when a user asks what happens to their keys.

    It lives here rather than in the ui so it cannot drift from the code it describes.
    """
    swap = "swap file" if sys.platform != "win32" else "page file"
    return (
        f"SIENG3 overwrites key material as soon as it is finished with, but Python "
        f"cannot guarantee memory is cleared: values may have been copied internally, "
        f"and the operating system may have written them to the {swap}. Protection "
        f"against an attacker who can read this program's memory is outside the scope "
        f"of this version."
    )
