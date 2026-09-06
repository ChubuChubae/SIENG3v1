"""Authenticated encryption. One algorithm, deliberately.

AES-256-GCM-SIV (RFC 8452) and nothing else. A second cipher would mean a negotiation,
a negotiation means a downgrade path, and a downgrade path is a vulnerability that is
easier to add than to remove.
"""

from sieng.crypto.aead.gcm_siv import (
    KEY_BYTES,
    NONCE_BYTES,
    OVERHEAD,
    TAG_BYTES,
    open_,
    seal,
    sealed_length,
)

__all__ = [
    "KEY_BYTES",
    "NONCE_BYTES",
    "OVERHEAD",
    "TAG_BYTES",
    "open_",
    "seal",
    "sealed_length",
]
