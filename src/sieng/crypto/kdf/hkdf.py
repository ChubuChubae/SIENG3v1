"""HKDF-SHA256, the one place keys are made from other keys.

Two halves, and keeping them apart matters:

    extract   takes something with entropy but no uniform shape, such as a Diffie-Hellman
              output, and produces a uniformly random 32 byte key.
    expand    takes an already uniform key and stretches it into as many separate keys as
              are needed, each one bound to a label.

Everything below the session level uses expand alone. The KEM output has already been
extracted once, and extracting a second time buys nothing while making the chain harder
to follow.

The arithmetic is not implemented here. It comes from `cryptography`, which is audited and
constant time. What this module owns is the shape: length prefixing, the fixed 32 byte
size, and refusing inputs that would silently produce a weak key.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import struct
from typing import Final

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand

from sieng.common.errors import CryptoError

HASH: Final = hashes.SHA256()

# Every key in this system is 32 bytes. Nothing here needs a different size, and allowing
# one would mean a caller could ask for 16 and weaken a key without anyone noticing.
KEY_BYTES: Final = 32

# RFC 5869 caps the output of a single expand at 255 * HashLen.
MAX_EXPAND_BYTES: Final = 255 * 32

# Length prefixes are two bytes, so no single field may exceed this.
MAX_FIELD_BYTES: Final = 0xFFFF


def length_prefixed(*fields: bytes) -> bytes:
    """Join fields so that no two different splits can produce the same bytes.

        LP(x) = uint16_be(len(x)) || x

    Without this, ("ab", "c") and ("a", "bc") concatenate to the same thing, and an
    attacker who controls where one field ends can move bytes between them while the
    transcript stays identical. That is the canonicalisation attack, and length prefixing
    is what closes it. SESSION_PROTOCOL.md 5.1 requires it on every field, with no
    exceptions.
    """
    out = bytearray()
    for index, field in enumerate(fields):
        if len(field) > MAX_FIELD_BYTES:
            raise CryptoError(
                f"Field {index} is {len(field)} bytes, which does not fit in a two byte "
                f"length prefix. Hash it down before putting it in a transcript."
            )
        out += struct.pack(">H", len(field)) + field
    return bytes(out)


def extract(ikm: bytes, info: bytes, salt: bytes = b"") -> bytes:
    """Turn raw key material into a uniform 32 byte key.

    Used once per session, on the KEM output. `info` is the suite label, so a secret
    derived under one suite can never equal one derived under another.
    """
    if not ikm:
        raise CryptoError("Refusing to derive a key from empty input key material")
    if not info:
        raise CryptoError("Refusing to derive a key without a label, see kdf/labels.py")
    return HKDF(algorithm=HASH, length=KEY_BYTES, salt=salt, info=info).derive(ikm)


def expand(key: bytes, info: bytes, length: int = KEY_BYTES) -> bytes:
    """Stretch an already uniform key into `length` bytes bound to `info`.

    This is the workhorse. Every arrow in the FORMAT_SPEC.md 2.1 diagram below the session
    level is one call to this.
    """
    if len(key) != KEY_BYTES:
        raise CryptoError(
            f"expand() needs a {KEY_BYTES} byte key, got {len(key)}. Anything shorter has "
            f"not been through extract() and is not uniform."
        )
    if not info:
        raise CryptoError("Refusing to derive a key without a label, see kdf/labels.py")
    if not 0 < length <= MAX_EXPAND_BYTES:
        raise CryptoError(f"Cannot expand to {length} bytes, the range is 1..{MAX_EXPAND_BYTES}")
    return HKDFExpand(algorithm=HASH, length=length, info=info).derive(key)


def expand_key(key: bytes, info: bytes) -> bytes:
    """expand() for the common case of wanting exactly one 32 byte key."""
    return expand(key, info, KEY_BYTES)


def counter_info(label: bytes, session_id: bytes, counter: int) -> bytes:
    """The info string for a per-message derivation: label, session, then counter.

    The counter is what stops two messages in one session from deriving the same keys,
    and the session id is what stops two sessions from colliding on the same counter.
    """
    if len(session_id) != 4:
        raise CryptoError(f"Session id must be 4 bytes, got {len(session_id)}")
    if not 0 <= counter < 1 << 24:
        raise CryptoError(f"Counter {counter} is outside the 24 bit range the header holds")
    return label + session_id + counter.to_bytes(3, "big")


def stream_info(label: bytes, counter: int) -> bytes:
    """The info string for the header keystream: label then counter, no session id.

    The header is what the receiver reads before it knows anything, including the session
    id, so this derivation cannot depend on it (FORMAT_SPEC.md 3.3).
    """
    if not 0 <= counter < 1 << 24:
        raise CryptoError(f"Counter {counter} is outside the 24 bit range the header holds")
    return label + counter.to_bytes(3, "big")
