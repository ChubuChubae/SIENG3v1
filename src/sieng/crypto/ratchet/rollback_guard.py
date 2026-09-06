"""Rollback detection. Read the first paragraph before relying on any of this.

**This detects rollback. It does not prevent it.**

The state file lives on a normal filesystem. Anyone who can write it can also replace it
with an older copy, and can edit the generation counter inside it to whatever they like.
There is no version of this file that changes that, because the protection would have to
live somewhere the attacker cannot reach, and on a desktop machine no such place exists
without hardware support this project does not assume.

What it does is notice the ordinary cases, which are the common ones:

    a restored backup       the user copied an old .state back and did not think about it
    a synced folder         a cloud client silently reverted the file
    a copied installation   the same session now runs on two machines

None of those is an attacker. All of them cause counter reuse, and all of them would
otherwise go unnoticed until someone analysed the traffic. Being told on the next send is
the whole value here.

What happens when detection fires is refusal, not a warning. A warning would be clicked
past, and the failure it warns about is silent, so the user would never learn they were
wrong to click. THREAT_MODEL.md 4 records the same limitation, and the two must be
changed together if this ever changes.

Consequences of a rollback that reaches the point of sending: message counters repeat.
Under AES-256-GCM-SIV that reveals whether two plaintexts were identical and nothing
further, which is precisely why that AEAD was chosen (crypto/aead/gcm_siv.py). It is a
degraded state, not a broken one.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from dataclasses import dataclass
from pathlib import Path

from sieng.common.errors import CryptoError, RollbackDetected
from sieng.crypto.ratchet import generation as gen
from sieng.crypto.ratchet.state_store import RatchetState


@dataclass(frozen=True)
class GuardReport:
    """What the guard found, so a caller can explain it rather than just failing."""

    ok: bool
    reason: str = ""
    loaded_generation: int = 0
    expected_generation: int = 0

    def describe(self) -> str:
        if self.ok:
            return f"State is at generation {self.loaded_generation}, as expected"
        return self.reason


def inspect(state: RatchetState, last_generation: int | None = None) -> GuardReport:
    """Look at loaded state and say whether it is safe to use. Never raises.

    Used by the ui to show a status before the user commits to anything. The enforcing
    version is `require_forward`.
    """
    try:
        gen.check_machine(state.machine_id)
    except CryptoError as error:
        return GuardReport(
            ok=False,
            reason=str(error),
            loaded_generation=state.generation,
            expected_generation=last_generation or 0,
        )

    if last_generation is not None and state.generation < last_generation:
        return GuardReport(
            ok=False,
            reason=(
                f"State is at generation {state.generation} but generation "
                f"{last_generation} was already used. A backup was probably restored."
            ),
            loaded_generation=state.generation,
            expected_generation=last_generation,
        )
    return GuardReport(
        ok=True,
        loaded_generation=state.generation,
        expected_generation=last_generation or state.generation,
    )


def require_forward(state: RatchetState, last_generation: int | None = None) -> None:
    """Refuse to continue unless the state has moved forward. Raises RollbackDetected.

    Called before every send, inside the lock, after loading and before ratcheting.
    """
    report = inspect(state, last_generation)
    if not report.ok:
        raise RollbackDetected(
            f"{report.reason} Continuing would reuse message counters, so it is refused. "
            f"If this is expected, delete the session and start a new one: the old "
            f"messages remain readable, but this chain cannot safely be resumed."
        )


def quarantine(state_path: Path) -> Path:
    """Move suspect state aside instead of deleting it.

    A user who has just been told their state went backwards may need the file to work out
    what happened, and deleting the evidence to make an error message go away is not a
    service. The moved file is still encrypted.
    """
    path = Path(state_path)
    target = path.with_suffix(path.suffix + ".rollback")
    index = 1
    while target.exists():
        target = path.with_suffix(f"{path.suffix}.rollback{index}")
        index += 1
    path.replace(target)
    return target


def prevention_is_possible() -> bool:
    """Always False, as a function so it cannot be forgotten in a review.

    If a future version gains a monotonic counter the attacker cannot rewind, such as a
    TPM or a secure element, this is the one place that changes, and the module docstring
    and THREAT_MODEL.md 4 change with it.
    """
    return False
