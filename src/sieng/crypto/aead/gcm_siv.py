"""AES-256-GCM-SIV: the encryption every payload actually passes through.

Why SIV rather than plain GCM, which is faster and more common. With GCM, using the same
key and nonce twice does not merely leak that two messages are equal: it leaks the XOR of
the two plaintexts and, far worse, it leaks the authentication key itself, after which an
attacker can forge any message they like. Nonce reuse is not a degraded mode, it is total
failure.

And nonce reuse is reachable here. The nonce comes from the ratchet counter, and the
ratchet state lives in a file on a normal computer. Restore a backup, copy a folder to a
second machine, or crash halfway through a save, and the counter goes backwards. That is
an accident an ordinary user can have, not an attack. GCM-SIV degrades gracefully in
exactly that case: reusing a nonce reveals only that the two plaintexts were identical,
and nothing else. RFC 8452 exists for this situation.

    seal    key, nonce, plaintext, aad -> ciphertext || tag
    open_   the same in reverse, or DecryptError. Never anything else.

The name open_ has a trailing underscore because `open` is a builtin, and shadowing it in
a crypto module is the kind of small confusion that becomes a large one.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV

from sieng.common.errors import CryptoError, DecryptError

# AES-256. The 128 bit variant is not offered: one key size means one thing to review.
KEY_BYTES: Final = 32

# RFC 8452 fixes the nonce at 96 bits. It is not configurable.
NONCE_BYTES: Final = 12

# The authentication tag, appended to the ciphertext by seal().
TAG_BYTES: Final = 16

# GCM-SIV output is the plaintext length plus the tag, always. Callers rely on this to
# work out capacity before they have a ciphertext to measure (FORMAT_SPEC.md 5.3).
OVERHEAD: Final = TAG_BYTES


def seal(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt and authenticate. Returns ciphertext with the tag appended.

    `aad` is authenticated but not encrypted. This project puts the header and the
    carrier fingerprint there, which is what makes a ciphertext lifted out of one image
    and dropped into another fail to open (THREAT_MODEL.md S10).
    """
    check_key(key)
    check_nonce(nonce)
    return AESGCMSIV(key).encrypt(nonce, plaintext, aad)


def open_(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Decrypt and verify, or raise DecryptError.

    Every failure raises the same bare DecryptError: wrong key, tampered ciphertext,
    wrong image, truncated input, mismatched aad. The caller is not told which, because
    an error that distinguishes them is an oracle an attacker can query.

    The length check below runs before the tag check and could in principle be timed, but
    the length of a ciphertext is already public: it is the number of bytes the attacker
    handed in. Nothing secret is learned from it.
    """
    check_key(key)
    check_nonce(nonce)
    if len(ciphertext) < TAG_BYTES:
        raise DecryptError
    try:
        return AESGCMSIV(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag:
        raise DecryptError from None
    except Exception:
        # Anything the library can throw becomes the same error. A library that starts
        # raising a new exception type must not turn into a distinguishable failure here.
        raise DecryptError from None


def sealed_length(plaintext_length: int) -> int:
    """How long the ciphertext will be, without producing one.

    Needed because capacity has to be checked against the cover before encrypting, and
    encrypting first to measure would mean holding a ciphertext that may not fit.
    """
    if plaintext_length < 0:
        raise CryptoError(f"Plaintext length cannot be negative, got {plaintext_length}")
    return plaintext_length + OVERHEAD


def check_key(key: bytes) -> None:
    """A wrong key size here would silently select AES-128 or AES-192 in some libraries."""
    if len(key) != KEY_BYTES:
        raise CryptoError(
            f"AES-256-GCM-SIV needs a {KEY_BYTES} byte key, got {len(key)}. "
            f"Keys come from crypto/kdf, never from a caller."
        )


def check_nonce(nonce: bytes) -> None:
    if len(nonce) != NONCE_BYTES:
        raise CryptoError(f"AES-256-GCM-SIV needs a {NONCE_BYTES} byte nonce, got {len(nonce)}")
