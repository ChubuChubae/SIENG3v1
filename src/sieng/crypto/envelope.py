"""The SessionEnvelope: what one side has to send before any message can be read.

It carries the encapsulated session secret and enough identification for the recipient to
know which of their keys to use. After that the ratchet takes over and every later message
costs twelve bytes of header.

Two shapes, and the difference is not cosmetic:

    EXTERNAL   a separate .sess file. It may start with a magic string, because it is not
               pretending to be anything.
    INLINE     embedded in the image with the payload. No magic, no structure, nothing
               that could be recognised. Every bit has to be indistinguishable from noise.

There is a cost to EXTERNAL that the user has to be told about rather than left to work
out: a .sess file sitting on the disk is itself evidence that this system was used. It
proves nothing about the content, but it answers the question "was anything hidden here",
and that is usually the question that matters. INLINE avoids it and pays in capacity.

    EXTERNAL   1,244 bytes in a file that should not exist
    INLINE     1,240 bytes taken out of the payload's budget

Which one is right is decided by the carrier's capacity rather than by preference, because
an inline envelope that eats most of the cover pushes the embedding rate up, and a high
rate is the single thing detectors are best at spotting.

Sizes changed with D14: the encapsulation is now one 1,168 byte HPKE blob rather than a
32 byte ephemeral plus a 1,088 byte ML-KEM ciphertext.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import struct
from dataclasses import dataclass
from typing import Final

from sieng.common.errors import CryptoError
from sieng.crypto import header as header_module
from sieng.crypto.kem.hybrid import SEALED_BYTES

MAGIC: Final = b"SI3S"
VERSION: Final = 1
SUITE: Final = 1

FINGERPRINT_BYTES: Final = 32
SESSION_ID_BYTES: Final = 4

AUTH_IMPLICIT: Final = 0
AUTH_PQ_EXPLICIT: Final = 1

# Ed25519 plus ML-DSA-65. Both must verify, so both are always present or neither is.
SIGNATURE_BYTES: Final = 64 + 3309

# version, suite, auth_mode, envelope_mode, session_id, two fingerprints, the sealed secret
BODY_FORMAT: Final = f">BBBB{SESSION_ID_BYTES}s{FINGERPRINT_BYTES}s{FINGERPRINT_BYTES}s"
BODY_BYTES: Final = struct.calcsize(BODY_FORMAT) + SEALED_BYTES

INLINE_BYTES: Final = BODY_BYTES
EXTERNAL_BYTES: Final = len(MAGIC) + BODY_BYTES

# How many times over the envelope must fit before it is worth embedding it inline. Eight
# means the payload still gets seven eighths of the cover; below that the envelope is
# most of what is being hidden and the rate climbs for no benefit.
INLINE_HEADROOM: Final = 8


@dataclass(frozen=True)
class SessionEnvelope:
    """Everything the recipient needs to derive `ss` and start the ratchet."""

    session_id: bytes
    sender_fingerprint: bytes
    recipient_fingerprint: bytes
    sealed_secret: bytes
    auth_mode: int = AUTH_IMPLICIT
    envelope_mode: int = header_module.ENVELOPE_EXTERNAL
    signature: bytes = b""
    version: int = VERSION
    suite: int = SUITE

    def __post_init__(self) -> None:
        _check(len(self.session_id), SESSION_ID_BYTES, "Session id")
        _check(len(self.sender_fingerprint), FINGERPRINT_BYTES, "Sender fingerprint")
        _check(len(self.recipient_fingerprint), FINGERPRINT_BYTES, "Recipient fingerprint")
        _check(len(self.sealed_secret), SEALED_BYTES, "Sealed secret")
        if self.auth_mode not in (AUTH_IMPLICIT, AUTH_PQ_EXPLICIT):
            raise CryptoError(f"Unknown auth mode {self.auth_mode}")
        expected = SIGNATURE_BYTES if self.auth_mode == AUTH_PQ_EXPLICIT else 0
        if len(self.signature) != expected:
            raise CryptoError(
                f"Auth mode {self.auth_mode} needs a {expected} byte signature, "
                f"got {len(self.signature)}. Both Ed25519 and ML-DSA are required "
                f"together: one of the two verifying is not enough."
            )

    def body(self) -> bytes:
        """Everything except the magic, which is what INLINE embeds."""
        return (
            struct.pack(
                BODY_FORMAT,
                self.version,
                self.suite,
                self.auth_mode,
                self.envelope_mode,
                self.session_id,
                self.sender_fingerprint,
                self.recipient_fingerprint,
            )
            + self.sealed_secret
            + self.signature
        )

    def pack_external(self) -> bytes:
        """For the .sess file. Magic first, so a wrong file is identified as one."""
        return MAGIC + self.body()

    def pack_inline(self) -> bytes:
        """For embedding. No magic and no framing: it must look like noise."""
        return self.body()

    def size(self) -> int:
        return len(self.body())

    @classmethod
    def unpack_external(cls, raw: bytes) -> "SessionEnvelope":
        if not raw.startswith(MAGIC):
            raise CryptoError(f"This is not a SIENG3 session file: expected {MAGIC!r} at the start")
        return cls.unpack_inline(raw[len(MAGIC) :])

    @classmethod
    def unpack_inline(cls, raw: bytes) -> "SessionEnvelope":
        """Parse a body. The length tells us whether a signature is present."""
        if len(raw) not in (INLINE_BYTES, INLINE_BYTES + SIGNATURE_BYTES):
            raise CryptoError(
                f"A session envelope is {INLINE_BYTES} bytes, or "
                f"{INLINE_BYTES + SIGNATURE_BYTES} with a signature. Got {len(raw)}."
            )
        fixed = struct.calcsize(BODY_FORMAT)
        version, suite, auth_mode, envelope_mode, sid, sender, recipient = struct.unpack(
            BODY_FORMAT, raw[:fixed]
        )
        if version != VERSION or suite != SUITE:
            raise CryptoError(
                f"Session envelope version {version} suite {suite} is not one this build "
                f"implements, which is version {VERSION} suite {SUITE}"
            )
        return cls(
            version=version,
            suite=suite,
            auth_mode=auth_mode,
            envelope_mode=envelope_mode,
            session_id=sid,
            sender_fingerprint=sender,
            recipient_fingerprint=recipient,
            sealed_secret=raw[fixed : fixed + SEALED_BYTES],
            signature=raw[fixed + SEALED_BYTES :],
        )


def envelope_size(auth_mode: int = AUTH_IMPLICIT, inline: bool = True) -> int:
    """How many bytes an envelope takes, before one exists to measure."""
    base = INLINE_BYTES if inline else EXTERNAL_BYTES
    return base + (SIGNATURE_BYTES if auth_mode == AUTH_PQ_EXPLICIT else 0)


def choose_mode(
    capacity_base: int,
    payload_rate: float,
    auth_mode: int = AUTH_IMPLICIT,
    expected_file_count: int = 1,
) -> int:
    """Pick the envelope mode from what the carrier can actually hold.

    From the carrier's capacity, not from the user's preference. A user who asks for
    INLINE on a small image gets a much higher embedding rate than they asked for, and
    rate is what detectors measure best. The caller may override this, but it has to
    override it deliberately and the ui has to say what it costs.

    capacity_base is the non-zero AC count for a JPEG, so capacity_base * payload_rate is
    the number of bits available at the requested rate.
    """
    if payload_rate <= 0:
        raise CryptoError(f"Payload rate must be positive, got {payload_rate}")
    if expected_file_count < 1:
        raise CryptoError(f"Expected file count must be at least 1, got {expected_file_count}")

    capacity_bits = capacity_base * payload_rate
    envelope_bits = envelope_size(auth_mode, inline=True) * 8

    if capacity_bits >= envelope_bits * INLINE_HEADROOM:
        return header_module.ENVELOPE_INLINE
    if capacity_bits >= envelope_bits * INLINE_HEADROOM / expected_file_count:
        return header_module.ENVELOPE_MULTIPART
    return header_module.ENVELOPE_EXTERNAL


def _check(actual: int, expected: int, what: str) -> None:
    if actual != expected:
        raise CryptoError(f"{what} must be {expected} bytes, got {actual}")
