"""The states a key may be in, and which moves between them are allowed.

A key is not simply present or absent. It is generated, put into service, rotated out,
revoked when something goes wrong, and eventually destroyed. Each of those is a different
answer to "may I use this?", and without somewhere to write the answer down the question
gets answered by whichever piece of code happens to ask.

    GENERATED -> ACTIVE      put into service
    ACTIVE    -> ROTATING    a replacement exists; still usable for decrypting old traffic
    ROTATING  -> REVOKED     no longer trusted
    ACTIVE    -> REVOKED     compromised, straight out of service
    any       -> DESTROYED   the material is gone

REVOKED and DESTROYED are terminal, and using a key in either state raises rather than
returning a warning. A revoked key that still works is a revoked key in name only.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from sieng.common.errors import CryptoError


class KeyState(Enum):
    GENERATED = auto()
    ACTIVE = auto()
    ROTATING = auto()
    REVOKED = auto()
    DESTROYED = auto()


ALLOWED: dict[KeyState, frozenset[KeyState]] = {
    KeyState.GENERATED: frozenset({KeyState.ACTIVE, KeyState.REVOKED, KeyState.DESTROYED}),
    KeyState.ACTIVE: frozenset({KeyState.ROTATING, KeyState.REVOKED, KeyState.DESTROYED}),
    KeyState.ROTATING: frozenset({KeyState.REVOKED, KeyState.DESTROYED}),
    KeyState.REVOKED: frozenset({KeyState.DESTROYED}),
    KeyState.DESTROYED: frozenset(),
}

# States in which a key may still be used to read old traffic, but not to send new.
DECRYPT_ONLY: frozenset[KeyState] = frozenset({KeyState.ROTATING})

# States in which a key may be used at all.
USABLE: frozenset[KeyState] = frozenset({KeyState.ACTIVE, KeyState.ROTATING})


@dataclass
class ManagedKey:
    """A key plus the record of where it is in its life.

    The material itself is not held here. This is the label on the box, and the box is
    the keystore.
    """

    name: str
    state: KeyState = KeyState.GENERATED
    history: list[tuple[KeyState, KeyState]] = field(default_factory=list)

    def transition(self, to: KeyState) -> None:
        """Move to another state, or refuse and say why.

        Refusing matters most for the moves that look harmless. Bringing a REVOKED key
        back to ACTIVE would undo a revocation that was probably made in a hurry for a
        good reason, and nothing else would notice.
        """
        if to not in ALLOWED[self.state]:
            allowed = ", ".join(sorted(s.name for s in ALLOWED[self.state])) or "nothing"
            raise CryptoError(
                f"Key '{self.name}' cannot go from {self.state.name} to {to.name}. "
                f"From {self.state.name} the only moves are: {allowed}."
            )
        self.history.append((self.state, to))
        self.state = to

    def require_usable(self, for_sending: bool = True) -> None:
        """Raise unless this key may be used right now.

        `for_sending` separates the two questions. A rotating key must still open messages
        that were sent before it was replaced, but must never be chosen for a new one.
        """
        if self.state not in USABLE:
            raise CryptoError(
                f"Key '{self.name}' is {self.state.name} and must not be used. {self._reason()}"
            )
        if for_sending and self.state in DECRYPT_ONLY:
            raise CryptoError(
                f"Key '{self.name}' is being rotated out. It can still read old messages "
                f"but must not be used to send new ones."
            )

    def is_usable(self, for_sending: bool = True) -> bool:
        """The same question without the exception, for a status display."""
        try:
            self.require_usable(for_sending)
        except CryptoError:
            return False
        return True

    def _reason(self) -> str:
        if self.state is KeyState.REVOKED:
            return "It was revoked, which is not reversible."
        if self.state is KeyState.DESTROYED:
            return "Its material has been destroyed."
        return "It has not been put into service yet."
