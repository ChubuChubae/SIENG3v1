"""A DCT carrier backed by a plain file, for testing the pipeline without jpeglib.

The engine tests need a carrier that produces quantised DCT planes. Using a real JPEG
means every one of them is skipped wherever jpeglib is not installed, and a skipped test
is a test that does not exist. This carrier stores its coefficients directly, so the
pipeline can be exercised anywhere.

It is not a substitute for the real thing and does not pretend to be. What it proves is
that the engine assembles the layers correctly; what it cannot prove is that a JPEG comes
out byte identical, which is `tests/integration/test_embed_roundtrip.py` with a real file.
Both are needed, and neither replaces the other.

Lives in tests/ rather than src/, so there is no path by which it reaches a real user.
"""

from pathlib import Path

import numpy as np

from sieng.carrier.base import Carrier
from sieng.common.types import DCT_DOMAIN, STRONG_TIER
from sieng.cost import _dct
from sieng.domain.plane import Plane
from sieng.domain.selection import build_changeable_mask

MAGIC = b"FAKEDCT\x00"
QUANT = np.full((8, 8), 4.0)


class FakeDctCarrier(Carrier):
    """Quantised DCT coefficients in a file, with no entropy coding in the way."""

    suffixes = (".fakedct",)
    magic = (MAGIC,)
    domain = DCT_DOMAIN
    lossless_roundtrip = True
    security_tier = STRONG_TIER

    def __init__(self, path):
        super().__init__(path)
        self.grid = np.zeros((0, 0), dtype=np.int16)

    def load(self):
        raw = self.path.read_bytes()
        size = int.from_bytes(raw[8:12], "big")
        self.grid = np.frombuffer(raw[12:], dtype=np.int16).reshape(size, size).copy()
        self.loaded = True

    def planes(self):
        self.require_loaded()
        mask = build_changeable_mask(self.grid, DCT_DOMAIN)
        return [Plane(self.grid, mask, {"quant_table": QUANT, "component_index": 0})]

    def apply(self, planes):
        self.require_loaded()
        self.grid = planes[0].values.astype(np.int16)

    def save(self, destination):
        self.require_loaded()
        Path(destination).write_bytes(_pack(self.grid))

    def fingerprint(self):
        """Only what embedding does not change, same rule as the real carriers."""
        self.require_loaded()
        return self.hash_fields(
            b"fakedct",
            QUANT.astype(np.uint16).tobytes(),
            self.grid.shape[0].to_bytes(4, "big"),
        )

    def capacity_base(self):
        self.require_loaded()
        return int(np.count_nonzero(build_changeable_mask(self.grid, DCT_DOMAIN)))


def write_cover(path, size=256, seed=1):
    """A cover with a smooth half and a textured half, like the other fixtures."""
    rng = np.random.default_rng(seed)
    columns = np.arange(size)
    image = 128 + 40 * np.sin(2 * np.pi * columns[None, :] / 90) * np.ones((size, 1))
    image[:, size // 2 :] += rng.normal(0, 35, (size, size // 2))

    blocks = _dct.as_blocks(image - _dct.LEVEL_SHIFT)
    coefficients = np.einsum("ix,rcxy,jy->rcij", _dct.DCT, blocks, _dct.DCT)
    grid = np.round(coefficients / QUANT).astype(np.int16).swapaxes(1, 2).reshape(size, size)
    Path(path).write_bytes(_pack(grid))
    return Path(path)


def _pack(grid):
    return MAGIC + grid.shape[0].to_bytes(4, "big") + grid.tobytes()
