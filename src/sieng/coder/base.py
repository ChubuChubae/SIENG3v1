"""Pieces the syndrome coder needs before any trellis runs.

Two of them are part of the file format and must never drift:

    build_h_hat   defines the parity checks, so a different matrix decodes to garbage
    flip_costs    decides which changes are allowed at all

Changing either one breaks every stego file already produced, so both are pinned by
tests and any change means a new crypto suite (PROJECT_STRUCTURE.md 8.4).
"""

import hashlib

import numpy as np

from sieng.domain.plane import Array, IndexArray

# Constraint height. Higher trades embedding efficiency for exponentially more work,
# and 2**h states have to fit in memory. Matches STC_HEIGHT_RANGE in app.settings.
MIN_HEIGHT = 6
MAX_HEIGHT = 14
DEFAULT_HEIGHT = 10

# Changing a coefficient to zero, or away from zero, moves it in or out of the set that
# build_changeable_mask selects. The receiver builds that set from the stego file, so the
# two sides would disagree about which coefficients carry the message and every bit after
# the first such change would be wrong. Forbidding the move keeps the set identical.
FORBIDDEN = np.inf


def build_h_hat(height: int, width: int) -> IndexArray:
    """The submatrix that defines the trellis, as `width` columns of `height` bits.

    Derived from SHAKE256 so it is identical on every machine and version, the same
    reason permute() does not use numpy.random. Two bits are forced in every column:

        the top bit, so a column can reach the highest state and the trellis stays connected
        the bottom bit, so every column can affect the syndrome bit being decided

    Without those the trellis has states nothing can reach, which quietly costs
    embedding efficiency instead of failing.
    """
    if not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise ValueError(
            f"Constraint height {height} is outside {MIN_HEIGHT}..{MAX_HEIGHT}. "
            f"Lower is faster and weaker, higher costs exponentially more memory and time."
        )
    if width < 1:
        raise ValueError(f"Cannot build a trellis {width} columns wide")

    seed = f"sieng3/stc/v1/h{height}/w{width}".encode()
    stream = np.frombuffer(hashlib.shake_256(seed).digest(width * 8), dtype=">u8")

    top = 1 << (height - 1)
    columns = (stream % top).astype(np.int64)
    return (columns | top | 1).astype(np.int64)


def flip_costs(values: Array, rho_p1: Array, rho_m1: Array) -> tuple[Array, Array]:
    """What it costs to flip each coefficient's parity, and which way to move.

    Flipping the parity means adding or subtracting one, so the cheaper direction wins.
    Both directions are refused when the result would be zero, or when the value already
    is zero, because that changes which coefficients are non-zero. See FORBIDDEN above.
    """
    if not (values.shape == rho_p1.shape == rho_m1.shape):
        raise ValueError(
            f"Cost arrays must match the values: values{values.shape}, "
            f"rho_p1{rho_p1.shape}, rho_m1{rho_m1.shape}"
        )

    up = np.asarray(rho_p1, dtype=np.float64).copy()
    down = np.asarray(rho_m1, dtype=np.float64).copy()

    up[values == -1] = FORBIDDEN
    down[values == 1] = FORBIDDEN
    up[values == 0] = FORBIDDEN
    down[values == 0] = FORBIDDEN

    cost: Array = np.minimum(up, down)
    direction: Array = np.where(up <= down, 1, -1).astype(np.int16)
    return cost, direction


def parity_of(values: Array) -> Array:
    """The bit each coefficient currently carries.

    Two's complement gives the right answer for negatives as well: -3 has parity 1,
    which matches abs(-3) being odd.
    """
    return (np.asarray(values).astype(np.int64) & 1).astype(np.uint8)


def bytes_to_bits(payload: bytes) -> Array:
    """MSB first, matching the bit order the format spec fixes for embedding."""
    return np.unpackbits(np.frombuffer(payload, dtype=np.uint8))


def bits_to_bytes(bits: Array) -> bytes:
    """The inverse. The bit count must be a whole number of bytes."""
    if bits.size % 8:
        raise ValueError(f"{bits.size} bits is not a whole number of bytes")
    return bytes(np.packbits(np.asarray(bits, dtype=np.uint8)))
