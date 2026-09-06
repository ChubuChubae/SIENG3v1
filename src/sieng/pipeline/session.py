"""Creating a session, so the ui does not have to reach into crypto to do it.

The import-linter contract "ui never holds raw keys" caught the first version of this,
which had the CLI calling `crypto.ratchet.session.create` directly. The contract was right.
A ui that imports crypto is a ui that can be given a key to hold, and every later feature
that wants "just one more thing from crypto" makes the boundary a little softer. This file
is the boundary: the ui asks for a session, and gets back the two values it has to show.

What this returns is honest rather than tidy. The shared secret comes back in the open,
because the caller has to give it to the other side and this version of the program has no
way to do that for them. Phase 7 has the whole handshake, and once there is a ui for it
this function grows a second form that never returns a secret at all.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import secrets
from pathlib import Path
from typing import Final

from sieng.crypto.ratchet import session as ratchet

SHARED_SECRET_BYTES: Final = 32
SESSION_ID_BYTES: Final = 4


def create_session(
    state_path: Path, password: bytes, window: int = 1000, **costs: int
) -> tuple[bytes, bytes]:
    """Start a session and write its state. Returns (session_id, shared_secret).

    The secret is generated here rather than taken as an argument, so there is no path by
    which a caller supplies a weak one. `costs` exists only so tests can lower the Argon2
    parameters; nothing in the product passes it.
    """
    shared_secret = secrets.token_bytes(SHARED_SECRET_BYTES)
    session_id = secrets.token_bytes(SESSION_ID_BYTES)
    ratchet.create(Path(state_path), session_id, shared_secret, password, window, **costs)
    return session_id, shared_secret


def join_session(
    state_path: Path,
    session_id: bytes,
    shared_secret: bytes,
    password: bytes,
    window: int = 1000,
    **costs: int,
) -> None:
    """Create the other side's state from a secret that was carried over by hand.

    The counterpart to create_session. Both sides must start from the same secret and the
    same session id, or every message fails to open with no indication of why.
    """
    ratchet.create(Path(state_path), session_id, shared_secret, password, window, **costs)
