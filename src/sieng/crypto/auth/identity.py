"""A full identity: the two KEM keys, and optionally the two signing keys.

Four keys, because there are two jobs and each needs both a classical and a post-quantum
algorithm:

    x25519 + ML-KEM-768     establishing a secret. Always present.
    Ed25519 + ML-DSA-65     signing. Only for AUTH_PQ_EXPLICIT, which costs 3,373 bytes
                            per handshake and so is not the default.

The fingerprint covers all four, so an identity that gains signing keys is a different
identity with a different fingerprint. That is correct rather than inconvenient: a user
who verified a fingerprint verified those exact keys, and silently adding a key they never
saw would make the verification mean less than they think.

    fingerprint = SHA-256(LP(x25519) || LP(mlkem) || LP(ed25519) || LP(mldsa))

The empty signing keys are still length prefixed, so an identity without them cannot
collide with one whose keys happen to line up.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import hashlib
from dataclasses import dataclass
from typing import Final

from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa

from sieng.common.errors import CryptoError
from sieng.crypto.kdf import hkdf, labels
from sieng.crypto.kem import mlkem768, x25519
from sieng.crypto.kem.hybrid import PublicIdentity, SecretIdentity, generate_identity

ED25519_PUBLIC_BYTES: Final = 32
ED25519_SECRET_BYTES: Final = 32
MLDSA_PUBLIC_BYTES: Final = 1952
MLDSA_SEED_BYTES: Final = 32

FINGERPRINT_BYTES: Final = 32

# How the fingerprint is shown to a user: 32 hex characters in eight groups of four, which
# can be read aloud over a phone call without losing your place.
DISPLAY_GROUPS: Final = 8
DISPLAY_GROUP_SIZE: Final = 4


@dataclass(frozen=True)
class Identity:
    """Someone's public identity, as the other side sees it."""

    kem: PublicIdentity
    ed25519_public: bytes = b""
    mldsa_public: bytes = b""

    def __post_init__(self) -> None:
        if self.ed25519_public and len(self.ed25519_public) != ED25519_PUBLIC_BYTES:
            raise CryptoError(
                f"Ed25519 public key must be {ED25519_PUBLIC_BYTES} bytes, "
                f"got {len(self.ed25519_public)}"
            )
        if self.mldsa_public and len(self.mldsa_public) != MLDSA_PUBLIC_BYTES:
            raise CryptoError(
                f"ML-DSA-65 public key must be {MLDSA_PUBLIC_BYTES} bytes, "
                f"got {len(self.mldsa_public)}"
            )
        if bool(self.ed25519_public) != bool(self.mldsa_public):
            raise CryptoError(
                "An identity has both signing keys or neither. AUTH_PQ_EXPLICIT requires "
                "Ed25519 and ML-DSA to verify together, so one on its own is not usable "
                "and would only look like protection."
            )

    def can_sign(self) -> bool:
        """True when this identity can be used with AUTH_PQ_EXPLICIT."""
        return bool(self.ed25519_public)

    def fingerprint(self) -> bytes:
        """The 32 byte name for this identity. SESSION_PROTOCOL.md 3.2."""
        return hashlib.sha256(
            labels.TRANSCRIPT
            + hkdf.length_prefixed(
                self.kem.x25519, self.kem.mlkem, self.ed25519_public, self.mldsa_public
            )
        ).digest()

    def display(self) -> str:
        """The fingerprint as a user sees it: eight groups of four hex characters.

        Only the first sixteen bytes are shown. Thirty-two hex characters is already at
        the limit of what someone will read out accurately, and a fingerprint nobody
        finishes comparing protects nobody.
        """
        digits = self.fingerprint().hex().upper()[: DISPLAY_GROUPS * DISPLAY_GROUP_SIZE]
        groups = [
            digits[i : i + DISPLAY_GROUP_SIZE] for i in range(0, len(digits), DISPLAY_GROUP_SIZE)
        ]
        return " ".join(groups)

    def x25519_public(self) -> bytes:
        return self.kem.x25519

    def mlkem_public(self) -> bytes:
        return self.kem.mlkem


@dataclass(frozen=True)
class SecretKeys:
    """The private half. Seeds only, so the keystore holds 160 bytes rather than 6,500."""

    kem: SecretIdentity
    ed25519_secret: bytes = b""
    mldsa_seed: bytes = b""

    def __post_init__(self) -> None:
        if self.ed25519_secret and len(self.ed25519_secret) != ED25519_SECRET_BYTES:
            raise CryptoError(f"Ed25519 secret must be {ED25519_SECRET_BYTES} bytes")
        if self.mldsa_seed and len(self.mldsa_seed) != MLDSA_SEED_BYTES:
            raise CryptoError(f"ML-DSA-65 seed must be {MLDSA_SEED_BYTES} bytes")
        if bool(self.ed25519_secret) != bool(self.mldsa_seed):
            raise CryptoError("An identity has both signing keys or neither")

    def can_sign(self) -> bool:
        return bool(self.ed25519_secret)

    def public(self) -> Identity:
        if not self.can_sign():
            return Identity(self.kem.public())
        return Identity(
            self.kem.public(),
            self.ed25519_key().public_key().public_bytes_raw(),
            self.mldsa_key().public_key().public_bytes_raw(),
        )

    def ed25519_key(self) -> ed25519.Ed25519PrivateKey:
        if not self.ed25519_secret:
            raise CryptoError("This identity has no Ed25519 key, so it cannot sign")
        return ed25519.Ed25519PrivateKey.from_private_bytes(self.ed25519_secret)

    def mldsa_key(self) -> mldsa.MLDSA65PrivateKey:
        if not self.mldsa_seed:
            raise CryptoError("This identity has no ML-DSA key, so it cannot sign")
        return mldsa.MLDSA65PrivateKey.from_seed_bytes(self.mldsa_seed)


def generate(signing: bool = False) -> SecretKeys:
    """A fresh identity.

    Signing keys are opt in because they are only used by AUTH_PQ_EXPLICIT, and an
    identity that carries them has a different fingerprint. Deciding later means asking
    every contact to verify a new one.
    """
    kem = generate_identity()
    if not signing:
        return SecretKeys(kem)
    return SecretKeys(
        kem,
        ed25519.Ed25519PrivateKey.generate().private_bytes_raw(),
        mldsa.MLDSA65PrivateKey.generate().private_bytes_raw(),
    )


def load_public(
    x25519_public: bytes,
    mlkem_public: bytes,
    ed25519_public: bytes = b"",
    mldsa_public: bytes = b"",
) -> Identity:
    """Build an identity from raw bytes, checking each component is a real key.

    The length checks in PublicIdentity are not enough on their own: a string of the right
    length that is not a valid key would be accepted there and fail much later, somewhere
    that does not know what went wrong.
    """
    x25519.load_public(x25519_public)
    mlkem768.load_public(mlkem_public)
    if ed25519_public:
        ed25519.Ed25519PublicKey.from_public_bytes(ed25519_public)
    if mldsa_public:
        mldsa.MLDSA65PublicKey.from_public_bytes(mldsa_public)
    return Identity(PublicIdentity(mlkem_public, x25519_public), ed25519_public, mldsa_public)
