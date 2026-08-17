"""The only place that talks to jpeglib, plus the file surgery its output needs.

Measured on jpeglib 1.0.2 with libjpeg 6b (tools/spike_jpeglib.py), a round trip through
read_dct and write_dct keeps the entropy coded data byte for byte identical but changes
three things in the headers:

    a second JFIF APP0 is appended, adding 18 bytes
    SOF component ids are renumbered from 1,2,3 to 0,1,2
    SOS component selectors are renumbered the same way

None of that touches a coefficient, but all of it is visible to anyone comparing against
an original, which is exactly the comparison we must survive. So the file is rebuilt here:
the original's headers verbatim, followed by the freshly encoded entropy data.

That splice is only valid while the quantisation and Huffman tables stay the same, because
the entropy data is meaningless without the tables that produced it. verify_tables_match
checks that on every write and refuses rather than producing a file that decodes to noise.
"""

from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

from sieng.common.errors import CorruptCarrierError, UnsupportedCarrierError
from sieng.domain.plane import Array

SOI = 0xD8
EOI = 0xD9
SOS = 0xDA
DQT = 0xDB
DHT = 0xC4

# Markers that carry no length field, so the walk steps past them by two bytes.
STANDALONE = {SOI, EOI, 0x01} | set(range(0xD0, 0xD8))

BLOCK = 8


class Segment(NamedTuple):
    """One JPEG marker segment. length is the declared payload, excluding the marker."""

    marker: int
    offset: int
    length: int

    @property
    def end(self) -> int:
        """Offset just past this segment. For SOS this is where entropy data begins."""
        return self.offset + 2 + self.length


def parse_segments(raw: bytes) -> list[Segment]:
    """Walk the segments up to and including SOS."""
    segments: list[Segment] = []
    offset = 0
    while offset < len(raw) - 1:
        if raw[offset] != 0xFF:
            offset += 1
            continue
        marker = raw[offset + 1]
        if marker in (0xFF, 0x00):
            offset += 1
            continue
        if marker in STANDALONE:
            segments.append(Segment(marker, offset, 0))
            offset += 2
            if marker == EOI:
                break
            continue
        length = int.from_bytes(raw[offset + 2 : offset + 4], "big")
        segments.append(Segment(marker, offset, length))
        offset += 2 + length
        if marker == SOS:
            break
    return segments


def find_sos(raw: bytes) -> Segment:
    """The start of scan segment, after which the entropy coded data runs to EOI."""
    segments = parse_segments(raw)
    if not segments or segments[-1].marker != SOS:
        raise CorruptCarrierError("JPEG has no start of scan marker, it cannot be decoded")
    return segments[-1]


def collect(raw: bytes, markers: tuple[int, ...]) -> list[bytes]:
    """Every segment of the given kinds, as raw bytes, in file order."""
    return [
        raw[segment.offset : segment.end]
        for segment in parse_segments(raw)
        if segment.marker in markers
    ]


def verify_tables_match(original: bytes, written: bytes) -> None:
    """Refuse to splice if the tables changed.

    libjpeg may re-derive Huffman tables when the coefficients change. If it does, the new
    entropy data is encoded against tables the original file does not contain, and pasting
    it after the original headers produces a file that decodes to noise. Failing here is
    the only safe outcome: a silently broken stego file is worse than no file.
    """
    for marker, name in ((DQT, "quantisation"), (DHT, "Huffman")):
        if collect(original, (marker,)) != collect(written, (marker,)):
            raise CorruptCarrierError(
                f"libjpeg rewrote the {name} tables while encoding, so the original headers "
                f"no longer describe the new scan data. The splice in _jpeg_codec is not "
                f"valid for this image. Re-check tools/spike_jpeglib.py before going further."
            )


def blocks_to_grid(blocks: Array) -> Array:
    """(by, bx, 8, 8) as jpeglib returns it, to the (h, w) grid the domain layer expects.

    domain.build_changeable_mask finds the DC coefficient at [::8, ::8], which only holds
    if each 8x8 block sits as a contiguous tile in a 2-D grid.
    """
    by, bx = blocks.shape[0], blocks.shape[1]
    grid: Array = blocks.transpose(0, 2, 1, 3).reshape(by * BLOCK, bx * BLOCK)
    return np.ascontiguousarray(grid)


def grid_to_blocks(grid: Array) -> Array:
    """The inverse of blocks_to_grid."""
    by = grid.shape[0] // BLOCK
    bx = grid.shape[1] // BLOCK
    blocks: Array = grid.reshape(by, BLOCK, bx, BLOCK).transpose(0, 2, 1, 3)
    return np.ascontiguousarray(blocks)


def read_dct(path: Path) -> Any:
    """Read quantised coefficients. Never dequantise, never run an inverse DCT."""
    try:
        import jpeglib
    except ImportError as error:
        raise UnsupportedCarrierError(
            "jpeglib is not installed, so JPEG files cannot be opened. Run: pip install jpeglib"
        ) from error

    try:
        return jpeglib.read_dct(str(path))
    except Exception as error:
        # Catching everything is deliberate: whatever jpeglib raises, the file is unusable
        # and the caller only needs one clear reason.
        raise CorruptCarrierError(
            f"jpeglib could not read {Path(path).name}: {type(error).__name__}: {error}"
        ) from error


def encode_to_bytes(dct: Any, scratch: Path) -> bytes:
    """Have jpeglib write the file, and hand back the bytes.

    jpeglib only writes to a path, so a scratch file is unavoidable. The caller decides
    where it goes so it can be put next to the destination rather than in a shared temp
    directory, where a stego file has no business sitting.
    """
    try:
        dct.write_dct(str(scratch))
        return scratch.read_bytes()
    finally:
        scratch.unlink(missing_ok=True)


def splice(original: bytes, written: bytes) -> bytes:
    """Original headers plus newly encoded entropy data.

    Everything the original said about itself is preserved: marker order, the JFIF header,
    component numbering, any EXIF or comment. Only the compressed image data is new.
    """
    verify_tables_match(original, written)
    return original[: find_sos(original).end] + written[find_sos(written).end :]
