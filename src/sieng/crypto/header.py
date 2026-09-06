"""The 12 bytes that go in front of every payload, and the whitening that hides them.

    byte  0    1    2    3    4    5    6    7    8    9   10   11
        +----+----+----+----+----+----+----+----+----+----+----+----+
        | vs |      session id       |    counter   |    length    | fl |
        +----+----+----+----+----+----+----+----+----+----+----+----+

Twelve bytes is ninety-six coefficients at one bit each. On a 512x512 cover at 0.05
bpnzAC that is roughly seven percent of everything available, which is why the size was
argued over and settled rather than guessed (D6, FORMAT_SPEC.md 3.1).

Every byte of it is whitened before embedding. Without that, `version` and `suite` are
constants and the reserved flag bits are zero, so the first byte of every file this
program has ever produced looks the same. A steganalyst does not need to break anything
to use that; they need to notice it once.

Whitening uses a session level key, and that is forced rather than chosen. The counter
lives inside the header, and you would need the counter to find the per-message key, so a
per-message key cannot be what unwraps the header. The receiver instead searches forward
from the last counter it saw, which is what `unwhiten_search` does, and that search must
be bounded or an empty file costs sixteen million HKDF calls.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from dataclasses import dataclass
from typing import Final

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.kdf import hkdf, labels

HEADER_BYTES: Final = 12
HEADER_BITS: Final = HEADER_BYTES * 8

VERSION: Final = 1
SUITE: Final = 1

SESSION_ID_BYTES: Final = 4
MAX_COUNTER: Final = (1 << 24) - 1
MAX_LENGTH: Final = (1 << 24) - 1

# ---- flags (FORMAT_SPEC.md 3.4) --------------------------------------------

FLAG_HAS_PRECOVER: Final = 1 << 0
FLAG_MULTIPART: Final = 1 << 1
ENVELOPE_MASK: Final = 0b1100
ENVELOPE_SHIFT: Final = 2
FLAG_AUTH_PQ: Final = 1 << 4
FLAG_BOOTSTRAP: Final = 1 << 5

# Bits 6 and 7. A receiver must refuse a header that sets them rather than ignoring them:
# unchecked spare bits are a channel an attacker can send data through, and a future
# version could not tell an old file from a tampered one.
RESERVED_MASK: Final = 0b1100_0000

ENVELOPE_EXTERNAL: Final = 0
ENVELOPE_INLINE: Final = 1
ENVELOPE_MULTIPART: Final = 2
ENVELOPE_RESERVED: Final = 3


@dataclass(frozen=True)
class Header:
    """One message's header, as values rather than bits."""

    session_id: bytes
    counter: int
    length: int
    flags: int = 0
    version: int = VERSION
    suite: int = SUITE

    def __post_init__(self) -> None:
        if len(self.session_id) != SESSION_ID_BYTES:
            raise CryptoError(
                f"Session id must be {SESSION_ID_BYTES} bytes, got {len(self.session_id)}"
            )
        if not 0 <= self.counter <= MAX_COUNTER:
            raise CryptoError(f"Counter {self.counter} does not fit in 24 bits")
        if not 0 <= self.length <= MAX_LENGTH:
            raise CryptoError(
                f"Ciphertext length {self.length} does not fit in 24 bits, so it cannot be "
                f"described by this header. The limit is {MAX_LENGTH} bytes per message."
            )
        if not 0 <= self.flags <= 0xFF:
            raise CryptoError(f"Flags must be one byte, got {self.flags}")
        if self.flags & RESERVED_MASK:
            raise CryptoError(
                f"Flag bits 6 and 7 are reserved and must be zero, got {self.flags:#010b}"
            )
        if not 0 <= self.version <= 0xF or not 0 <= self.suite <= 0xF:
            raise CryptoError("Version and suite are four bits each")

    @property
    def envelope_mode(self) -> int:
        return (self.flags & ENVELOPE_MASK) >> ENVELOPE_SHIFT

    @property
    def has_precover(self) -> bool:
        return bool(self.flags & FLAG_HAS_PRECOVER)

    @property
    def is_pq_authenticated(self) -> bool:
        return bool(self.flags & FLAG_AUTH_PQ)

    @property
    def carries_envelope(self) -> bool:
        return bool(self.flags & FLAG_BOOTSTRAP)

    def pack(self) -> bytes:
        """The plaintext twelve bytes, before whitening."""
        return (
            bytes([(self.version << 4) | self.suite])
            + self.session_id
            + self.counter.to_bytes(3, "big")
            + self.length.to_bytes(3, "big")
            + bytes([self.flags])
        )

    @classmethod
    def unpack(cls, raw: bytes) -> "Header":
        """Read twelve plaintext bytes back into values, refusing anything malformed."""
        if len(raw) != HEADER_BYTES:
            raise CryptoError(f"A header is {HEADER_BYTES} bytes, got {len(raw)}")
        return cls(
            version=raw[0] >> 4,
            suite=raw[0] & 0xF,
            session_id=raw[1:5],
            counter=int.from_bytes(raw[5:8], "big"),
            length=int.from_bytes(raw[8:11], "big"),
            flags=raw[11],
        )


def build_flags(
    *,
    has_precover: bool = False,
    multipart: bool = False,
    envelope_mode: int = ENVELOPE_EXTERNAL,
    pq_auth: bool = False,
    bootstrap: bool = False,
) -> int:
    """Assemble the flag byte from named options, so no caller shifts bits by hand."""
    if not ENVELOPE_EXTERNAL <= envelope_mode <= ENVELOPE_MULTIPART:
        raise CryptoError(
            f"Envelope mode {envelope_mode} is not one of external, inline or multipart. "
            f"Value 3 is reserved and must never be written."
        )
    flags = envelope_mode << ENVELOPE_SHIFT
    if has_precover:
        flags |= FLAG_HAS_PRECOVER
    if multipart:
        flags |= FLAG_MULTIPART
    if pq_auth:
        flags |= FLAG_AUTH_PQ
    if bootstrap:
        flags |= FLAG_BOOTSTRAP
    return flags


# ---- whitening -------------------------------------------------------------


def keystream(session_key: bytes, counter: int, length: int = HEADER_BYTES) -> bytes:
    """The bytes a header is XORed with.

    The counter is in the info string, so every message gets a different keystream. If it
    were left out, every header in a session would be masked identically and XORing two
    of them together would show where their plaintexts differ, which is most of them.
    """
    if not 0 <= counter <= MAX_COUNTER:
        raise CryptoError(f"Counter {counter} does not fit in 24 bits")
    return hkdf.expand(session_key, hkdf.stream_info(labels.HEADER_STREAM, counter), length)


def whiten(plaintext: bytes, session_key: bytes, counter: int) -> bytes:
    """XOR a header with its keystream. Its own inverse, given the same counter."""
    stream = keystream(session_key, counter, len(plaintext))
    return bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))


def unwhiten(masked: bytes, session_key: bytes, counter: int) -> bytes:
    """The same operation. Named separately because the call sites read better for it."""
    return whiten(masked, session_key, counter)


def unwhiten_search(
    masked: bytes,
    session_key: bytes,
    last_counter: int,
    max_skip: int,
    max_length: int | None = None,
) -> Header:
    """Find the counter this header was whitened with, by trying the plausible ones.

    The chicken and egg problem in one function. The keystream depends on the counter, and
    the counter is inside the header, so the only way in is to try candidates and check
    whether the result makes sense.

    Bounded by max_skip, and that bound is the entire defence against a cheap denial of
    service: a file with nothing hidden in it never matches, and without a limit the
    receiver would work through all sixteen million counters before saying so.

    A candidate is accepted when the version and suite are ones we implement, the counter
    inside matches the counter tried, the reserved bits are clear, and the length is not
    larger than the carrier could hold. Four conditions, so a wrong candidate passing all
    of them by chance is around one in four billion.
    """
    if max_skip < 1:
        raise CryptoError(f"max_skip must be at least 1, got {max_skip}")
    if len(masked) != HEADER_BYTES:
        raise DecryptError

    for candidate in range(last_counter, min(last_counter + max_skip, MAX_COUNTER + 1)):
        header = _try_counter(masked, session_key, candidate, max_length)
        if header is not None:
            return header

    # Same error as every other failure. A caller that could tell "no counter matched"
    # from "the payload did not decrypt" would learn whether a file holds anything.
    raise DecryptError


def _try_counter(
    masked: bytes, session_key: bytes, candidate: int, max_length: int | None
) -> Header | None:
    """Unwhiten with one candidate counter and say whether the result is a real header."""
    try:
        header = Header.unpack(unwhiten(masked, session_key, candidate))
    except CryptoError:
        # Reserved bits set, or a field out of range. Not a header, so not this counter.
        return None
    if header.version != VERSION or header.suite != SUITE:
        return None
    if header.counter != candidate:
        return None
    if max_length is not None and header.length > max_length:
        return None
    return header
