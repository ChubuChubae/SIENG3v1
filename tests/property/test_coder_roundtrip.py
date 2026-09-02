"""Properties the trellis must hold for every cover and every payload, not just chosen ones.

Sizes stay small because the trellis is O(n * 2**h) and hypothesis runs many examples.
The realistic sizes are covered once each in the unit tests.
"""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from sieng.coder.base import FORBIDDEN, flip_costs
from sieng.coder.stc import embed, extract

seeds = st.integers(min_value=0, max_value=2**31 - 1)
sizes = st.integers(min_value=64, max_value=600)
heights = st.integers(min_value=6, max_value=8)
rates = st.floats(min_value=0.02, max_value=0.45)


def build(size, seed, wet_every=0):
    """A cover with no zeros, and optionally some coefficients pinned as unmovable."""
    rng = np.random.default_rng(seed)
    values = rng.integers(-30, 30, size).astype(np.int16)
    values[values == 0] = 3
    cost = rng.random(size) * 2 + 0.05
    if wet_every:
        cost[::wet_every] = FORBIDDEN
    return values, cost


@given(size=sizes, seed=seeds, height=heights, rate=rates)
@settings(max_examples=60, deadline=None)
def test_the_message_always_comes_back(size, seed, height, rate):
    values, cost = build(size, seed)
    n_bits = max(1, int(size * rate))
    bits = np.random.default_rng(seed + 1).integers(0, 2, n_bits).astype(np.uint8)

    stego = embed(values, cost, cost, bits, height)

    assert np.array_equal(extract(stego, n_bits, height), bits)


@given(size=sizes, seed=seeds, height=heights, rate=rates)
@settings(max_examples=60, deadline=None)
def test_the_non_zero_set_is_never_disturbed(size, seed, height, rate):
    """Coefficients crossing zero would desynchronise the receiver's selection channel."""
    values, cost = build(size, seed)
    values[::5] = 1
    values[2::5] = -1
    n_bits = max(1, int(size * rate))
    bits = np.random.default_rng(seed + 2).integers(0, 2, n_bits).astype(np.uint8)

    stego = embed(values, cost, cost, bits, height)

    assert np.array_equal(stego != 0, values != 0)


@given(size=sizes, seed=seeds, height=heights)
@settings(max_examples=40, deadline=None)
def test_nothing_ever_moves_by_more_than_one(size, seed, height):
    values, cost = build(size, seed)
    bits = np.random.default_rng(seed + 3).integers(0, 2, max(1, size // 8)).astype(np.uint8)

    stego = embed(values, cost, cost, bits, height)

    assert np.abs(stego.astype(np.int64) - values.astype(np.int64)).max() <= 1


@given(size=sizes, seed=seeds, height=heights)
@settings(max_examples=40, deadline=None)
def test_unmovable_coefficients_stay_put(size, seed, height):
    values, cost = build(size, seed, wet_every=4)
    bits = np.random.default_rng(seed + 4).integers(0, 2, max(1, size // 16)).astype(np.uint8)

    stego = embed(values, cost, cost, bits, height)

    assert np.array_equal(stego[::4], values[::4])


@given(size=sizes, seed=seeds)
@settings(max_examples=40, deadline=None)
def test_the_direction_chosen_is_always_the_cheaper_one(size, seed):
    rng = np.random.default_rng(seed)
    values, _ = build(size, seed)
    up = rng.random(size) * 2 + 0.05
    down = rng.random(size) * 2 + 0.05

    cost, direction = flip_costs(values, up, down)

    picked = np.where(direction > 0, up, down)
    assert np.allclose(cost[np.isfinite(cost)], picked[np.isfinite(cost)])
