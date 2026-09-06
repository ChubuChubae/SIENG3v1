"""Every domain separation string in the project, in one place.

A label is what stops two different keys derived from the same secret from colliding.
`CK[n]` produces both the message key and the next chain key, and the only thing keeping
those two apart is that one asks for "msg" and the other asks for "ratchet". Get a label
wrong and the two become the same 32 bytes, which is silent and total.

Three rules, and they are not style preferences:

    1. Never write one of these strings anywhere else. Import it from here.
    2. Never change a string. Every stego file ever written with it becomes unreadable.
       A new derivation gets a new label, and a changed derivation gets a new SUITE.
    3. Never reuse one for a second purpose.

Source of truth: FORMAT_SPEC.md 2.2. This file must match that table exactly.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from collections import Counter
from typing import Final

# Bumped when any derivation formula, label or layout changes. The receiver reads this
# from the header and refuses a file it does not recognise rather than guessing.
SUITE_VERSION: Final = 1

# ---- session level ---------------------------------------------------------

# Binds the shared secret to the exact KEM combination that produced it. A file made with
# a different KEM cannot derive the same ss even from the same inputs.
KEM_SUITE: Final = b"sieng3/kem/x25519-mlkem768/v1"

# ss -> K_hdr_session. Session level on purpose: the header holds the counter, so the key
# that decrypts the header cannot itself depend on the counter (FORMAT_SPEC.md 3.3).
HEADER_KEY: Final = b"sieng3/hdrkey/v1"

# ss -> CK[0], the root of the ratchet chain.
CHAIN_INIT: Final = b"sieng3/chain/v1"

# ---- message level ---------------------------------------------------------

# CK[n] -> CK[n+1]. The one-way step that makes past messages unrecoverable.
RATCHET_STEP: Final = b"sieng3/ratchet/v1"

# CK[n] -> MK[n]. Same input as RATCHET_STEP, different label, and that is the whole
# reason the message key does not equal the next chain key.
MESSAGE_KEY: Final = b"sieng3/msg/v1"

# MK[n] -> the four subkeys at once, as one 108 byte expansion.
MESSAGE_KEYS: Final = b"sieng3/msgkeys/v1"

# K_hdr_session -> the 12 byte keystream the header is whitened with.
HEADER_STREAM: Final = b"sieng3/hdrstream/v1"

# ---- identity and storage --------------------------------------------------

# Prefix of the transcript. Note the different shape: this one is a separator inside a
# hash input rather than an HKDF info string, which is why it does not follow the
# sieng3/... form. It comes from SESSION_PROTOCOL.md and must stay as written there.
TRANSCRIPT: Final = b"SIENG3-transcript-v1"

# Wraps a private key before it touches the disk.
KEYSTORE_WRAP: Final = b"sieng3/keystore/v1"

# Encrypts the ratchet state file. A separate label from KEYSTORE_WRAP so that a stolen
# state file cannot be fed to the keystore reader or the other way round.
STATE_WRAP: Final = b"sieng3/state/v1"


ALL_LABELS: Final = (
    KEM_SUITE,
    HEADER_KEY,
    CHAIN_INIT,
    RATCHET_STEP,
    MESSAGE_KEY,
    MESSAGE_KEYS,
    HEADER_STREAM,
    TRANSCRIPT,
    KEYSTORE_WRAP,
    STATE_WRAP,
)


def check_labels_are_distinct() -> None:
    """Fail loudly at import time if two labels ever become equal.

    A duplicate here means two different keys are derived identically. It would not raise
    anything, produce no wrong output, and simply make the system insecure, so the check
    has to be mechanical rather than left to review.
    """
    counts = Counter(ALL_LABELS)
    duplicates = sorted(label.decode() for label, n in counts.items() if n > 1)
    if duplicates:
        raise AssertionError(
            f"Duplicate KDF labels: {duplicates}. "
            f"Two derivations sharing a label produce the same key."
        )


check_labels_are_distinct()
