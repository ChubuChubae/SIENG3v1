"""The contract every carrier honours. This is what lets JPEG and PNG share one stack.

Below this layer nothing knows the word JPEG. A carrier turns a file into Plane objects,
takes them back, and writes the file out again without disturbing anything it did not
have to touch.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from sieng.common.types import Domain, SecurityTier
from sieng.domain.plane import Plane

# How many bytes sniff() reads to identify a file. Every magic we care about fits.
SNIFF_BYTES = 32


class Carrier(ABC):
    """A file that can hold hidden data, seen as numbers.

    The class attributes are metadata the registry and the ui read without instantiating
    anything, so a dropdown can be built from what is registered rather than a hardcoded list.
    """

    suffixes: ClassVar[tuple[str, ...]]
    magic: ClassVar[tuple[bytes, ...]]
    domain: ClassVar[Domain]

    # False means the format cannot be written back unchanged, so embedding in it would
    # leave recompression traces. Such a carrier must never be used for real hiding.
    lossless_roundtrip: ClassVar[bool]

    # Phase 1 ships only "strong". The other two exist so the warning path is written and
    # tested before Phase 2 brings back carriers that deserve them.
    security_tier: ClassVar[SecurityTier]

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.loaded = False

    @classmethod
    def sniff(cls, head: bytes) -> bool:
        """True if these first bytes look like this format.

        Content decides, never the file name. A renamed file is common and a deliberately
        misnamed one is a classic way to confuse a parser into the wrong code path.
        """
        return any(head.startswith(m) for m in cls.magic)

    @abstractmethod
    def load(self) -> None:
        """Read the file into memory, separating what may change from what must not."""

    @abstractmethod
    def planes(self) -> list[Plane]:
        """Return the changeable numbers. JPEG returns one plane per colour component."""

    @abstractmethod
    def apply(self, planes: list[Plane]) -> None:
        """Take modified planes back into the internal structure."""

    @abstractmethod
    def save(self, destination: Path) -> None:
        """Write the file out. Everything not modified must come out byte for byte the same."""

    @abstractmethod
    def fingerprint(self) -> bytes:
        """Hash of the properties that embedding does not change, used as AEAD aad.

        It must be built only from things the receiver can recompute from the stego file.
        Never include coefficient values: they are exactly what embedding changes.
        """

    @abstractmethod
    def capacity_base(self) -> int:
        """The denominator of the payload rate. For JPEG this is the non-zero AC count."""

    def require_loaded(self) -> None:
        """Guard for methods that only make sense after load()."""
        if not self.loaded:
            raise RuntimeError(
                f"{type(self).__name__} has not loaded {self.path.name} yet. Call load() first."
            )

    @staticmethod
    def hash_fields(*fields: bytes) -> bytes:
        """Length-prefixed SHA-256 over the given fields.

        Length prefixes stop two different field sets from producing the same digest,
        which is the same canonicalisation problem the transcript has (SESSION_PROTOCOL.md 5.1).
        """
        digest = hashlib.sha256()
        for field in fields:
            digest.update(len(field).to_bytes(2, "big"))
            digest.update(field)
        return digest.digest()
