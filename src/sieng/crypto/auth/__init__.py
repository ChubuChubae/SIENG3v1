"""Who sent this, and is that who they claim to be.

Four concerns, kept apart because they fail differently:

    transcript    what the two sides must agree on, byte for byte
    identity      the four public keys and the fingerprint over them
    signatures    AUTH_PQ_EXPLICIT, where both algorithms must verify
    trust_store   which fingerprints this machine accepts, and why

The weakest link is not in any of them. It is the moment a human decides that a
fingerprint belongs to the person they mean, and nothing here can do that for them.
"""

from sieng.crypto.auth.identity import Identity, SecretKeys, generate, load_public
from sieng.crypto.auth.signatures import SIGNATURE_BYTES, SignatureError, sign, verify
from sieng.crypto.auth.transcript import build
from sieng.crypto.auth.trust_store import (
    VERIFICATION_METHODS,
    TrustEntry,
    TrustStore,
)

__all__ = [
    "SIGNATURE_BYTES",
    "VERIFICATION_METHODS",
    "Identity",
    "SecretKeys",
    "SignatureError",
    "TrustEntry",
    "TrustStore",
    "build",
    "generate",
    "load_public",
    "sign",
    "verify",
]
