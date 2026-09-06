"""HILL: the spatial cost model, for PNG.

Three filters, in this order, and the reasoning is worth keeping in mind:

    high pass    find where the image is not smooth
    3x3 average  a single noisy pixel is not a texture, so blur the answer a little
    15x15 average spread it wider still, so a change never lands on an isolated
                 cheap pixel with expensive ones all around it

Cost is the reciprocal, so a large filtered response means a cheap pixel.

The last step is what the name is about: low complexity, and the *lowest* value of the
neighbourhood wins, which pushes changes into the middle of textured regions rather than
onto the sharp edges that a residual based detector looks at first.

Note the tier. PNG is lossless so the file survives, but a spatial LSB style change is a
much weaker hiding place than a DCT one, and the security tier on the carrier says so.
"""

from typing import ClassVar

import numpy as np

from sieng.common.types import SPATIAL_DOMAIN, Domain
from sieng.cost import wavelet
from sieng.cost.base import CostModel
from sieng.domain.plane import Array, Plane

# The KB high pass kernel, as published. Separable into the same 1-D filter both ways.
KB_1D = np.array([-1.0, 2.0, -1.0])

FIRST_AVERAGE = 3
SECOND_AVERAGE = 15


class HillCost(CostModel):
    """High-pass, Low-pass, Low-pass. For 8 bit spatial planes."""

    name: ClassVar[str] = "hill"
    domain: ClassVar[Domain] = SPATIAL_DOMAIN

    def compute(self, plane: Plane) -> tuple[Array, Array]:
        channels = int(plane.meta.get("channels", 1))
        rho = np.empty(plane.values.shape, dtype=np.float64)

        # Samples are interleaved along each row, so every channel is filtered on its own.
        # Filtering across them would compare a red value with the green next to it.
        for channel in range(channels):
            view = np.asarray(plane.values[:, channel::channels], dtype=np.float64)
            rho[:, channel::channels] = channel_cost(view)
        return rho, rho


def channel_cost(image: Array) -> Array:
    """The HILL cost of one 2-D channel. Large filter response gives small cost."""
    residual = np.abs(mirror_filter(image, KB_1D, KB_1D))
    smoothed = mirror_filter(residual, box(FIRST_AVERAGE), box(FIRST_AVERAGE))
    spread = mirror_filter(smoothed, box(SECOND_AVERAGE), box(SECOND_AVERAGE))
    with np.errstate(divide="ignore"):
        return 1.0 / spread


def box(size: int) -> Array:
    """A 1-D averaging filter. Two of them make the square average of the paper."""
    return np.full(size, 1.0 / size)


def mirror_filter(image: Array, col_filter: Array, row_filter: Array) -> Array:
    """Separable filtering with mirrored borders, keeping the image size.

    Mirroring matters here: zero padding would make every border pixel look like a strong
    edge, and the border would then be the cheapest part of the image.
    """
    pad = max(col_filter.size, row_filter.size)
    padded = np.pad(image, pad, mode="symmetric")
    filtered = wavelet.convolve2_same(padded, col_filter, row_filter)
    return filtered[pad:-pad, pad:-pad]
