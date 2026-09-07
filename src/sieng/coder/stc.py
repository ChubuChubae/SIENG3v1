"""Syndrome-Trellis Codes: pick which coefficients to nudge, as cheaply as possible.

Given a cost for changing each coefficient and a message to hide, this finds the set of
changes with the lowest total cost that still produces the right syndrome. It is what
turns a good cost model into a good stego image: J-UNIWARD says where changes are cheap,
STC arranges for the changes to land there.

The layer knows nothing about images or crypto. It sees an array, two cost arrays and a
bit string.

Reference implementation. Correct and slow, at O(n * 2**h) time and memory. The C kernel
in _native must produce identical output bit for bit, and this is what proves it does.
"""

import numpy as np

from sieng.coder.base import (
    DEFAULT_HEIGHT,
    build_h_hat,
    flip_costs,
    parity_of,
)
from sieng.common.errors import CapacityError
from sieng.domain.plane import Array

# The forward pass keeps one bit per state per column, so a segment costs
# columns * 2**height / 8 bytes. Beyond this the machine starts swapping and the run
# effectively hangs, so refuse with advice instead.
MAX_TRELLIS_BYTES = 2 * 1024**3

# How many coefficients one trellis segment covers, so that memory depends on the segment
# rather than on the image.
#
# **Not part of the file format.** The segments produce the same answer the whole trellis
# would have (see _solve), the receiver never learns they existed, and extract() is
# untouched. Changing this number costs time and memory and nothing else.
#
# 65,536 columns is 8 MB per segment at the default height of 10, which leaves a 24
# megapixel photo as steady as a thumbnail.
SEGMENT_COLUMNS = 65_536


def segment_bits(width: int, height: int, n_bits: int) -> int:
    """How many message bits one segment carries. At least one block, never more than all."""
    per_segment = max(1, SEGMENT_COLUMNS // max(width, 1))
    return min(per_segment, n_bits)


def usable_length(n_values: int, n_bits: int) -> tuple[int, int]:
    """How wide each block is, and how many coefficients that actually uses.

    Each message bit gets one block of w columns. Anything past m*w is left untouched,
    which is the standard way to handle a cover that is not an exact multiple.
    """
    if n_bits <= 0:
        raise ValueError(f"Nothing to embed: {n_bits} bits")
    width = n_values // n_bits
    if width < 1:
        raise CapacityError(
            requested_bits=n_bits,
            max_bits=n_values,
            max_bpnzac=1.0,
        )
    return width, width * n_bits


def embed(
    values: Array,
    rho_p1: Array,
    rho_m1: Array,
    bits: Array,
    height: int = DEFAULT_HEIGHT,
) -> Array:
    """Return a copy of values carrying the message, changed as little as possible.

    Raises CapacityError when the message cannot be carried at all, which happens when
    it is longer than the cover or when a block has no affordable change left in it.
    """
    values = np.asarray(values)
    bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
    n_bits = int(bits.size)
    if n_bits == 0:
        return values.copy()

    width, usable = usable_length(int(values.size), n_bits)
    states = 1 << height
    per_segment = segment_bits(width, height, n_bits)
    segment_columns = per_segment * width
    if segment_columns * states // 8 > MAX_TRELLIS_BYTES:
        raise ValueError(
            f"One trellis segment of {segment_columns} columns at height {height} needs "
            f"{segment_columns * states / 8 / 1024**3:.1f} GiB. Lower the constraint "
            f"height, or send a larger message so each bit spans fewer coefficients."
        )

    cost, direction = flip_costs(values, rho_p1, rho_m1)
    parity = parity_of(values)
    h_hat = build_h_hat(height, width)

    chosen = _solve(parity[:usable], cost[:usable], bits, h_hat, height, width, states)

    result: Array = values.copy()
    flip = chosen != parity[:usable]
    result[:usable][flip] += direction[:usable][flip]

    # Cheap next to the trellis, and it catches a wrong H matrix or an off by one in the
    # backtrack immediately rather than at extraction time on the receiver's machine.
    if not np.array_equal(extract(result, n_bits, height), bits):
        raise RuntimeError(
            "STC produced a cover that does not extract back to the message. "
            "This is a bug in the coder, not a bad input."
        )
    return result


def _forward(
    parity: Array,
    cost: Array,
    bits: Array,
    xor_table: list[Array],
    width: int,
    weight: Array,
    keep_path: bool,
) -> tuple[Array, Array | None]:
    """Run the trellis over one stretch of columns, from a starting weight vector.

    Called twice per segment: once to find out where the segment ends up, then again to
    redo it with the decisions recorded. That is the whole trick for keeping memory flat.
    """
    states = weight.size
    path = np.zeros((parity.size, states // 8), dtype=np.uint8) if keep_path else None

    column_index = 0
    for block in range(int(bits.size)):
        for offset in range(width):
            change = float(cost[column_index])
            carries_one = bool(parity[column_index])
            # Leaving the column alone costs nothing unless it already carries a one and
            # the path wants a zero here, and the other way round.
            keep = weight + (change if carries_one else 0.0)
            flip = weight[xor_table[offset]] + (0.0 if carries_one else change)
            take_one = flip < keep
            if path is not None:
                # One bit per state, not one byte. The decision is a single bit, and over
                # a photo's worth of coefficients at 2**10 states the difference is
                # gigabytes.
                path[column_index] = np.packbits(take_one)
            weight = np.where(take_one, flip, keep)
            column_index += 1

        # Only the paths whose syndrome bit already matches survive, then the register
        # shifts down and the top half becomes unreachable.
        half = states >> 1
        weight = np.concatenate([weight[int(bits[block]) :: 2], np.full(half, np.inf)])

    return weight, path


def _backtrack(
    path: Array,
    bits: Array,
    h_hat: Array,
    width: int,
    end_state: int,
) -> tuple[Array, int]:
    """Walk the recorded decisions backwards. Returns the choices and the state it began in.

    The state it began in is what the previous segment has to end in, which is how the
    segments join up without any of them being terminated.
    """
    chosen = np.zeros(path.shape[0], dtype=np.uint8)
    state = end_state
    column_index = chosen.size - 1
    for block in range(int(bits.size) - 1, -1, -1):
        state = 2 * state + int(bits[block])
        for offset in range(width - 1, -1, -1):
            # The packed bit for this state. packbits is big-endian within each byte.
            takes_one = bool(path[column_index][state >> 3] >> (7 - (state & 7)) & 1)
            chosen[column_index] = takes_one
            if takes_one:
                state ^= int(h_hat[offset])
            column_index -= 1
    return chosen, state


def _solve(
    parity: Array,
    cost: Array,
    bits: Array,
    h_hat: Array,
    height: int,
    width: int,
    states: int,
) -> Array:
    """The lowest cost set of changes, found without ever holding the whole trellis.

    The obvious implementation keeps one decision per state per column for the entire
    image, which is gigabytes on a real photograph and was the reason a normal JPEG could
    not be used as a cover at all.

    So the columns are cut into segments. The forward pass runs over all of them keeping
    only the weight vector at each boundary, which is kilobytes; then each segment is
    redone, one at a time, with its decisions recorded and immediately backtracked. The
    state a segment starts in is the state the one before it has to end in, so the joins
    need nothing stored in the file and no segment is terminated early.

    **The answer is the same one the whole-image trellis would have given**, bit for bit.
    Nothing is approximated here, only recomputed: the cost is one extra forward pass.
    """
    n_bits = int(bits.size)
    all_states = np.arange(states, dtype=np.int64)
    xor_table = [all_states ^ int(column) for column in h_hat]
    per_segment = segment_bits(width, height, n_bits)
    starts = list(range(0, n_bits, per_segment))

    weight = np.full(states, np.inf, dtype=np.float64)
    weight[0] = 0.0
    entry_weights: list[Array] = []
    for start_bit in starts:
        entry_weights.append(weight)
        stop_bit = min(start_bit + per_segment, n_bits)
        weight, _ = _forward(
            parity[start_bit * width : stop_bit * width],
            cost[start_bit * width : stop_bit * width],
            bits[start_bit:stop_bit],
            xor_table,
            width,
            weight,
            keep_path=False,
        )

    state = int(np.argmin(weight))
    if not np.isfinite(weight[state]):
        # Every surviving path costs infinity, so some block had no affordable change in
        # it. Too much of the cover is wet for this payload, not merely expensive.
        movable = int(np.isfinite(cost).sum())
        raise CapacityError(
            requested_bits=n_bits,
            max_bits=movable,
            max_bpnzac=movable / max(cost.size, 1),
        )

    chosen = np.zeros(parity.size, dtype=np.uint8)
    for index in range(len(starts) - 1, -1, -1):
        start_bit = starts[index]
        stop_bit = min(start_bit + per_segment, n_bits)
        start, stop = start_bit * width, stop_bit * width
        _, path = _forward(
            parity[start:stop],
            cost[start:stop],
            bits[start_bit:stop_bit],
            xor_table,
            width,
            entry_weights[index],
            keep_path=True,
        )
        assert path is not None
        chosen[start:stop], state = _backtrack(
            path, bits[start_bit:stop_bit], h_hat, width, state
        )
    return chosen


def extract(values: Array, n_bits: int, height: int = DEFAULT_HEIGHT) -> Array:
    """Read the message back. Just a matrix product, so far cheaper than embedding."""
    values = np.asarray(values)
    width, usable = usable_length(int(values.size), n_bits)
    h_hat = build_h_hat(height, width)

    parity = parity_of(values[:usable]).reshape(n_bits, width)
    contributions = np.where(parity.astype(bool), h_hat[None, :], 0)
    block_xor = np.bitwise_xor.reduce(contributions, axis=1)

    out = np.zeros(n_bits, dtype=np.uint8)
    state = 0
    for block in range(n_bits):
        state ^= int(block_xor[block])
        out[block] = state & 1
        state >>= 1
    return out


def distortion(values: Array, stego: Array, rho_p1: Array, rho_m1: Array) -> float:
    """Total cost actually paid. Compared against the simulator to measure coding loss."""
    delta = np.asarray(stego).astype(np.int64) - np.asarray(values).astype(np.int64)
    paid = np.where(delta > 0, rho_p1, np.where(delta < 0, rho_m1, 0.0))
    return float(np.sum(paid[np.isfinite(paid)]))
