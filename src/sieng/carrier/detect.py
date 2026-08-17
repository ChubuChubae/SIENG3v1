"""Work out what a file really is, from its bytes.

The file name is never consulted. Users rename files, and a file named .png that is
really something else is a classic way to push a parser down the wrong path. Formats
outside the Phase 1 scope are refused by name so the message can say what is going on,
instead of failing later with something confusing.
"""

from pathlib import Path

from sieng.carrier.base import SNIFF_BYTES, Carrier
from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import LossyCarrierError, UnsupportedCarrierError

# Formats we can name but deliberately do not support in Phase 1. Saying which phase
# they arrive in is more useful than "unsupported file".
DEFERRED_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"BM", "BMP", "Phase 2"),
    (b"II*\x00", "TIFF", "Phase 2"),
    (b"MM\x00*", "TIFF", "Phase 2"),
    (b"RIFF", "WAV or AVI", "Phase 2"),
    (b"ID3", "MP3", "Phase 2"),
    (b"\xff\xfb", "MP3", "Phase 2"),
    (b"%PDF", "PDF", "not planned"),
    (b"PK\x03\x04", "ZIP or Office document", "not planned"),
    (b"\x7fELF", "ELF binary", "not planned"),
    (b"MZ", "Windows executable", "not planned"),
)

# WEBP and MP4 hide behind a container magic, so they need the bytes further in.
WEBP_AT_8 = b"WEBP"
MP4_AT_4 = b"ftyp"


def read_head(path: Path, size: int = SNIFF_BYTES) -> bytes:
    """Read the first bytes of a file, or raise a clear error if it cannot be read."""
    path = Path(path)
    if not path.is_file():
        raise UnsupportedCarrierError(f"Not a file: {path}")
    with path.open("rb") as handle:
        return handle.read(size)


def describe_deferred(head: bytes) -> str | None:
    """Name the format if it is one we know but do not support yet."""
    if len(head) >= 12 and head[8:12] == WEBP_AT_8:
        return "WEBP arrives in Phase 2"
    if len(head) >= 8 and head[4:8] == MP4_AT_4:
        return "MP4 arrives in Phase 2"
    for magic, name, when in DEFERRED_MAGIC:
        if head.startswith(magic):
            if when == "not planned":
                return f"{name} is not a carrier"
            return f"{name} arrives in {when}"
    return None


def sniff(path: Path, registry: CarrierRegistry) -> type[Carrier]:
    """Return the carrier class for this file, going by content only."""
    head = read_head(path)

    carrier = registry.match_magic(head)
    if carrier is not None:
        return carrier

    detail = describe_deferred(head)
    supported = ", ".join(registry.suffixes()) or "nothing yet"
    raise UnsupportedCarrierError(
        f"Cannot embed in {Path(path).name}: "
        + (f"{detail}. " if detail else "unrecognised format. ")
        + f"Phase 1 supports {supported}. "
        f"The file's own bytes decide this, not its name."
    )


def open_carrier(
    path: Path, registry: CarrierRegistry, *, require_lossless: bool = True
) -> Carrier:
    """Identify, build and load a carrier in one step.

    require_lossless defaults to True because a carrier that cannot be written back
    unchanged leaves recompression traces, which defeats the point of hiding anything.
    Analysis tools that only read may pass False.
    """
    carrier_class = sniff(path, registry)

    if require_lossless and not carrier_class.lossless_roundtrip:
        raise LossyCarrierError(
            f"{carrier_class.__name__} cannot write {Path(path).name} back unchanged, "
            f"so embedding in it would leave recompression traces a detector can find."
        )

    carrier = carrier_class(Path(path))
    carrier.load()
    return carrier
