"""X25519, the classical half of the hybrid.

It does two jobs here and they are worth separating in your head:

    inside X-Wing   one of the two components the hybrid KEM combines, handled entirely
                    by the HPKE code in hybrid.py. Nothing here touches that path.
    dh_static       the static-to-static exchange that gives AUTH_IMPLICIT its sender
                    authentication for zero bytes on the wire. That is what this file is
                    called for directly.

X25519 is not post-quantum, and the project says so out loud rather than hoping nobody
notices: SESSION_PROTOCOL.md 4.3 records that AUTH_IMPLICIT authenticates classically
only. Confidentiality is post-quantum because it comes from ML-KEM. Impersonation needs a
quantum computer at the moment the session is created, which is a very different threat
from recording traffic today and decrypting it later.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from typing import Final

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from sieng.common.errors import CryptoError

PUBLIC_BYTES: Final = 32
PRIVATE_BYTES: Final = 32
SHARED_BYTES: Final = 32


def generate() -> X25519PrivateKey:
    return X25519PrivateKey.generate()


def load_private(raw: bytes) -> X25519PrivateKey:
    if len(raw) != PRIVATE_BYTES:
        raise CryptoError(f"X25519 private key must be {PRIVATE_BYTES} bytes, got {len(raw)}")
    return X25519PrivateKey.from_private_bytes(raw)


def load_public(raw: bytes) -> X25519PublicKey:
    if len(raw) != PUBLIC_BYTES:
        raise CryptoError(f"X25519 public key must be {PUBLIC_BYTES} bytes, got {len(raw)}")
    return X25519PublicKey.from_public_bytes(raw)


def private_bytes(key: X25519PrivateKey) -> bytes:
    return key.private_bytes_raw()


def public_bytes(key: X25519PublicKey) -> bytes:
    return key.public_bytes_raw()


def exchange(private_key: X25519PrivateKey, peer_public: bytes) -> bytes:
    """The shared secret between our private key and their public one.

    A public key of small order drives the result to all zeros, which both sides would
    then agree on without either of them having proved anything. `cryptography` rejects
    those outright, and this wrapper turns that into the project's own error type so a
    caller cannot mistake it for something recoverable.
    """
    try:
        shared = private_key.exchange(load_public(peer_public))
    except ValueError as error:
        raise CryptoError(
            "X25519 exchange produced no shared secret. The peer's public key is not a "
            "valid point, which means it was either corrupted or chosen to force a "
            "known result."
        ) from error
    if len(shared) != SHARED_BYTES:
        raise CryptoError(f"X25519 returned {len(shared)} bytes, expected {SHARED_BYTES}")
    return shared
