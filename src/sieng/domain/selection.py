"""Which elements may be changed, and in what secret order they are visited.

The order is the selection channel. Without it an examiner knows exactly which
coefficients to look at first, which makes their job much easier. It comes from
seed_sel, which is derived per message, so every file gets a different order and
what an examiner learns from one image does not carry to the next.
"""

import hashlib

import numpy as np

from sieng.common.types import BLOCK_SIZE, DCT_DOMAIN, SPATIAL_DOMAIN
from sieng.domain.plane import Array, BoolArray, IndexArray

# 8 bytes of sort key per element. Collisions are what would make two orders differ,
# and at 64 bits the chance is around 6e-8 even for a 1.5 megapixel plane.
KEY_BYTES = 8
KEY_DTYPE = np.dtype(">u8")


def build_changeable_mask(
    values: Array, domain: str, *, skip_dc: bool = True, block: int = BLOCK_SIZE
) -> BoolArray:
    """Return the boolean mask of elements that may be modified.

    DCT: only non-zero AC coefficients. Zero coefficients are wet because moving one to
    1 is both very visible statistically and would change the entropy coded length.
    The DC coefficient shifts the average brightness of a whole 8x8 block, which is
    visible to the eye, so it is excluded. This is also why the payload unit is bpnzAC.

    Spatial: everything is changeable.
    """
    if domain == SPATIAL_DOMAIN:
        return np.ones(values.shape, dtype=np.bool_)

    if domain != DCT_DOMAIN:
        raise ValueError(
            f"Unknown domain '{domain}': expected '{DCT_DOMAIN}' or '{SPATIAL_DOMAIN}'"
        )

    if values.ndim != 2:
        raise ValueError(f"DCT planes must be 2-D block grids, got {values.ndim} dimensions")
    if values.shape[0] % block or values.shape[1] % block:
        raise ValueError(
            f"DCT plane {values.shape} is not a whole number of {block}x{block} blocks"
        )

    mask: BoolArray = values != 0
    if skip_dc:
        mask[::block, ::block] = False
    return mask


def permute(n: int, seed: bytes) -> IndexArray:
    """Return a secret visit order of 0..n-1, the same on every platform and version.

    Implemented as argsort over a SHAKE256 keystream rather than a shuffle from
    numpy.random, because numpy gives no cross version guarantee for Generator methods
    and this order has to stay reproducible for as long as any stego file exists.
    The algorithm lives here, in our code, where we control it.
    """
    if n < 0:
        raise ValueError(f"Cannot permute {n} elements")
    if n == 0:
        return np.empty(0, dtype=np.int64)

    stream = hashlib.shake_256(seed).digest(n * KEY_BYTES)
    keys = np.frombuffer(stream, dtype=KEY_DTYPE)
    order: IndexArray = np.argsort(keys, kind="stable").astype(np.int64)
    return order


def inverse_permute(order: IndexArray) -> IndexArray:
    """Return the index that undoes permute(), so extraction can walk back."""
    inverse: IndexArray = np.empty_like(order)
    inverse[order] = np.arange(order.size, dtype=order.dtype)
    return inverse


def count_nonzero_ac(values: Array, *, block: int = BLOCK_SIZE) -> int:
    """Count non-zero AC coefficients. This is the denominator of bpnzAC."""
    return int(np.count_nonzero(build_changeable_mask(values, DCT_DOMAIN, block=block)))
