"""The transcript: one string of bytes that pins down exactly which exchange this is.

Every field that identifies the handshake goes in, length prefixed, in a fixed order. The
result is fed to HPKE as its `info` and mixed into the KDF, so both sides derive the same
session key only if they agree on every one of those fields.

Why the public keys are in it, when both sides already know them. That is the point. An
attacker in the middle who swaps a public key on the way past has changed the exchange,
and if the keys were not in the transcript nothing would notice: the two sides would each
complete a handshake, with the attacker, and neither would see anything wrong. With the
keys in the transcript the derived secrets differ and the first message fails to open.

Why every field is length prefixed, without exception. Concatenating "ab" and "c" gives
the same bytes as "a" and "bc". An attacker who controls where one field ends can move
bytes across the boundary while the transcript stays identical, and a signature over it
still verifies. Two bytes of length in front of each field closes that, and the moment one
field is exempted it opens again.

    LP(x) = uint16_be(len(x)) || x

What changed with D14. The published formula ended with the ephemeral public key and the
ML-KEM ciphertext, because the transcript had to commit to them: ML-KEM is not committing
on its own, so two ciphertexts can decapsulate to one shared secret. Under X-Wing through
HPKE that job is done by HPKE's own key schedule, which binds the encapsulation into the
context. Including it here as well is not merely redundant, it is impossible: the
encapsulation is produced by feeding this transcript in as `info`, so the transcript
cannot contain it. The two lines are gone and SESSION_PROTOCOL.md 5.2 records why.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from typing import Final

from sieng.common.errors import CryptoError
from sieng.crypto.kdf import hkdf, labels

VERSION: Final = 1
SUITE: Final = 1

AUTH_IMPLICIT: Final = 0
AUTH_PQ_EXPLICIT: Final = 1

SESSION_ID_BYTES: Final = 4
FINGERPRINT_BYTES: Final = 32


def build(
    session_id: bytes,
    sender: "IdentityView",
    recipient: "IdentityView",
    auth_mode: int = AUTH_IMPLICIT,
    version: int = VERSION,
    suite: int = SUITE,
) -> bytes:
    """The transcript for one handshake. The field order is fixed and must never change.

    Reordering, adding or removing a field changes every session key this project would
    derive, so a change here is a change of suite, not a refactor.
    """
    if len(session_id) != SESSION_ID_BYTES:
        raise CryptoError(f"Session id must be {SESSION_ID_BYTES} bytes, got {len(session_id)}")
    if auth_mode not in (AUTH_IMPLICIT, AUTH_PQ_EXPLICIT):
        raise CryptoError(f"Unknown auth mode {auth_mode}")

    return hkdf.length_prefixed(
        labels.TRANSCRIPT,
        bytes([version]),
        bytes([suite]),
        bytes([auth_mode]),
        session_id,
        sender.fingerprint(),
        recipient.fingerprint(),
        sender.x25519_public(),
        sender.mlkem_public(),
        recipient.x25519_public(),
        recipient.mlkem_public(),
    )


class IdentityView:
    """What build() needs from an identity. Implemented by auth.identity.Identity.

    Written as a small protocol rather than importing the concrete class, so this file
    stays readable on its own and the transcript formula has no dependencies to follow.
    """

    def fingerprint(self) -> bytes:
        raise NotImplementedError

    def x25519_public(self) -> bytes:
        raise NotImplementedError

    def mlkem_public(self) -> bytes:
        raise NotImplementedError
