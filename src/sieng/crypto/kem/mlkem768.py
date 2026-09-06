"""ML-KEM-768 (FIPS 203), the post-quantum half of the hybrid.

This file is thin on purpose. The algorithm comes from `cryptography` and is never
reimplemented here: a lattice KEM written by hand is how you get a timing side channel
that nobody finds for years.

What this file does own is the availability check. As of version 48 the maintainers of
`cryptography` no longer guarantee that every algorithm is present on every backend. If
the installed build lacks ML-KEM, key generation raises UnsupportedAlgorithm, and the one
thing this project must never do in response is quietly continue with classical
cryptography only. A user who was told their messages are post-quantum secure would not
be, and nothing in the output would look different.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from typing import Final

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey, MLKEM768PublicKey

from sieng.common.errors import CryptoError

PUBLIC_BYTES: Final = 1184
SEED_BYTES: Final = 64
CIPHERTEXT_BYTES: Final = 1088
SHARED_BYTES: Final = 32

UNAVAILABLE = (
    "This build of `cryptography` has no ML-KEM-768, so the post-quantum half of the "
    "hybrid cannot run. Install cryptography>=48 from a wheel, which ships a backend "
    "that supports it. SIENG3 will not fall back to classical only encryption: doing so "
    "would leave the user believing they have protection they do not have."
)


def ensure_available() -> None:
    """Refuse to start rather than silently drop to classical cryptography.

    Called once at startup so the failure arrives before a user has picked a file and
    typed a message, rather than in the middle of embedding.
    """
    try:
        MLKEM768PrivateKey.generate()
    except UnsupportedAlgorithm as error:
        raise CryptoError(UNAVAILABLE) from error


def is_available() -> bool:
    """Same question, as a bool, for a status line that should not raise."""
    try:
        ensure_available()
    except CryptoError:
        return False
    return True


def generate() -> MLKEM768PrivateKey:
    try:
        return MLKEM768PrivateKey.generate()
    except UnsupportedAlgorithm as error:
        raise CryptoError(UNAVAILABLE) from error


def load_private(seed: bytes) -> MLKEM768PrivateKey:
    """Rebuild a private key from its 64 byte seed.

    The seed is what the keystore holds. It is a quarter the size of the expanded key and
    the expansion is deterministic, so there is nothing to gain from storing more.
    """
    if len(seed) != SEED_BYTES:
        raise CryptoError(f"ML-KEM-768 seed must be {SEED_BYTES} bytes, got {len(seed)}")
    try:
        return MLKEM768PrivateKey.from_seed_bytes(seed)
    except UnsupportedAlgorithm as error:
        raise CryptoError(UNAVAILABLE) from error


def load_public(raw: bytes) -> MLKEM768PublicKey:
    if len(raw) != PUBLIC_BYTES:
        raise CryptoError(f"ML-KEM-768 public key must be {PUBLIC_BYTES} bytes, got {len(raw)}")
    try:
        return MLKEM768PublicKey.from_public_bytes(raw)
    except UnsupportedAlgorithm as error:
        raise CryptoError(UNAVAILABLE) from error


def seed_bytes(key: MLKEM768PrivateKey) -> bytes:
    return key.private_bytes_raw()


def public_bytes(key: MLKEM768PublicKey) -> bytes:
    return key.public_bytes_raw()
