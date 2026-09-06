"""The generation counter and the machine id: two facts that say whether state is stale.

A ratchet is only safe while its state moves forward. Two things can make it move
backwards, and they need different answers:

    a restored backup      the file is older than the last one written on this machine.
                           The generation counter catches it: it only ever increases, so
                           a lower one means the file went back in time.
    a copied folder        the same state now exists on two machines, and both will hand
                           out the same counters. The machine id catches it: the file
                           records which machine wrote it, and another machine reading it
                           knows the state is not exclusively its own.

Neither is prevention. Someone who can write the state file can write anything they like
into it, including a higher generation. What this gives is the ability to notice, which is
the difference between a user silently reusing counters for months and a user being told
on the next send. rollback_guard.py says the same thing at more length, because it is the
kind of limitation that gets quietly forgotten.

The machine id is derived, not stored in a config the user might copy along with
everything else. It has to be stable across reboots and different on a different machine.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import hashlib
import platform
import uuid
from typing import Final

from sieng.common.errors import CryptoError

MACHINE_ID_BYTES: Final = 16
GENERATION_BYTES: Final = 8
MAX_GENERATION: Final = (1 << 64) - 1

# Not a secret, so it does not need a secret key. It only has to differ between machines.
MACHINE_LABEL: Final = b"sieng3/machine/v1"


def machine_id() -> bytes:
    """A stable identifier for this computer.

    Built from the MAC-derived node id and the platform description. Neither is unique in
    the strong sense: a virtual machine can be cloned with its MAC intact, and then two
    copies share an id. That failure mode leaves this check blind, which is another reason
    it is described as detection rather than protection.
    """
    material = f"{uuid.getnode()}:{platform.system()}:{platform.node()}".encode()
    return hashlib.sha256(MACHINE_LABEL + material).digest()[:MACHINE_ID_BYTES]


def check_generation(loaded: int, last_seen: int) -> None:
    """Refuse state that has gone backwards.

    `loaded` is what the file says, `last_seen` is what this process wrote or read last.
    Equal is fine on a first read; lower never is.
    """
    if loaded < last_seen:
        raise RollbackError(loaded, last_seen)
    if loaded > MAX_GENERATION:
        raise CryptoError(f"Generation {loaded} is outside the 64 bit field")


def next_generation(current: int) -> int:
    """One step forward. Refuses to wrap, because a wrapped counter is a silent rollback."""
    if current >= MAX_GENERATION:
        raise CryptoError(
            f"The generation counter has reached {MAX_GENERATION} and cannot advance. "
            f"Start a new session rather than wrapping, which would look like a rollback."
        )
    return current + 1


def check_machine(loaded: bytes, expected: bytes | None = None) -> None:
    """Refuse state written by a different machine.

    The state file is not portable, and that is deliberate. Copying it to a second machine
    gives two machines the same chain, and both will hand out the same counters until one
    of them gets ahead.
    """
    current = expected if expected is not None else machine_id()
    if len(loaded) != MACHINE_ID_BYTES:
        raise CryptoError(f"Machine id must be {MACHINE_ID_BYTES} bytes, got {len(loaded)}")
    if loaded != current:
        raise CryptoError(
            "This ratchet state was written on a different machine. Using it here would "
            "give both machines the same counters, so it is refused. Start a new session "
            "on this machine instead of copying state between them."
        )


class RollbackError(CryptoError):
    """The state file went backwards. Carries both numbers so a user can see the gap."""

    def __init__(self, loaded: int, last_seen: int) -> None:
        self.loaded = loaded
        self.last_seen = last_seen
        super().__init__(
            f"Ratchet state moved backwards: the file is at generation {loaded} but "
            f"generation {last_seen} was already used. This usually means a backup was "
            f"restored. Continuing would reuse message counters, so it is refused."
        )
