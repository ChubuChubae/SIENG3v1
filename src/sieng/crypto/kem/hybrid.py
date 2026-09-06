"""The hybrid key exchange: X-Wing through HPKE, plus the static exchange that authenticates.

This file used to be the most dangerous one in the project. Combining an elliptic curve
secret with a lattice secret sounds like concatenation, and it is not: ML-KEM on its own
is not committing, meaning an attacker can build a ciphertext that decapsulates to a
chosen secret under two different keys. Fixing that by hand means getting the exact set of
values fed into the KDF right, and getting it wrong produces a system that works
perfectly and is broken.

Decision D14 removed that problem rather than solving it. `cryptography` ships X-Wing
(`KEM.MLKEM768_X25519`), the reviewed standard combiner, reachable through HPKE. So the
handshake becomes: generate a random 32 byte session secret, and let HPKE carry it to the
recipient under X-Wing.

    blob = HPKE(X-Wing, HKDF-SHA256, AES-256-GCM).encrypt(secret, recipient_pk, info=transcript)

Three things fall out of that one line, all of which used to be our responsibility:

    the combiner    X-Wing's, not ours
    transcript      bound inside HPKE's key schedule through `info`, so a modified
                    transcript makes the blob fail to open rather than merely deriving a
                    different key later
    AES-256-GCM     safe here despite the project using GCM-SIV everywhere else, because
                    HPKE derives a fresh nonce from a fresh ephemeral on every call, so
                    the nonce reuse that GCM-SIV exists to survive cannot occur (D15)

Cost: 1,168 bytes instead of 1,120. Forty-eight bytes for a combiner somebody else
reviewed, and the envelope is external anyway.

What HPKE does not give us is sender authentication: `Suite` exposes base mode only, so
the sender is anonymous to it. AUTH_IMPLICIT therefore comes from `dh_static`, mixed into
the KDF one layer up, exactly as SESSION_PROTOCOL.md 4.1 describes. Zero extra bytes.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import hashlib
import secrets
import struct
from dataclasses import dataclass
from typing import Final

from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm
from cryptography.hazmat.primitives.hpke import (
    AEAD,
    KDF,
    KEM,
    MLKEM768X25519PrivateKey,
    MLKEM768X25519PublicKey,
    Suite,
)

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.kdf import hkdf, labels
from sieng.crypto.kem import mlkem768, x25519

# X-Wing, HKDF-SHA256, AES-256-GCM. Fixed, never negotiated: a choice on the wire is a
# downgrade path, and there is nothing here worth negotiating.
SUITE: Final = KEM.MLKEM768_X25519

# The secret HPKE carries. It is the input to the whole key schedule in FORMAT_SPEC.md 2.1.
SECRET_BYTES: Final = 32

# 1088 byte ML-KEM ciphertext plus a 32 byte X25519 ephemeral.
ENCAPSULATED_BYTES: Final = 1120

# The sealed secret: encapsulation, then 32 bytes of secret under a 16 byte tag.
SEALED_BYTES: Final = ENCAPSULATED_BYTES + SECRET_BYTES + 16

# A public identity on the wire: the two components, in this order, back to back.
PUBLIC_BYTES: Final = mlkem768.PUBLIC_BYTES + x25519.PUBLIC_BYTES


def suite() -> Suite:
    """The one cipher suite this project speaks."""
    return Suite(SUITE, KDF.HKDF_SHA256, AEAD.AES_256_GCM)


@dataclass(frozen=True)
class PublicIdentity:
    """Someone's long term public key, as the other side needs to see it.

    The hybrid key object in `cryptography` is opaque: it has no serialisation of its own
    and is built from its two components. So the wire format is ours, and it is the
    simplest one that cannot be misparsed: two fixed length fields in a fixed order.
    """

    mlkem: bytes
    x25519: bytes

    def __post_init__(self) -> None:
        if len(self.mlkem) != mlkem768.PUBLIC_BYTES:
            raise CryptoError(
                f"ML-KEM public key must be {mlkem768.PUBLIC_BYTES} bytes, got {len(self.mlkem)}"
            )
        if len(self.x25519) != x25519.PUBLIC_BYTES:
            raise CryptoError(
                f"X25519 public key must be {x25519.PUBLIC_BYTES} bytes, got {len(self.x25519)}"
            )

    def to_bytes(self) -> bytes:
        """Both components, ML-KEM first. Fixed widths, so no length prefix is needed."""
        return self.mlkem + self.x25519

    @classmethod
    def from_bytes(cls, raw: bytes) -> "PublicIdentity":
        if len(raw) != PUBLIC_BYTES:
            raise CryptoError(
                f"A public identity is {PUBLIC_BYTES} bytes, got {len(raw)}. "
                f"That is {mlkem768.PUBLIC_BYTES} of ML-KEM then {x25519.PUBLIC_BYTES} of X25519."
            )
        return cls(raw[: mlkem768.PUBLIC_BYTES], raw[mlkem768.PUBLIC_BYTES :])

    def fingerprint(self) -> bytes:
        """A short, stable name for this identity, for the trust store and the envelope.

        Hashed rather than the key itself: the envelope allots 32 bytes for it, and a
        user who compares two identities out loud needs something they can read. Length
        prefixed before hashing so that no pair of component keys can collide by having
        the boundary between them moved.
        """
        return hashlib.sha256(
            labels.TRANSCRIPT + hkdf.length_prefixed(self.mlkem, self.x25519)
        ).digest()

    def _hpke_key(self) -> MLKEM768X25519PublicKey:
        return MLKEM768X25519PublicKey(
            mlkem768.load_public(self.mlkem), x25519.load_public(self.x25519)
        )


@dataclass(frozen=True)
class SecretIdentity:
    """The private half. Held in memory only while it is needed, and never written raw.

    Stored as seeds rather than expanded keys: 64 bytes for ML-KEM and 32 for X25519,
    against 2,400 for the expanded ML-KEM key. Expansion is deterministic, so nothing is
    lost, and there is less material to wipe.
    """

    mlkem_seed: bytes
    x25519_secret: bytes

    def __post_init__(self) -> None:
        if len(self.mlkem_seed) != mlkem768.SEED_BYTES:
            raise CryptoError(
                f"ML-KEM seed must be {mlkem768.SEED_BYTES} bytes, got {len(self.mlkem_seed)}"
            )
        if len(self.x25519_secret) != x25519.PRIVATE_BYTES:
            raise CryptoError(
                f"X25519 secret must be {x25519.PRIVATE_BYTES} bytes, got {len(self.x25519_secret)}"
            )

    def public(self) -> PublicIdentity:
        return PublicIdentity(
            mlkem768.public_bytes(mlkem768.load_private(self.mlkem_seed).public_key()),
            x25519.public_bytes(x25519.load_private(self.x25519_secret).public_key()),
        )

    def _hpke_key(self) -> MLKEM768X25519PrivateKey:
        return MLKEM768X25519PrivateKey(
            mlkem768.load_private(self.mlkem_seed), x25519.load_private(self.x25519_secret)
        )


def generate_identity() -> SecretIdentity:
    """A fresh long term identity. Both halves at once, because one without the other is
    not a usable key and letting them exist separately invites mismatched pairs."""
    return SecretIdentity(
        mlkem768.seed_bytes(mlkem768.generate()),
        x25519.private_bytes(x25519.generate()),
    )


def seal_secret(recipient: PublicIdentity, transcript: bytes) -> tuple[bytes, bytes]:
    """Pick a session secret and encapsulate it to the recipient under X-Wing.

    Returns (secret, blob). The secret stays local and feeds the key schedule; the blob
    goes in the envelope. `transcript` binds the blob to everything already agreed, so a
    blob lifted into a different handshake will not open.
    """
    secret = secrets.token_bytes(SECRET_BYTES)
    try:
        blob = suite().encrypt(secret, recipient._hpke_key(), info=transcript)
    except UnsupportedAlgorithm as error:
        raise CryptoError(mlkem768.UNAVAILABLE) from error
    if len(blob) != SEALED_BYTES:
        raise CryptoError(f"Expected a {SEALED_BYTES} byte encapsulation, got {len(blob)}")
    return secret, blob


def open_secret(recipient: SecretIdentity, blob: bytes, transcript: bytes) -> bytes:
    """Recover the session secret, or raise DecryptError.

    Same rule as the AEAD layer: a wrong key, a tampered blob and a transcript that does
    not match all fail identically, because a caller that can tell them apart is an oracle.
    """
    if len(blob) != SEALED_BYTES:
        raise DecryptError
    try:
        secret = suite().decrypt(blob, recipient._hpke_key(), info=transcript)
    except UnsupportedAlgorithm as error:
        raise CryptoError(mlkem768.UNAVAILABLE) from error
    except (InvalidTag, ValueError):
        raise DecryptError from None
    if len(secret) != SECRET_BYTES:
        raise DecryptError
    return secret


def static_exchange(sender: SecretIdentity, recipient: PublicIdentity) -> bytes:
    """dh_static: the sender's long term key against the recipient's.

    This is the whole of AUTH_IMPLICIT. Only someone holding the sender's private key can
    compute it, so only they can derive a session key the recipient will accept, and it
    costs nothing on the wire because both sides already know both public keys.
    """
    return x25519.exchange(x25519.load_private(sender.x25519_secret), recipient.x25519)


def derive_shared_secret(hpke_secret: bytes, dh_static: bytes, transcript: bytes) -> bytes:
    """Mix the two secrets and the transcript into `ss`, the root of everything else.

    Length prefixed, so no field can be made to look like part of another one. The
    transcript is already bound inside the HPKE blob, and it goes in here as well: the
    two bindings cover different things and neither makes the other redundant.
    """
    if len(hpke_secret) != SECRET_BYTES:
        raise CryptoError(f"Session secret must be {SECRET_BYTES} bytes, got {len(hpke_secret)}")
    if len(dh_static) != x25519.SHARED_BYTES:
        raise CryptoError(f"dh_static must be {x25519.SHARED_BYTES} bytes, got {len(dh_static)}")
    ikm = hkdf.length_prefixed(hpke_secret, dh_static, transcript)
    return hkdf.extract(ikm, labels.KEM_SUITE)


def envelope_overhead(auth_signature_bytes: int = 0) -> int:
    """How many bytes the handshake adds, for the capacity check in the pipeline.

    Kept here rather than in the pipeline so the number cannot drift from the code that
    produces it.
    """
    return SEALED_BYTES + PUBLIC_BYTES + auth_signature_bytes


def parse_sealed(blob: bytes) -> tuple[bytes, bytes]:
    """Split a blob into its encapsulation and its ciphertext, for logging and tests.

    Never used to decrypt. HPKE takes the whole blob, and splitting it to feed the halves
    back separately would be reimplementing the format.
    """
    if len(blob) != SEALED_BYTES:
        raise CryptoError(f"A sealed secret is {SEALED_BYTES} bytes, got {len(blob)}")
    return blob[:ENCAPSULATED_BYTES], blob[ENCAPSULATED_BYTES:]


def suite_identifier() -> bytes:
    """What goes in the header so a receiver can refuse a suite it does not implement."""
    return struct.pack(">H", labels.SUITE_VERSION) + labels.KEM_SUITE
