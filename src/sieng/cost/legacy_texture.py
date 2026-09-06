"""The cost model the old LSB-PP project used, kept only so its results stay comparable.

Two signals, both computed on pixels: how fast brightness changes, and how varied the
neighbourhood is. Where both are high the pixel is called safe.

This is here for one reason. Every earlier result was produced with this scoring, and
throwing it away would leave the new numbers with nothing to be measured against. It is
not a candidate for real use: modern detectors are trained on residuals of exactly this
kind, so a model built from them scores a pixel with the same tool that will convict it.

Do not extend this file. If a spatial model is wanted, hill.py is the one to improve.
"""

from typing import ClassVar

import numpy as np

from sieng.common.types import SPATIAL_DOMAIN, Domain
from sieng.cost.base import CostModel
from sieng.cost.hill import box, mirror_filter
from sieng.domain.plane import Array, Plane

# Neighbourhood the entropy is measured over. Small enough to follow real texture.
ENTROPY_WINDOW = 9

# 8 bit values are grouped into this many bins first. A 9x9 window holds 81 samples, so
# counting 256 separate levels would measure sampling noise rather than texture.
ENTROPY_BINS = 32

# Keeps the reciprocal finite where the image is perfectly flat.
FLOOR = 1e-3


class LegacyTextureCost(CostModel):
    """Gradient magnitude combined with local entropy. Baseline only."""

    name: ClassVar[str] = "legacy_texture"
    domain: ClassVar[Domain] = SPATIAL_DOMAIN

    def compute(self, plane: Plane) -> tuple[Array, Array]:
        channels = int(plane.meta.get("channels", 1))
        rho = np.empty(plane.values.shape, dtype=np.float64)
        # Interleaved samples again, so each channel is scored on its own.
        for channel in range(channels):
            view = np.asarray(plane.values[:, channel::channels], dtype=np.float64)
            rho[:, channel::channels] = channel_cost(view)
        return rho, rho


def channel_cost(image: Array) -> Array:
    """Cost of one 2-D channel. Busy and varied is cheap, flat and uniform is expensive."""
    texture = normalise(gradient_magnitude(image)) * normalise(local_entropy(image))
    return 1.0 / (texture + FLOOR)


def gradient_magnitude(image: Array) -> Array:
    """How fast brightness changes at each pixel, taken as the larger of the two directions."""
    down = np.abs(np.diff(image, axis=0, append=image[-1:, :]))
    across = np.abs(np.diff(image, axis=1, append=image[:, -1:]))
    return np.maximum(down, across)


def local_entropy(image: Array, window: int = ENTROPY_WINDOW, bins: int = ENTROPY_BINS) -> Array:
    """Shannon entropy of the values around each pixel, in bits.

    Computed as one box filter per bin over a membership map, rather than a loop over
    windows. That is the only reason this runs at a usable speed on a real image.
    """
    width = 256 // bins
    binned = np.clip(np.rint(image), 0, 255).astype(np.int64) // width
    entropy = np.zeros(image.shape, dtype=np.float64)
    for value in range(bins):
        share = mirror_filter((binned == value).astype(np.float64), box(window), box(window))
        positive = share > 0
        entropy -= np.where(positive, share * np.log2(np.where(positive, share, 1.0)), 0.0)
    return entropy


def normalise(values: Array) -> Array:
    """Scale to 0..1 so the two signals can be multiplied without one drowning the other."""
    top = float(np.max(values))
    return values / top if top > 0 else np.zeros_like(values)
