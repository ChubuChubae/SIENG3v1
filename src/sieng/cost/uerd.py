"""UERD: spread the damage evenly over the image's own energy.

The idea is simpler than UNIWARD and costs a fraction of the time. Each 8x8 block gets an
energy, taken from its own dequantised AC coefficients plus a quarter of each neighbour's.
A coefficient in a busy block is cheap, and within a block the fine detail coefficients,
which have the largest quantisation steps, are cheaper still.

This is the baseline. Every result for J-UNIWARD is reported next to a UERD run, so a bad
number can be blamed on the cost model rather than on the coder or the pipeline.

Ported from the reference Matlab (vazswk/UERD, J_UERD.m). Two deliberate differences from
it are recorded at the bottom of this file.
"""

from typing import ClassVar

import numpy as np

from sieng.common.types import BLOCK_SIZE, DCT_DOMAIN, Domain
from sieng.cost._dct import as_blocks
from sieng.cost.base import CostModel
from sieng.domain.plane import Array, Plane

# How much of a neighbouring block's energy counts towards this one. The same weight is
# used for the four sides and the four corners, as in the reference.
NEIGHBOUR_WEIGHT = 0.25


class UerdCost(CostModel):
    """Uniform Embedding Revisited Distortion, for quantised DCT planes."""

    name: ClassVar[str] = "uerd"
    domain: ClassVar[Domain] = DCT_DOMAIN

    def __init__(self, block: int = BLOCK_SIZE) -> None:
        self.block = block

    def compute(self, plane: Plane) -> tuple[Array, Array]:
        quant = quant_table_of(plane, self.block)
        energy = block_energy(plane.values, dc_adjusted(quant), self.block)
        spread = spread_energy(energy)

        # Each block's cost pattern is the quantisation table divided by that block's
        # energy: a large step means a coefficient the encoder already treats as noise.
        with np.errstate(divide="ignore", invalid="ignore"):
            per_block = dc_adjusted(quant)[None, None, :, :] / spread[:, :, None, None]
        rho = unblock(per_block, plane.values.shape, self.block)

        finite = rho[np.isfinite(rho) & (rho > 0)]
        if finite.size:
            rho = rho / finite.min()
        return rho, rho


def quant_table_of(plane: Plane, block: int = BLOCK_SIZE) -> Array:
    """The plane's quantisation table, or a clear complaint if the carrier did not attach one."""
    quant = plane.meta.get("quant_table")
    if quant is None:
        raise ValueError(
            "This plane carries no 'quant_table' in its meta, so a DCT cost model cannot "
            "score it. Only a JPEG carrier produces planes these models can use."
        )
    quant = np.asarray(quant, dtype=np.float64)
    if quant.shape != (block, block):
        raise ValueError(f"Quantisation table must be {block}x{block}, got {quant.shape}")
    return quant


def dc_adjusted(quant: Array) -> Array:
    """The table with the DC step replaced by the mean of its two neighbours.

    The real DC step is far larger than any AC step, and using it directly would make the
    DC coefficient look absurdly cheap. The reference substitutes an AC-sized value.
    """
    adjusted = quant.copy()
    adjusted[0, 0] = 0.5 * (quant[1, 0] + quant[0, 1])
    return adjusted


def block_energy(values: Array, quant: Array, block: int = BLOCK_SIZE) -> Array:
    """Total dequantised AC magnitude per block. DC is excluded: it says nothing about texture."""
    blocks = np.abs(as_blocks(np.asarray(values, dtype=np.float64), block) * quant)
    blocks[:, :, 0, 0] = 0.0
    energy: Array = blocks.sum(axis=(2, 3))
    return energy


def spread_energy(energy: Array, weight: float = NEIGHBOUR_WEIGHT) -> Array:
    """Each block's energy plus a share of all eight neighbours'.

    Without this a flat block next to a busy one would look completely wet, and the
    boundary between the two is exactly where an examiner looks first.
    """
    padded = np.pad(energy, 1, mode="symmetric")
    total = energy.copy()
    for row in (0, 1, 2):
        for col in (0, 1, 2):
            if (row, col) != (1, 1):
                total += weight * padded[row : row + energy.shape[0], col : col + energy.shape[1]]
    return total


def unblock(per_block: Array, shape: tuple[int, ...], block: int = BLOCK_SIZE) -> Array:
    """Put a (block_rows, block_cols, block, block) array back into a flat grid."""
    return per_block.swapaxes(1, 2).reshape(shape)


# Two deliberate differences from the reference, both consequences of decisions made in
# earlier phases and both recorded here so nobody "fixes" them later.
#
# 1. The reference lets every coefficient carry, including zeros, so its costs are defined
#    everywhere. Here build_changeable_mask() keeps only non-zero AC, and base.py turns
#    the rest wet. That is what makes bpnzAC the honest unit.
# 2. The reference lets a coefficient cross zero. flip_costs() forbids that, because the
#    receiver rebuilds the changeable set from the stego file and the two sides would
#    disagree. A coefficient of magnitude 1 can therefore only move outwards.
