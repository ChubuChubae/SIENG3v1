"""One session, with the commit order the rest of the system depends on.

FORMAT_SPEC.md 6 gives the order and warns that getting it wrong lets counters repeat.
It is written here as a single function so that no caller can assemble it differently:

    1. take the lock          before loading, not before saving
    2. load and check         generation has not gone backwards, machine id matches
    3. ratchet                derive the message keys, advance the chain
    4. commit the state       temp, fsync, rename, fsync directory
    5. hand the keys back     the caller writes the stego file only now
    6. release the lock

Step 4 before step 5 is the part that looks wrong and is not. Writing the state first
means a crash between them loses a message: the counter has moved on, and no file was
produced. That is a wasted counter and nothing worse. The other order loses far more: a
stego file exists, the state never recorded it, and the next send reuses the counter that
file was written with.

The rule is that a counter is spent the moment it is handed out, whether or not anything
came of it. `send()` is written so there is no path that returns keys without having
committed them first.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from sieng.common.errors import CryptoError
from sieng.crypto.ratchet import generation as gen
from sieng.crypto.ratchet import rollback_guard, state_lock, state_store
from sieng.crypto.ratchet.chain import (
    MessageKeys,
    RecvChain,
    SendChain,
    advance,
    derive_message_key,
    root_chain_key,
)
from sieng.crypto.ratchet.state_store import RatchetState

DEFAULT_MAX_SKIP: Final = 1000


def start(session_id: bytes, shared_secret: bytes, window: int = DEFAULT_MAX_SKIP) -> RatchetState:
    """The state of a brand new session, before anything has been sent."""
    return RatchetState(
        session_id=session_id,
        chain_key=root_chain_key(shared_secret),
        counter=0,
        generation=0,
        window=window,
    )


def create(
    path: Path,
    session_id: bytes,
    shared_secret: bytes,
    password: bytes,
    window: int = DEFAULT_MAX_SKIP,
    **costs: int,
) -> RatchetState:
    """Write the initial state for a new session, refusing to overwrite an existing one.

    Overwriting would reset the counter to zero on a chain that has already used it, which
    is the same damage as a rollback and easier to do by accident.
    """
    path = Path(path)
    if path.exists():
        raise CryptoError(
            f"A ratchet state already exists at {path.name}. Overwriting it would reset "
            f"the counter on a chain that has already used it. Delete the session "
            f"deliberately if that is what you want."
        )
    state = start(session_id, shared_secret, window)
    with state_lock.exclusive(path):
        state_store.save(path, state, password, **costs)
    return state


def send(path: Path, password: bytes, **costs: int) -> MessageKeys:
    """Take the next set of send keys, having first recorded that they were taken.

    Everything between taking the lock and releasing it happens here, in this order,
    because the order is the security property.
    """
    with state_lock.exclusive(path):
        state = state_store.load(path, password)
        rollback_guard.require_forward(state)

        chain = SendChain.resume(state.session_id, state.chain_key, state.counter)
        keys = chain.next_message_keys()

        state.chain_key = chain.chain_key()
        state.counter = chain.counter
        state.generation = gen.next_generation(state.generation)
        state_store.save(path, state, password, **costs)

    return keys


def receive(
    path: Path, password: bytes, counter: int, max_skip: int = DEFAULT_MAX_SKIP, **costs: int
) -> MessageKeys:
    """The keys for one received counter, with the skipped pool and replay set updated.

    The state is committed before the keys are returned, same as sending. A message that
    fails to decrypt afterwards has still consumed nothing: `mark_received` is what marks
    a counter as spent, and it is called only once the payload has actually opened.
    """
    with state_lock.exclusive(path):
        state = state_store.load(path, password)
        rollback_guard.require_forward(state)

        chain = RecvChain.resume(
            state.session_id,
            state.chain_key,
            state.counter,
            state.skipped,
            state.consumed,
            max_skip,
            state.window,
        )
        keys = chain.keys_for(counter)

        state.chain_key, state.counter, state.skipped, state.consumed = chain.snapshot()
        state.generation = gen.next_generation(state.generation)
        state_store.save(path, state, password, **costs)

    return keys


def mark_received(path: Path, password: bytes, counter: int, **costs: int) -> None:
    """Record that a counter was successfully used, so a replay of it is refused.

    Separate from `receive` on purpose. Marking inside `receive` would let anyone burn a
    counter by sending garbage, which turns a replay defence into a denial of service.
    """
    with state_lock.exclusive(path):
        state = state_store.load(path, password)
        state.consumed.add(counter)
        state.skipped.pop(counter, None)
        state.generation = gen.next_generation(state.generation)
        state_store.save(path, state, password, **costs)


@contextmanager
def opened(path: Path, password: bytes, **costs: int) -> Iterator[RatchetState]:
    """Load, let the caller change the state, then commit. All inside one lock.

    For operations that do not fit send or receive. The state is saved on a clean exit
    and left untouched if the block raises, so a failure partway through cannot leave the
    chain half advanced.
    """
    with state_lock.exclusive(path):
        state = state_store.load(path, password)
        rollback_guard.require_forward(state)
        yield state
        state.generation = gen.next_generation(state.generation)
        state_store.save(path, state, password, **costs)


__all__ = [
    "advance",
    "create",
    "derive_message_key",
    "mark_received",
    "opened",
    "receive",
    "send",
    "start",
]
