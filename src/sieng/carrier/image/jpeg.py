"""JPEG carrier: quantised DCT coefficients, never decompressed to pixels.

The whole project rests on one rule here. Coefficients go in and out exactly as libjpeg
stored them, and the file is rebuilt from the original's own headers. Anything that
decodes to pixels and re-encodes leaves double compression traces, and DCTR and GFR find
those with nothing embedded at all.
"""

import struct
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from sieng.carrier.base import Carrier
from sieng.carrier.image._jpeg_codec import (
    BLOCK,
    blocks_to_grid,
    encode_to_bytes,
    grid_to_blocks,
    read_dct,
    splice,
)
from sieng.common.errors import UnsupportedCarrierError
from sieng.common.types import DCT_DOMAIN, STRONG_TIER, Domain, SecurityTier
from sieng.domain.plane import Array, Plane
from sieng.domain.selection import build_changeable_mask

JPEG_MAGIC = b"\xff\xd8\xff"

# Luma first. Chroma planes are usually subsampled, so they hold far fewer coefficients
# and are noisier ground for embedding, but they are still offered.
COMPONENT_NAMES = ("Y", "Cb", "Cr")


class JpegCarrier(Carrier):
    """Baseline JPEG. Coefficients are read and written without ever becoming pixels."""

    suffixes: ClassVar[tuple[str, ...]] = (".jpg", ".jpeg", ".jpe")
    magic: ClassVar[tuple[bytes, ...]] = (JPEG_MAGIC,)
    domain: ClassVar[Domain] = DCT_DOMAIN
    lossless_roundtrip: ClassVar[bool] = True
    security_tier: ClassVar[SecurityTier] = STRONG_TIER

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.raw = b""
        self.dct: Any = None
        self.grids: list[Array] = []
        self.modified = False

    def load(self) -> None:
        self.raw = self.path.read_bytes()
        self.dct = read_dct(self.path)
        self.reject_progressive()
        self.grids = [blocks_to_grid(plane) for plane in self.component_arrays()]
        self.loaded = True

    def reject_progressive(self) -> None:
        """Refuse progressive JPEGs rather than quietly turning them into baseline ones.

        A progressive file stores its coefficients across several scans. jpeglib hands
        them back in the same shape as a baseline file, so nothing looks wrong, but
        writing them out again rebuilds the file as baseline. That changes the structure
        of every byte, which is a far louder signal than any payload.
        """
        if getattr(self.dct, "progressive_mode", False):
            raise UnsupportedCarrierError(
                f"{self.path.name} is a progressive JPEG. Phase 1 handles baseline only, "
                f"because rewriting a progressive file as baseline changes its whole "
                f"structure. Convert it to baseline first if you need to use it."
            )

    def component_arrays(self) -> list[Array]:
        """The coefficient array of each component present, luma first."""
        arrays: list[Array] = []
        for name in COMPONENT_NAMES:
            plane = getattr(self.dct, name, None)
            if plane is not None:
                arrays.append(np.asarray(plane))
        if not arrays:
            raise UnsupportedCarrierError(
                f"{self.path.name} has no Y component, so there is nothing to embed in"
            )
        return arrays

    def planes(self) -> list[Plane]:
        self.require_loaded()
        planes: list[Plane] = []
        for index, grid in enumerate(self.grids):
            mask = build_changeable_mask(grid, DCT_DOMAIN)
            meta = {
                "component": COMPONENT_NAMES[index],
                "component_index": index,
                "block_size": BLOCK,
            }
            planes.append(Plane(grid, mask, meta))
        return planes

    def apply(self, planes: list[Plane]) -> None:
        self.require_loaded()
        if len(planes) != len(self.grids):
            raise ValueError(
                f"This JPEG has {len(self.grids)} components but {len(planes)} planes were given"
            )
        for index, plane in enumerate(planes):
            self.grids[index] = plane.values.astype(np.int16)
        self.modified = True

    def save(self, destination: Path) -> None:
        self.require_loaded()
        destination = Path(destination)

        if not self.modified:
            destination.write_bytes(self.raw)
            return

        for index, name in enumerate(COMPONENT_NAMES[: len(self.grids)]):
            setattr(self.dct, name, grid_to_blocks(self.grids[index]))

        scratch = destination.with_suffix(destination.suffix + ".partial")
        written = encode_to_bytes(self.dct, scratch)
        destination.write_bytes(splice(self.raw, written))

    def fingerprint(self) -> bytes:
        """Everything about the file that embedding does not change.

        The receiver recomputes this from the stego file, so it must exclude the
        coefficients themselves and include only what survives a change to them.
        """
        self.require_loaded()
        qt = np.asarray(self.dct.qt).astype(np.uint16).tobytes()
        samp = np.asarray(getattr(self.dct, "samp_factor", [])).astype(np.int32).tobytes()
        return self.hash_fields(
            b"jpeg",
            qt,
            struct.pack(">I", int(self.dct.width)),
            struct.pack(">I", int(self.dct.height)),
            samp,
            bytes([len(self.grids), int(bool(getattr(self.dct, "progressive_mode", False)))]),
        )

    def capacity_base(self) -> int:
        """Non-zero AC coefficients in the luma plane. This is the denominator of bpnzAC.

        Luma only, because that is what the literature reports and what the payload rates
        in the experiment configs mean.
        """
        self.require_loaded()
        return int(np.count_nonzero(build_changeable_mask(self.grids[0], DCT_DOMAIN)))

    def nnz_ac(self, component: int = 0) -> int:
        """Non-zero AC count for one component, for reporting and for the analyzer."""
        self.require_loaded()
        return int(np.count_nonzero(build_changeable_mask(self.grids[component], DCT_DOMAIN)))

    @property
    def quant_tables(self) -> Array:
        """The quantisation tables, as read. Needed by the cost model."""
        self.require_loaded()
        return np.asarray(self.dct.qt)
