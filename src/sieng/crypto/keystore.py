"""Private keys at rest. The one place a secret is allowed to reach the disk.

Everything written here is wrapped: Argon2id turns the user's password into a key, and
AES-256-GCM-SIV encrypts the seeds under it. There is no code path that writes a raw
private key, not for debugging and not for tests, because a path that exists gets used.

The file layout, and why each field is in it:

    magic "SI3K"        (4)   so a wrong file is refused as a wrong file, not as a wrong
                              password, which would send the user hunting for the wrong bug
    version             (1)   this format will change; a reader must be able to say so
    argon2 parameters   (9)   time, memory and lanes as they were when this was written.
                              Argon2 output depends on them, so a file written at one cost
                              and read at another fails exactly like a wrong password.
                              Without these on disk the costs could never be raised again
    salt                (16)  so two users with the same password get different keys
    nonce               (12)
    ciphertext + tag    (var) the seeds

The header is not encrypted, and it does not need to be. It says nothing about the key,
and all of it is needed before decryption can begin.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.aead import gcm_siv
from sieng.crypto.kdf import argon2, hkdf, labels
from sieng.crypto.kem.hybrid import SecretIdentity
from sieng.crypto.kem.mlkem768 import SEED_BYTES as MLKEM_SEED_BYTES
from sieng.crypto.kem.x25519 import PRIVATE_BYTES as X25519_SECRET_BYTES

MAGIC: Final = b"SI3K"
VERSION: Final = 1

# time_cost, memory_cost_kib, lanes. Written as they were used, read back and passed
# straight to the KDF, which is the only way a cost increase can ever be rolled out.
PARAMETER_FORMAT: Final = ">IIB"
PARAMETER_BYTES: Final = struct.calcsize(PARAMETER_FORMAT)

HEADER_FORMAT: Final = f">4sB{PARAMETER_BYTES}s"
HEADER_BYTES: Final = struct.calcsize(HEADER_FORMAT)

SEALED_IDENTITY_BYTES: Final = MLKEM_SEED_BYTES + X25519_SECRET_BYTES


@dataclass(frozen=True)
class WrappedKey:
    """A keystore file, parsed but not yet opened."""

    version: int
    time_cost: int
    memory_cost_kib: int
    lanes: int
    salt: bytes
    nonce: bytes
    ciphertext: bytes

    def parameters(self) -> dict[str, int]:
        """The Argon2 settings this file was written with, ready to pass to the KDF."""
        return {
            "time_cost": self.time_cost,
            "memory_cost_kib": self.memory_cost_kib,
            "lanes": self.lanes,
        }

    def header(self) -> bytes:
        return header_bytes(self.parameters())

    def to_bytes(self) -> bytes:
        return self.header() + self.salt + self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, raw: bytes) -> "WrappedKey":
        """Parse a keystore file, refusing anything that is not one.

        These failures are CryptoError rather than DecryptError on purpose. A malformed
        file is not a wrong password, and telling a user their password is wrong when
        their file is truncated sends them looking in the wrong place. Nothing here leaks
        anything about the key: the header is public.
        """
        minimum = HEADER_BYTES + argon2.SALT_BYTES + gcm_siv.NONCE_BYTES + gcm_siv.TAG_BYTES
        if len(raw) < minimum:
            raise CryptoError(f"Keystore file is {len(raw)} bytes, too short to be one")

        magic, version, packed = struct.unpack(HEADER_FORMAT, raw[:HEADER_BYTES])
        if magic != MAGIC:
            raise CryptoError(
                f"This is not a SIENG3 keystore: expected {MAGIC!r} at the start, found {magic!r}"
            )
        if version != VERSION:
            raise CryptoError(
                f"Keystore format version {version} is not supported by this build, "
                f"which writes and reads version {VERSION}"
            )

        time_cost, memory_cost_kib, lanes = struct.unpack(PARAMETER_FORMAT, packed)
        body = raw[HEADER_BYTES:]
        salt = body[: argon2.SALT_BYTES]
        nonce = body[argon2.SALT_BYTES : argon2.SALT_BYTES + gcm_siv.NONCE_BYTES]
        return cls(
            version=version,
            time_cost=time_cost,
            memory_cost_kib=memory_cost_kib,
            lanes=lanes,
            salt=salt,
            nonce=nonce,
            ciphertext=body[argon2.SALT_BYTES + gcm_siv.NONCE_BYTES :],
        )


def header_bytes(settings: dict[str, int]) -> bytes:
    """The unencrypted header, from the Argon2 settings it records."""
    packed = struct.pack(
        PARAMETER_FORMAT, settings["time_cost"], settings["memory_cost_kib"], settings["lanes"]
    )
    return struct.pack(HEADER_FORMAT, MAGIC, VERSION, packed)


def wrap(secret: bytes, password: bytes, **costs: int) -> WrappedKey:
    """Encrypt some key material under a password.

    The Argon2 parameters go into the AEAD's associated data as well as into the header,
    so an attacker cannot lower them in the file and have the reader accept it. Without
    that, editing three bytes would turn a 64 MiB derivation into a trivial one, and the
    file would still open.
    """
    if not secret:
        raise CryptoError("Refusing to wrap nothing")
    settings = {**argon2.current_parameters(), **costs}
    salt = argon2.new_salt()
    key = argon2.derive_key(password, salt, **settings)
    nonce = _nonce_for(key, salt)

    return WrappedKey(
        version=VERSION,
        time_cost=settings["time_cost"],
        memory_cost_kib=settings["memory_cost_kib"],
        lanes=settings["lanes"],
        salt=salt,
        nonce=nonce,
        ciphertext=gcm_siv.seal(key, nonce, secret, header_bytes(settings) + salt),
    )


def unwrap(wrapped: WrappedKey, password: bytes) -> bytes:
    """Recover the key material, or raise DecryptError.

    A wrong password and a tampered file fail identically, because both are the same
    question to the caller: this file did not open.
    """
    key = argon2.derive_key(password, wrapped.salt, **wrapped.parameters())
    if wrapped.nonce != _nonce_for(key, wrapped.salt):
        # The nonce is derived, not stored freely, so one that does not match means the
        # file was edited. Same error as everything else.
        raise DecryptError
    return gcm_siv.open_(key, wrapped.nonce, wrapped.ciphertext, wrapped.header() + wrapped.salt)


def _nonce_for(key: bytes, salt: bytes) -> bytes:
    """Derive the nonce rather than storing a random one.

    Each wrap draws a fresh salt, so the key is fresh, so the nonce never repeats under
    the same key. Deriving it removes twelve bytes an attacker could otherwise change
    freely, and GCM-SIV would survive a repeat here anyway.
    """
    return hkdf.expand(key, labels.KEYSTORE_WRAP + salt, gcm_siv.NONCE_BYTES)


# ---- identities ------------------------------------------------------------


def save_identity(path: Path, identity: SecretIdentity, password: bytes, **costs: int) -> None:
    """Write an identity to disk, encrypted. The only way an identity is ever stored.

    Written to a temporary file and renamed, so a crash midway leaves the previous key
    intact rather than a half written file that opens as neither.
    """
    payload = identity.mlkem_seed + identity.x25519_secret
    blob = wrap(payload, password, **costs).to_bytes()

    path = Path(path)
    scratch = path.with_suffix(path.suffix + ".partial")
    scratch.write_bytes(blob)
    scratch.replace(path)


def load_identity(path: Path, password: bytes) -> SecretIdentity:
    """Read an identity back. Raises DecryptError for a wrong password."""
    wrapped = WrappedKey.from_bytes(Path(path).read_bytes())
    payload = unwrap(wrapped, password)
    if len(payload) != SEALED_IDENTITY_BYTES:
        raise DecryptError
    return SecretIdentity(payload[:MLKEM_SEED_BYTES], payload[MLKEM_SEED_BYTES:])


def needs_rewrap(wrapped: WrappedKey) -> bool:
    """True when the file was written at weaker settings than this build now uses.

    The reason the parameters are on disk. When the defaults are raised, existing files
    keep opening at their old cost and can be rewritten at the new one on next unlock,
    rather than becoming unreadable.
    """
    current = argon2.current_parameters()
    return (
        wrapped.time_cost < current["time_cost"]
        or wrapped.memory_cost_kib < current["memory_cost_kib"]
        or wrapped.lanes < current["lanes"]
    )
