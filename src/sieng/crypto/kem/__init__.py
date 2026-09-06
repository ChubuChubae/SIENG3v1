"""Key establishment. Where a session secret comes from.

Hybrid on purpose: X25519 for the decades of scrutiny behind it, ML-KEM-768 for the
attacker who records traffic today and decrypts it once a quantum computer exists. Either
one failing leaves the other standing.

The combining is X-Wing's, reached through HPKE, and not ours. See hybrid.py for why that
mattered enough to be a recorded decision.
"""

from sieng.crypto.kem.hybrid import (
    PUBLIC_BYTES,
    SEALED_BYTES,
    SECRET_BYTES,
    PublicIdentity,
    SecretIdentity,
    derive_shared_secret,
    envelope_overhead,
    generate_identity,
    open_secret,
    seal_secret,
    static_exchange,
)
from sieng.crypto.kem.mlkem768 import ensure_available, is_available

__all__ = [
    "PUBLIC_BYTES",
    "SEALED_BYTES",
    "SECRET_BYTES",
    "PublicIdentity",
    "SecretIdentity",
    "derive_shared_secret",
    "ensure_available",
    "envelope_overhead",
    "generate_identity",
    "is_available",
    "open_secret",
    "seal_secret",
    "static_exchange",
]
