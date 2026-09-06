"""Argon2id: turn a password a human can remember into a key.

Every other key in this project comes from a KEM or from another key, and all of them are
already uniform. A password is neither. It has perhaps forty bits of real entropy and an
attacker can try billions of guesses a second against a fast hash, so the only defence is
to make each guess expensive in a way that does not help someone with a warehouse of GPUs.
That is what the memory cost buys: 64 MiB per attempt is nothing for one login and
ruinous for a cracking rig.

Argon2id rather than Argon2i or Argon2d, because it is the hybrid that RFC 9106 recommends
by default: the first pass resists side channel observation, the rest resist GPUs.

Used in exactly two places, both of them writing to disk: the keystore that holds private
identity keys, and the ratchet state file.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import secrets
from typing import Final

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from sieng.common.errors import CryptoError

# RFC 9106 section 4, the "second recommended option": 64 MiB, three passes, four lanes.
# Do not lower these to make a test run faster. Pass explicit parameters in the test.
TIME_COST: Final = 3
MEMORY_COST_KIB: Final = 64 * 1024
LANES: Final = 4

KEY_BYTES: Final = 32

# 16 bytes is the RFC 9106 recommendation, and it is what makes two users with the same
# password derive different keys, so one cracked password does not unlock the other.
SALT_BYTES: Final = 16

# Not a security boundary, just a guard against a paste accident becoming a 10 second hash.
MAX_PASSWORD_BYTES: Final = 1024


def new_salt() -> bytes:
    """A fresh random salt. Store it next to the ciphertext, it is not secret."""
    return secrets.token_bytes(SALT_BYTES)


def derive_key(
    password: bytes,
    salt: bytes,
    *,
    length: int = KEY_BYTES,
    time_cost: int = TIME_COST,
    memory_cost_kib: int = MEMORY_COST_KIB,
    lanes: int = LANES,
) -> bytes:
    """Derive a key from a password. Takes roughly a tenth of a second and 64 MiB.

    The cost parameters are arguments so a test can run in reasonable time, never so that
    real code can turn them down. Anything that writes a file uses the defaults.
    """
    if not password:
        raise CryptoError("Refusing to derive a key from an empty password")
    if len(password) > MAX_PASSWORD_BYTES:
        raise CryptoError(
            f"Password is {len(password)} bytes, over the {MAX_PASSWORD_BYTES} byte limit"
        )
    if len(salt) < 8:
        raise CryptoError(
            f"Salt is {len(salt)} bytes. Argon2 needs at least 8, and this project uses "
            f"{SALT_BYTES}. Use new_salt() rather than inventing one."
        )
    return Argon2id(
        salt=salt,
        length=length,
        iterations=time_cost,
        lanes=lanes,
        memory_cost=memory_cost_kib,
    ).derive(password)


def verify(
    password: bytes,
    salt: bytes,
    expected: bytes,
    *,
    time_cost: int = TIME_COST,
    memory_cost_kib: int = MEMORY_COST_KIB,
    lanes: int = LANES,
) -> bool:
    """Check a password against a previously derived key, in constant time.

    The cost parameters must be the ones the key was derived with. Argon2 output depends
    on them, so verifying at different settings fails for a correct password, which looks
    exactly like a wrong one. That is why 7.7 has to store them beside the salt: see
    PARAMETER_FIELDS.

    Returns a bool rather than raising, because the caller needs to answer every wrong
    password the same way and at the same speed.
    """
    derived = derive_key(
        password,
        salt,
        length=len(expected),
        time_cost=time_cost,
        memory_cost_kib=memory_cost_kib,
        lanes=lanes,
    )
    return secrets.compare_digest(derived, expected)


# What the keystore and the state file must write next to every salt. Without these, the
# cost parameters can never be raised: an old file would be undecryptable and there would
# be no way to tell that apart from a wrong password.
PARAMETER_FIELDS: Final = ("time_cost", "memory_cost_kib", "lanes")


def current_parameters() -> dict[str, int]:
    """The settings a new key is derived at. Store this with the ciphertext."""
    return {"time_cost": TIME_COST, "memory_cost_kib": MEMORY_COST_KIB, "lanes": LANES}
