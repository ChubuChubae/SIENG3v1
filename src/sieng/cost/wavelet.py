"""The Daubechies 8 filter bank UNIWARD measures distortion in.

UNIWARD's idea in one sentence: a change is safe only where the image is already busy in
all three directions at once, because a region that is smooth in any direction makes the
change stand out along that direction. Three directional filters answer that question.

The coefficients below are the published ones. They must not be rounded, reordered or
"cleaned up": a different filter bank gives a different cost map, and then nothing here is
comparable to any published result.

Sizes worth remembering. The 1-D filters have 16 taps, so the 2-D kernels are 16x16, so
changing one 8x8 block reaches 8 + 16 - 1 = 23 wavelet coefficients in each direction.
That 23 is where the window size in juniward.py comes from.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from sieng.domain.plane import Array

# Daubechies 8 high pass decomposition filter, exactly as the UNIWARD reference lists it.
HPDF = np.array(
    [
        -0.0544158422,
        0.3128715909,
        -0.6756307363,
        0.5853546837,
        0.0158291053,
        -0.2840155430,
        -0.0004724846,
        0.1287474266,
        0.0173693010,
        -0.0440882539,
        -0.0139810279,
        0.0087460940,
        0.0048703530,
        -0.0003917404,
        -0.0006754494,
        -0.0001174768,
    ],
    dtype=np.float64,
)

# The quadrature mirror of the above. Reversed, with alternating signs.
LPDF = ((-1.0) ** np.arange(HPDF.size)) * HPDF[::-1]

TAPS = int(HPDF.size)

# The image is extended before filtering so the border does not look like an edge, which
# would otherwise make every border block appear cheap. One kernel width is enough.
PAD = TAPS

# Each 2-D filter is an outer product of two 1-D filters, so every convolution here can be
# done as two cheap 1-D passes instead of one 16x16 one.
#   LH  low  down the columns, high across the rows  -> horizontal detail
#   HL  high down the columns, low  across the rows  -> vertical detail
#   HH  high both ways                               -> diagonal detail
DIRECTIONS = ("LH", "HL", "HH")


def separable_filters() -> list[tuple[Array, Array]]:
    """The three directional filters as (column filter, row filter) pairs."""
    return [(LPDF, HPDF), (HPDF, LPDF), (HPDF, HPDF)]


def daubechies8_filters() -> list[Array]:
    """The three 16x16 kernels themselves. Used by tests and by anything not separable."""
    return [np.outer(col, row) for col, row in separable_filters()]


def _convolve_same(data: Array, kernel: Array, axis: int) -> Array:
    """1-D convolution along one axis, keeping the input length.

    Matches Matlab's conv2 'same': the full result is trimmed to the central part, which
    for an even length kernel starts at taps // 2. Getting this offset wrong shifts the
    whole residual and quietly changes every cost.
    """
    taps = kernel.size
    data = np.moveaxis(data, axis, -1)
    width = np.zeros((data.ndim, 2), dtype=int)
    width[-1] = taps - 1
    padded = np.pad(data, width)
    windows = sliding_window_view(padded, taps, axis=-1)
    full = windows @ kernel[::-1]
    start = taps // 2
    return np.moveaxis(full[..., start : start + data.shape[-1]], -1, axis)


def convolve2_same(image: Array, col_filter: Array, row_filter: Array) -> Array:
    """2-D convolution with a separable kernel, keeping the input size."""
    return _convolve_same(_convolve_same(image, row_filter, axis=1), col_filter, axis=0)


def correlate2_full(image: Array, col_filter: Array, row_filter: Array) -> Array:
    """2-D correlation with a separable kernel, keeping every output position.

    Correlation rather than convolution, and 'full' rather than 'same', because this is
    what the reference uses for the impact table and the two differ by a flip.
    """
    taps = col_filter.size
    width = ((taps - 1, taps - 1), (taps - 1, taps - 1))
    padded = np.pad(np.asarray(image, dtype=np.float64), width)
    rows = sliding_window_view(padded, row_filter.size, axis=1) @ row_filter
    return sliding_window_view(rows, col_filter.size, axis=0) @ col_filter


def residuals(image: Array, pad: int = PAD) -> list[Array]:
    """The three directional residuals of a spatial image, still padded.

    The result keeps the padding so callers can index a window around any pixel without a
    bounds check. Add pad to an image coordinate to get the matching residual coordinate.
    """
    padded = np.pad(np.asarray(image, dtype=np.float64), pad, mode="symmetric")
    return [convolve2_same(padded, col, row) for col, row in separable_filters()]
