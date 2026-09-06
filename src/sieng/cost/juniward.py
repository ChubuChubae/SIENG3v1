"""J-UNIWARD: the cost model the whole project is built to serve.

The rule it encodes is short. Changing a coefficient disturbs a patch of the image; score
that disturbance against how busy the image already is there, in three directions at once,
and add the three up. A place that is smooth in any one direction is expensive, because a
change there has nothing to hide behind.

    rho = sum over the three directions of  sum |change in residual| / (sigma + |residual|)

The denominator is why sigma exists: a perfectly flat region has a residual of zero, and
without sigma the cost would be infinite for a reason that is arithmetic rather than real.

Two things make this affordable. The numerator does not depend on the image, so the effect
of each of the 64 coefficient positions is computed once. The denominator does not depend
on which coefficient inside the block moved, so it is computed once per block. What is left
is a matrix product, not a loop over every coefficient.
"""

from typing import ClassVar

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from sieng.common.types import BLOCK_SIZE, DCT_DOMAIN, Domain
from sieng.cost import wavelet
from sieng.cost._dct import basis_images, to_spatial
from sieng.cost.base import CostModel
from sieng.cost.uerd import quant_table_of, unblock
from sieng.domain.plane import Array, Plane

# Sensitivity of the cost to image content, as published. Smaller makes flat regions even
# more expensive relative to busy ones.
SIGMA = 2.0**-6

# One 8x8 block reaches 8 + 16 - 1 wavelet coefficients each way.
WINDOW = BLOCK_SIZE + wavelet.TAPS - 1

# Where a block's window starts inside the padded residual. The published Matlab and C++
# both read from 9, one pixel down and right of the 8 the geometry calls for. The error is
# real and documented (arXiv 2305.19776), and its effect is small, but reproducing it is
# what makes a number here comparable with a published one. See use_reference_offset.
REFERENCE_OFFSET = 9
CORRECTED_OFFSET = 8


class JUniwardCost(CostModel):
    """Universal wavelet relative distortion, evaluated on quantised DCT coefficients."""

    name: ClassVar[str] = "juniward"
    domain: ClassVar[Domain] = DCT_DOMAIN

    def __init__(self, *, use_reference_offset: bool = True, block: int = BLOCK_SIZE) -> None:
        """use_reference_offset keeps the published off-by-one, so results stay comparable.

        Turn it off only in an experiment that says so in its own config, never silently.
        """
        self.block = block
        self.offset = REFERENCE_OFFSET if use_reference_offset else CORRECTED_OFFSET

    def compute(self, plane: Plane) -> tuple[Array, Array]:
        quant = quant_table_of(plane, self.block)
        spatial = to_spatial(plane.values, quant, self.block)
        rho = wavelet_costs(spatial, quant, plane.values.shape, self.offset, self.block)
        # Symmetric by construction: the residual difference is the same size either way,
        # and the formula takes its absolute value.
        return rho, rho


def wavelet_costs(
    spatial: Array,
    quant: Array,
    shape: tuple[int, ...],
    offset: int = REFERENCE_OFFSET,
    block: int = BLOCK_SIZE,
) -> Array:
    """The UNIWARD score of every coefficient position, given the image as pixels.

    Split out from the class because SI-UNIWARD runs exactly this over the precover and
    then reweights the result. Nothing here depends on the coefficients themselves.
    """
    impact = mode_impact(quant, block)
    rows, cols = shape[0] // block, shape[1] // block

    total = np.zeros((rows * cols, block * block), dtype=np.float64)
    for index, residual in enumerate(wavelet.residuals(spatial)):
        windows = block_windows(residual, rows, cols, offset, block)
        sensitivity = 1.0 / (np.abs(windows) + SIGMA)
        total += sensitivity.reshape(rows * cols, -1) @ impact[index].T

    return unblock(total.reshape(rows, cols, block, block), shape, block)


def mode_impact(quant: Array, block: int = BLOCK_SIZE) -> Array:
    """How much changing each of the 64 coefficients by 1 moves each residual.

    Returns shape (3, 64, WINDOW * WINDOW), already absolute, flattened so the main loop
    is a plain matrix product. Depends only on the quantisation table, never on the image.
    """
    spatial = basis_images(block) * quant[:, :, None, None]
    impact = np.empty((3, block * block, WINDOW * WINDOW), dtype=np.float64)
    for index, (col_filter, row_filter) in enumerate(wavelet.separable_filters()):
        for mode in range(block * block):
            patch = spatial[mode // block, mode % block]
            impact[index, mode] = np.abs(
                wavelet.correlate2_full(patch, col_filter, row_filter)
            ).reshape(-1)
    return impact


def block_windows(residual: Array, rows: int, cols: int, offset: int, block: int) -> Array:
    """The WINDOW x WINDOW patch of the residual each block sits in.

    A view, not a copy, until the caller does arithmetic on it.
    """
    windows = sliding_window_view(residual, (WINDOW, WINDOW))
    return windows[offset : offset + rows * block : block, offset : offset + cols * block : block]
