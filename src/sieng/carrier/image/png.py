"""PNG carrier: spatial samples, written back without disturbing anything else.

Two decisions shape this file.

The original bytes are kept and written straight back when nothing was modified, so an
untouched file really is untouched rather than merely equivalent.

When pixels do change, the per row filter types from the original are reused instead of
picking new ones. A different filter choice changes every byte of the pixel stream even
where the pixels are identical, which is a far larger difference than the embedding itself.
"""

import struct
import zlib
from pathlib import Path
from typing import ClassVar

import numpy as np

from sieng.carrier.base import Carrier
from sieng.carrier.image.png_metadata import (
    IDAT,
    SIGNATURE,
    Chunk,
    Header,
    build_png,
    join_idat,
    parse_chunks,
    parse_header,
    trailing_bytes,
)
from sieng.common.errors import CorruptCarrierError, UnsupportedCarrierError
from sieng.common.types import SPATIAL_DOMAIN, STRONG_TIER, Domain, SecurityTier
from sieng.domain.plane import Array, Plane
from sieng.domain.selection import build_changeable_mask

# Bytes per pixel for each PNG colour type, at 8 bits per sample.
CHANNELS: dict[int, int] = {0: 1, 2: 3, 4: 2, 6: 4}
PALETTE_COLOUR_TYPE = 3
SUPPORTED_BIT_DEPTH = 8

FILTER_NONE = 0
FILTER_SUB = 1
FILTER_UP = 2
FILTER_AVERAGE = 3
FILTER_PAETH = 4


def paeth(left: int, above: int, upper_left: int) -> int:
    """The PNG predictor: whichever neighbour the gradient points at."""
    estimate = left + above - upper_left
    da = abs(estimate - left)
    db = abs(estimate - above)
    dc = abs(estimate - upper_left)
    if da <= db and da <= dc:
        return left
    if db <= dc:
        return above
    return upper_left


def unfilter(raw: bytes, height: int, stride: int, bpp: int) -> tuple[Array, Array]:
    """Undo the per row filters, returning the pixel bytes and the filter type of each row.

    Sub, Average and Paeth each depend on bytes reconstructed earlier in the same row,
    so those rows are walked one byte at a time. None and Up are vectorised. If PNG ever
    becomes a hot path this is the loop to move into C.
    """
    expected = height * (stride + 1)
    if len(raw) < expected:
        raise CorruptCarrierError(
            f"PNG pixel stream is {len(raw)} bytes but the header describes {expected}"
        )

    out = np.zeros((height, stride), dtype=np.uint8)
    filters = np.zeros(height, dtype=np.uint8)

    for row in range(height):
        base = row * (stride + 1)
        filter_type = raw[base]
        filters[row] = filter_type
        line = np.frombuffer(raw, dtype=np.uint8, count=stride, offset=base + 1).astype(np.int16)
        prior = out[row - 1].astype(np.int16) if row else np.zeros(stride, dtype=np.int16)

        if filter_type == FILTER_NONE:
            out[row] = line.astype(np.uint8)
        elif filter_type == FILTER_UP:
            out[row] = ((line + prior) % 256).astype(np.uint8)
        elif filter_type == FILTER_SUB:
            current = np.zeros(stride, dtype=np.int16)
            for i in range(stride):
                left = current[i - bpp] if i >= bpp else 0
                current[i] = (line[i] + left) % 256
            out[row] = current.astype(np.uint8)
        elif filter_type in (FILTER_AVERAGE, FILTER_PAETH):
            current = np.zeros(stride, dtype=np.int16)
            for i in range(stride):
                left = int(current[i - bpp]) if i >= bpp else 0
                above = int(prior[i])
                upper_left = int(prior[i - bpp]) if i >= bpp else 0
                if filter_type == FILTER_AVERAGE:
                    predictor = (left + above) // 2
                else:
                    predictor = paeth(left, above, upper_left)
                current[i] = (int(line[i]) + predictor) % 256
            out[row] = current.astype(np.uint8)
        else:
            raise CorruptCarrierError(f"Unknown PNG filter type {filter_type} on row {row}")

    return out, filters


def refilter(pixels: Array, filters: Array, bpp: int) -> bytes:
    """Re-apply the original filter types to modified pixel rows."""
    height, stride = pixels.shape
    chunks: list[bytes] = []

    for row in range(height):
        filter_type = int(filters[row])
        line = pixels[row].astype(np.int16)
        prior = pixels[row - 1].astype(np.int16) if row else np.zeros(stride, dtype=np.int16)

        if filter_type == FILTER_NONE:
            encoded = line % 256
        elif filter_type == FILTER_UP:
            encoded = (line - prior) % 256
        elif filter_type == FILTER_SUB:
            shifted = np.zeros(stride, dtype=np.int16)
            shifted[bpp:] = line[:-bpp]
            encoded = (line - shifted) % 256
        else:
            encoded = np.zeros(stride, dtype=np.int16)
            for i in range(stride):
                left = int(line[i - bpp]) if i >= bpp else 0
                above = int(prior[i])
                upper_left = int(prior[i - bpp]) if i >= bpp else 0
                if filter_type == FILTER_AVERAGE:
                    predictor = (left + above) // 2
                else:
                    predictor = paeth(left, above, upper_left)
                encoded[i] = (int(line[i]) - predictor) % 256

        chunks.append(bytes([filter_type]) + encoded.astype(np.uint8).tobytes())

    return b"".join(chunks)


class PngCarrier(Carrier):
    """Lossless spatial carrier. Every sample may move."""

    suffixes: ClassVar[tuple[str, ...]] = (".png",)
    magic: ClassVar[tuple[bytes, ...]] = (SIGNATURE,)
    domain: ClassVar[Domain] = SPATIAL_DOMAIN
    lossless_roundtrip: ClassVar[bool] = True
    security_tier: ClassVar[SecurityTier] = STRONG_TIER

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.raw = b""
        self.chunks: list[Chunk] = []
        self.header: Header | None = None
        self.pixels: Array = np.zeros(0, dtype=np.uint8)
        self.filters: Array = np.zeros(0, dtype=np.uint8)
        self.trailing = b""
        self.modified = False

    def load(self) -> None:
        self.raw = self.path.read_bytes()
        try:
            self.chunks = parse_chunks(self.raw)
        except ValueError as error:
            raise CorruptCarrierError(str(error)) from error

        header = parse_header(self.chunks)
        self.check_supported(header)
        self.header = header
        self.trailing = trailing_bytes(self.raw)

        bpp = CHANNELS[header.colour_type]
        stride = header.width * bpp
        pixel_stream = zlib.decompress(join_idat(self.chunks))
        self.pixels, self.filters = unfilter(pixel_stream, header.height, stride, bpp)
        self.loaded = True

    @staticmethod
    def check_supported(header: Header) -> None:
        """Refuse anything Phase 1 cannot write back correctly, instead of guessing."""
        if header.bit_depth != SUPPORTED_BIT_DEPTH:
            raise UnsupportedCarrierError(
                f"PNG bit depth {header.bit_depth} is not supported, only "
                f"{SUPPORTED_BIT_DEPTH} bits per sample."
            )
        if header.colour_type == PALETTE_COLOUR_TYPE:
            # Supporting these later also means keeping PLTE, tRNS, bKGD, sBIT and hIST
            # consistent with any change, since all of them are read against the palette.
            raise UnsupportedCarrierError(
                "Palette PNGs are not supported: the samples are palette indices, so moving "
                "one changes the colour outright instead of nudging it."
            )
        if header.colour_type not in CHANNELS:
            raise UnsupportedCarrierError(f"Unknown PNG colour type {header.colour_type}")
        if header.interlace:
            raise UnsupportedCarrierError(
                "Interlaced PNGs are not supported: Adam7 spreads each row across seven passes."
            )

    def planes(self) -> list[Plane]:
        self.require_loaded()
        mask = build_changeable_mask(self.pixels, SPATIAL_DOMAIN)
        colour_type = self.header.colour_type if self.header else 0
        # Rows hold interleaved samples, so a cost model must know how many channels are
        # woven together before it filters anything across a row.
        meta = {"colour_type": colour_type, "channels": CHANNELS.get(colour_type, 1)}
        return [Plane(self.pixels, mask, meta)]

    def apply(self, planes: list[Plane]) -> None:
        self.require_loaded()
        if len(planes) != 1:
            raise ValueError(f"PNG has one plane, got {len(planes)}")
        self.pixels = planes[0].values.astype(np.uint8)
        self.modified = True

    def save(self, destination: Path) -> None:
        self.require_loaded()
        Path(destination).write_bytes(self.raw if not self.modified else self.rebuild())

    def rebuild(self) -> bytes:
        """Rebuild the file with a new pixel stream, keeping every other chunk in place."""
        if self.header is None:
            raise RuntimeError("rebuild() called before load()")

        bpp = CHANNELS[self.header.colour_type]
        compressed = zlib.compress(refilter(self.pixels, self.filters, bpp), level=9)

        rebuilt: list[Chunk] = []
        written = False
        for chunk in self.chunks:
            if chunk.type == IDAT:
                # One IDAT replaces however many the original had.
                if not written:
                    rebuilt.append(Chunk(IDAT, compressed))
                    written = True
                continue
            rebuilt.append(chunk)

        return build_png(rebuilt) + self.trailing

    def fingerprint(self) -> bytes:
        self.require_loaded()
        if self.header is None:
            raise RuntimeError("fingerprint() called before load()")
        return self.hash_fields(
            b"png",
            struct.pack(">I", self.header.width),
            struct.pack(">I", self.header.height),
            bytes([self.header.bit_depth, self.header.colour_type, self.header.interlace]),
            self.filters.tobytes(),
        )

    def capacity_base(self) -> int:
        self.require_loaded()
        return int(self.pixels.size)


__all__ = ["CHANNELS", "PngCarrier", "paeth", "refilter", "unfilter"]
