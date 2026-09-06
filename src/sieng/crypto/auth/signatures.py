"""AUTH_PQ_EXPLICIT: sign the transcript with Ed25519 and ML-DSA-65, and require both.

Two signatures rather than one, because neither algorithm alone covers the threat:

    Ed25519     decades of scrutiny, fast, small. Broken by a quantum computer.
    ML-DSA-65   post-quantum, and much younger. Lattice signatures are where a
                cryptanalytic surprise is most likely to turn up.

Requiring both means an attacker has to break both. Accepting either would mean an
attacker has to break only the weaker one, which makes the pair worse than either on its
own. So `verify` returns nothing and raises on any failure; there is no partial success to
report and no caller that could sensibly act on one.

    signature = Ed25519(64) || ML-DSA-65(3309)   = 3,373 bytes

That is why this mode is not the default. Three and a third kilobytes does not fit in a
512x512 cover at any sensible rate, so AUTH_PQ_EXPLICIT forces an external envelope.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from typing import Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa

from sieng.common.errors import CryptoError
from sieng.crypto.auth.identity import Identity, SecretKeys

ED25519_BYTES: Final = 64
MLDSA_BYTES: Final = 3309
SIGNATURE_BYTES: Final = ED25519_BYTES + MLDSA_BYTES


class SignatureError(CryptoError):
    """A signature did not verify.

    Carries no detail about which of the two failed. Telling an attacker whether their
    Ed25519 forgery passed before the ML-DSA one was checked would let them attack the
    two halves separately, which is exactly what requiring both is meant to prevent.
    """

    MESSAGE = "Signature verification failed"

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)


def sign(secret: SecretKeys, transcript: bytes) -> bytes:
    """Sign a transcript with both algorithms. Ed25519 first, then ML-DSA."""
    if not secret.can_sign():
        raise CryptoError(
            "This identity has no signing keys, so it cannot use AUTH_PQ_EXPLICIT. "
            "Generate an identity with signing=True, which produces a different "
            "fingerprint that contacts will need to verify."
        )
    return secret.ed25519_key().sign(transcript) + secret.mldsa_key().sign(transcript)


def verify(identity: Identity, transcript: bytes, signature: bytes) -> None:
    """Check both signatures. Raises SignatureError unless both pass.

    Both are always checked, even after the first fails, so the time taken does not say
    which one it was.
    """
    if not identity.can_sign():
        raise CryptoError(
            f"Identity {identity.display()} has no signing keys, so a signature from it "
            f"cannot be checked. Refusing rather than treating it as unsigned."
        )
    if len(signature) != SIGNATURE_BYTES:
        raise SignatureError

    classical = _check_ed25519(identity, transcript, signature[:ED25519_BYTES])
    quantum = _check_mldsa(identity, transcript, signature[ED25519_BYTES:])
    if not (classical and quantum):
        raise SignatureError


def _check_ed25519(identity: Identity, transcript: bytes, signature: bytes) -> bool:
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(identity.ed25519_public).verify(
            signature, transcript
        )
    except (InvalidSignature, ValueError):
        return False
    return True


def _check_mldsa(identity: Identity, transcript: bytes, signature: bytes) -> bool:
    try:
        mldsa.MLDSA65PublicKey.from_public_bytes(identity.mldsa_public).verify(
            signature, transcript
        )
    except (InvalidSignature, ValueError):
        return False
    return True


def split(signature: bytes) -> tuple[bytes, bytes]:
    """The two halves, for logging and tests. Never used to verify one without the other."""
    if len(signature) != SIGNATURE_BYTES:
        raise CryptoError(f"A signature is {SIGNATURE_BYTES} bytes, got {len(signature)}")
    return signature[:ED25519_BYTES], signature[ED25519_BYTES:]
