"""Which identities are trusted, and the record of why each one is.

The hardest problem in this file is not cryptographic. Deciding that a public key really
belongs to the person you think it does cannot be solved by any algorithm: at some point
two humans have to compare a fingerprint over a channel an attacker does not control.
Everything here exists to support that moment and to remember what happened at it.

So a trust entry records *how* it was established, not merely that it was:

    qr       met in person and scanned. The strongest.
    voice    read the fingerprint aloud on a call. Strong if you know the voice.
    manual   typed it in from somewhere else. Depends on where.

There is deliberately no "accepted without checking". If that option existed the interface
would offer it, users would take it every time, and every layer of authentication built
underneath would be decoration. SESSION_PROTOCOL.md 3.3 makes the same point about the
GUI, which must ask the user to type back groups of the fingerprint rather than presenting
a button to click.

Revocation is local. There is no network transport in this version, so a revoked identity
is revoked on this machine and nowhere else, and the docstrings say so rather than letting
a user assume otherwise. A revoked identity cannot start a new session, but old sessions
still decrypt: revoking a key is not a reason to lose the messages it already protected.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from sieng.common.errors import CryptoError
from sieng.crypto.auth.identity import Identity, load_public

VERIFIED_QR: Final = "qr"
VERIFIED_VOICE: Final = "voice"
VERIFIED_MANUAL: Final = "manual"

# The ways a fingerprint can have been compared, strongest first. Nothing else is
# accepted, and in particular there is no value meaning "the user clicked past it".
VERIFICATION_METHODS: Final = (VERIFIED_QR, VERIFIED_VOICE, VERIFIED_MANUAL)

FORMAT_VERSION: Final = 1


@dataclass
class TrustEntry:
    """One identity, and the account of how it came to be trusted."""

    identity: Identity
    verified_via: str
    label: str = ""
    revoked: bool = False
    revoked_reason: str = ""

    def __post_init__(self) -> None:
        if self.verified_via not in VERIFICATION_METHODS:
            raise CryptoError(
                f"'{self.verified_via}' is not a way of verifying a fingerprint. "
                f"The options are: {', '.join(VERIFICATION_METHODS)}. There is no value "
                f"for accepting an identity without comparing it, on purpose."
            )

    def fingerprint(self) -> bytes:
        return self.identity.fingerprint()

    def describe(self) -> str:
        """One line for the ui, shown every time this identity is used.

        Every time, not once at setup. A user who verified a key by typing it in from an
        email six months ago should be reminded of that when they rely on it.
        """
        name = self.label or self.identity.display()
        if self.revoked:
            return f"{name} - REVOKED ({self.revoked_reason or 'no reason recorded'})"
        return f"{name} - verified via {self.verified_via}"


class TrustStore:
    """The identities this machine trusts. Local, and no attempt is made to hide that."""

    def __init__(self) -> None:
        self._entries: dict[bytes, TrustEntry] = {}

    def add(
        self,
        identity: Identity,
        verified_via: str,
        label: str = "",
    ) -> TrustEntry:
        """Trust an identity, recording how it was verified.

        Adding the same fingerprint twice is allowed and updates the record. Adding a
        *different* identity under a label already in use is not stopped here, because the
        fingerprint is what identifies someone and labels are only for humans.
        """
        entry = TrustEntry(identity, verified_via, label)
        self._entries[entry.fingerprint()] = entry
        return entry

    def get(self, fingerprint: bytes) -> TrustEntry:
        entry = self._entries.get(fingerprint)
        if entry is None:
            raise CryptoError(
                f"Identity {fingerprint.hex()[:16]} is not in this trust store. It has to "
                f"be verified out of band before it can be used."
            )
        return entry

    def is_trusted(self, fingerprint: bytes) -> bool:
        """True only if present and not revoked."""
        entry = self._entries.get(fingerprint)
        return entry is not None and not entry.revoked

    def require_for_new_session(self, identity: Identity) -> TrustEntry:
        """The check that runs before every new session.

        A revoked identity is refused here and nowhere else, which is why this is a
        separate method from `get`: decrypting an old message must still work.
        """
        entry = self.get(identity.fingerprint())
        if entry.revoked:
            raise CryptoError(
                f"Identity {identity.display()} was revoked "
                f"({entry.revoked_reason or 'no reason recorded'}) and cannot start a new "
                f"session. Messages already received from it can still be read."
            )
        return entry

    def revoke(self, fingerprint: bytes, reason: str = "") -> TrustEntry:
        """Mark an identity as no longer trusted. Local to this machine only."""
        entry = self.get(fingerprint)
        entry.revoked = True
        entry.revoked_reason = reason
        return entry

    def entries(self) -> list[TrustEntry]:
        """Every entry, revoked ones included, in insertion order."""
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    # ---- persistence -------------------------------------------------------

    def to_json(self) -> str:
        """Serialise. Public keys only: nothing secret is ever in a trust store."""
        payload = {
            "version": FORMAT_VERSION,
            "entries": [_entry_to_dict(entry) for entry in self._entries.values()],
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "TrustStore":
        data = json.loads(text)
        if data.get("version") != FORMAT_VERSION:
            raise CryptoError(
                f"Trust store format version {data.get('version')} is not supported by "
                f"this build, which reads version {FORMAT_VERSION}"
            )
        store = cls()
        for item in data["entries"]:
            entry = _entry_from_dict(item)
            store._entries[entry.fingerprint()] = entry
        return store

    def save(self, path: Path) -> None:
        """Written through a temporary file, so a crash cannot leave a half trust store.

        A truncated trust store is worse than none: it silently drops identities, and the
        next handshake with one of them looks like an attack rather than a lost file.
        """
        path = Path(path)
        scratch = path.with_suffix(path.suffix + ".partial")
        scratch.write_text(self.to_json(), encoding="utf-8")
        scratch.replace(path)

    @classmethod
    def load(cls, path: Path) -> "TrustStore":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def _entry_to_dict(entry: TrustEntry) -> dict[str, Any]:
    return {
        "x25519": entry.identity.kem.x25519.hex(),
        "mlkem": entry.identity.kem.mlkem.hex(),
        "ed25519": entry.identity.ed25519_public.hex(),
        "mldsa": entry.identity.mldsa_public.hex(),
        "verified_via": entry.verified_via,
        "label": entry.label,
        "revoked": entry.revoked,
        "revoked_reason": entry.revoked_reason,
    }


def _entry_from_dict(item: dict[str, Any]) -> TrustEntry:
    identity = load_public(
        bytes.fromhex(item["x25519"]),
        bytes.fromhex(item["mlkem"]),
        bytes.fromhex(item["ed25519"]),
        bytes.fromhex(item["mldsa"]),
    )
    return TrustEntry(
        identity=identity,
        verified_via=item["verified_via"],
        label=item.get("label", ""),
        revoked=item.get("revoked", False),
        revoked_reason=item.get("revoked_reason", ""),
    )
