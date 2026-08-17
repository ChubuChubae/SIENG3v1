"""Properties that must hold for every plane and every seed, not just the ones we picked.

These catch the shapes and sizes nobody thought to write a unit test for. The first
real payload roundtrip lands here in Phase 5 once the coder exists.
"""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from sieng.common.types import BLOCK_SIZE
from sieng.domain.plane import Plane
from sieng.domain.selection import build_changeable_mask, inverse_permute, permute

seeds = st.binary(min_size=32, max_size=32)
sizes = st.integers(min_value=0, max_value=2000)
blocks = st.integers(min_value=1, max_value=6)


@given(n=sizes, seed=seeds)
@settings(max_examples=100)
def test_permute_is_always_a_permutation(n, seed):
    order = permute(n, seed)

    assert order.size == n
    assert np.array_equal(np.sort(order), np.arange(n))


@given(n=st.integers(min_value=1, max_value=2000), seed=seeds)
@settings(max_examples=100)
def test_inverse_always_undoes_the_order(n, seed):
    order = permute(n, seed)
    values = np.arange(n)

    assert np.array_equal(values[order][inverse_permute(order)], values)


@given(n=sizes, seed=seeds)
@settings(max_examples=50)
def test_the_same_seed_always_gives_the_same_order(n, seed):
    assert np.array_equal(permute(n, seed), permute(n, seed))


@given(grid=blocks, fill=st.integers(min_value=-64, max_value=64))
@settings(max_examples=50)
def test_dc_is_never_changeable_at_any_size(grid, fill):
    size = grid * BLOCK_SIZE
    plane_values = np.full((size, size), fill, dtype=np.int16)

    mask = build_changeable_mask(plane_values, "dct")

    assert not mask[::BLOCK_SIZE, ::BLOCK_SIZE].any()


@given(grid=blocks, seed=seeds)
@settings(max_examples=50)
def test_flatten_unflatten_never_touches_wet_elements(grid, seed):
    size = grid * BLOCK_SIZE
    rng = np.random.default_rng(int.from_bytes(seed[:8], "big"))
    values = rng.integers(-32, 32, size=(size, size), dtype=np.int16)
    mask = build_changeable_mask(values, "dct")
    plane = Plane(values.copy(), mask)

    flat, index = plane.flatten()
    plane.unflatten(flat * 0, index)

    assert np.array_equal(plane.values[~mask], values[~mask])
    assert not plane.values[mask].any()
