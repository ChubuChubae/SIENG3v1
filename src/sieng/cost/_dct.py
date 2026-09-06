"""The 8x8 DCT basis, and what a JPEG block looks like once it is pixels again.

The DCT models need pixels to filter, but the carrier deliberately never decompresses.
So the cost layer does its own decompression, in floating point, with no rounding and no
clipping. That is on purpose: rounding here would add a quantisation step that the real
encoder does not apply at this point, and the cost map would drift from the reference.

Nothing written here ever reaches a file. It exists only to score coefficients.
"""

import numpy as np

from sieng.common.types import BLOCK_SIZE
from sieng.domain.plane import Array

# JPEG shifts samples to be centred on zero before the transform, so undoing it puts them
# back in the 0..255 range. Every filter used here is high pass, so this term cancels, but
# leaving it out would make the intermediate array hard to recognise.
LEVEL_SHIFT = 128.0


def dct_matrix(size: int = BLOCK_SIZE) -> Array:
    """Orthonormal DCT-II matrix. Row k is basis function k, so D @ x transforms a column."""
    k = np.arange(size).reshape(-1, 1)
    x = np.arange(size).reshape(1, -1)
    matrix: Array = np.cos(np.pi * (2 * x + 1) * k / (2 * size)) * np.sqrt(2.0 / size)
    matrix[0] /= np.sqrt(2.0)
    return matrix


DCT = dct_matrix()


def basis_images(size: int = BLOCK_SIZE) -> Array:
    """What changing each of the 64 coefficients by 1 does to the block's pixels.

    Shape (size, size, size, size), indexed [mode_row, mode_col, pixel_row, pixel_col].
    """
    matrix = dct_matrix(size)
    basis: Array = np.einsum("ix,jy->ijxy", matrix, matrix)
    return basis


def as_blocks(grid: Array, block: int = BLOCK_SIZE) -> Array:
    """Split a coefficient grid into (block_rows, block_cols, block, block)."""
    rows, cols = grid.shape
    if rows % block or cols % block:
        raise ValueError(f"Grid {grid.shape} is not a whole number of {block}x{block} blocks")
    return grid.reshape(rows // block, block, cols // block, block).swapaxes(1, 2)


def block_shape(grid: Array, block: int = BLOCK_SIZE) -> tuple[int, int]:
    """How many blocks the grid holds, down and across."""
    return grid.shape[0] // block, grid.shape[1] // block


def to_spatial(grid: Array, quant_table: Array, block: int = BLOCK_SIZE) -> Array:
    """Dequantise and inverse transform a whole plane, without rounding or clipping.

    This is the "jpeg_rec" step the UNIWARD reference performs before filtering.
    """
    blocks = as_blocks(np.asarray(grid, dtype=np.float64), block) * quant_table
    matrix = dct_matrix(block)
    pixels = np.einsum("ix,rcij,jy->rcxy", matrix, blocks, matrix)
    rows, cols = block_shape(grid, block)
    image: Array = pixels.swapaxes(1, 2).reshape(rows * block, cols * block) + LEVEL_SHIFT
    return image
