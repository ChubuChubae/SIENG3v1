"""domain: Plane, the changeable mask, the secret order, and capacity maths."""

import numpy as np
import pytest

from sieng.common.errors import CapacityError
from sieng.common.types import BLOCK_SIZE
from sieng.domain.capacity import (
    HEADER_BITS,
    bits_from_bpnzac,
    bpnzac_from_bits,
    check_capacity,
    max_payload_bits,
)
from sieng.domain.plane import Plane
from sieng.domain.selection import (
    build_changeable_mask,
    count_nonzero_ac,
    inverse_permute,
    permute,
)

SEED = bytes(range(32))


def dct_block_grid(blocks=4):
    """A small DCT plane with predictable content: every element set to its flat index."""
    size = blocks * BLOCK_SIZE
    return np.arange(size * size, dtype=np.int16).reshape(size, size)


# ---- Plane -----------------------------------------------------------------


def test_rejects_a_mask_of_the_wrong_shape():
    with pytest.raises(ValueError, match="shape mismatch"):
        Plane(np.zeros((4, 4), np.int16), np.ones((4, 5), bool))


def test_rejects_a_non_boolean_mask():
    with pytest.raises(ValueError, match="boolean mask"):
        Plane(np.zeros((4, 4), np.int16), np.ones((4, 4), np.int8))


def test_counts_only_changeable_elements():
    mask = np.zeros((4, 4), bool)
    mask[0, :3] = True

    assert Plane(np.zeros((4, 4), np.int16), mask).n_changeable() == 3


def test_flatten_returns_only_changeable_values():
    values = np.arange(16, dtype=np.int16).reshape(4, 4)
    mask = np.zeros((4, 4), bool)
    mask[1, 1] = mask[2, 3] = True

    flat, index = Plane(values, mask).flatten()

    assert list(flat) == [5, 11]
    assert list(index) == [5, 11]


def test_flatten_unflatten_roundtrip():
    values = np.arange(64, dtype=np.int16).reshape(8, 8)
    mask = values % 3 == 0
    plane = Plane(values.copy(), mask)

    flat, index = plane.flatten()
    plane.unflatten(flat + 1, index)

    assert np.array_equal(plane.values[mask], values[mask] + 1)
    assert np.array_equal(plane.values[~mask], values[~mask])


def test_unflatten_rejects_a_length_mismatch():
    plane = Plane(np.zeros((4, 4), np.int16), np.ones((4, 4), bool))
    _, index = plane.flatten()

    with pytest.raises(ValueError, match="Cannot unflatten"):
        plane.unflatten(np.zeros(3, np.int16), index)


def test_copy_is_independent():
    plane = Plane(np.zeros((4, 4), np.int16), np.ones((4, 4), bool), {"qtable": [1]})

    other = plane.copy()
    other.values[0, 0] = 99
    other.meta["qtable"] = [2]

    assert plane.values[0, 0] == 0
    assert plane.meta["qtable"] == [1]


# ---- changeable mask -------------------------------------------------------


def test_spatial_lets_everything_move():
    assert build_changeable_mask(np.zeros((5, 7), np.uint8), "spatial").all()


def test_dc_is_never_changeable():
    """Moving a DC coefficient shifts the brightness of a whole block, which is visible."""
    mask = build_changeable_mask(dct_block_grid(), "dct")

    assert not mask[::BLOCK_SIZE, ::BLOCK_SIZE].any()


def test_zero_coefficients_are_wet():
    values = dct_block_grid()
    values[1, 1] = 0

    assert not build_changeable_mask(values, "dct")[1, 1]


def test_skip_dc_can_be_turned_off_for_analysis():
    values = dct_block_grid()
    values[0, 0] = 5

    assert build_changeable_mask(values, "dct", skip_dc=False)[0, 0]


def test_rejects_a_grid_that_is_not_whole_blocks():
    with pytest.raises(ValueError, match="whole number"):
        build_changeable_mask(np.ones((10, 10), np.int16), "dct")


def test_rejects_an_unknown_domain():
    with pytest.raises(ValueError, match="Unknown domain"):
        build_changeable_mask(np.ones((8, 8), np.int16), "audio")


def test_count_nonzero_ac_matches_the_mask():
    values = dct_block_grid()

    assert count_nonzero_ac(values) == int(build_changeable_mask(values, "dct").sum())


# ---- secret order ----------------------------------------------------------


def test_permutation_contains_every_index_once():
    order = permute(1000, SEED)

    assert sorted(order) == list(range(1000))


def test_same_seed_gives_the_same_order():
    assert np.array_equal(permute(500, SEED), permute(500, SEED))


def test_different_seeds_give_different_orders():
    other = bytes(range(1, 33))

    assert not np.array_equal(permute(500, SEED), permute(500, other))


def test_permute_is_deterministic_across_platforms():
    """Pinned value. A change here breaks every stego file ever produced.

    The order comes from argsort over a SHAKE256 keystream, so it must not depend on
    the numpy version, the platform, or the byte order of the machine.
    """
    assert list(permute(8, SEED)) == [1, 0, 2, 4, 7, 5, 6, 3]


def test_inverse_permute_undoes_permute():
    order = permute(300, SEED)
    values = np.arange(300)

    assert np.array_equal(values[order][inverse_permute(order)], values)


def test_permuting_nothing_is_allowed():
    assert permute(0, SEED).size == 0


def test_rejects_a_negative_size():
    with pytest.raises(ValueError, match="Cannot permute"):
        permute(-1, SEED)


# ---- capacity --------------------------------------------------------------


@pytest.mark.parametrize(
    ("rate", "nnz", "expected"),
    [(0.05, 26000, 1300), (0.1, 26000, 2600), (0.2, 26000, 5200), (0.4, 26000, 10400)],
)
def test_the_four_research_payload_rates(rate, nnz, expected):
    assert bits_from_bpnzac(rate, nnz) == expected


def test_rate_and_bits_are_inverses():
    assert bpnzac_from_bits(bits_from_bpnzac(0.1, 26000), 26000) == pytest.approx(0.1)


def test_rejects_a_non_positive_rate():
    with pytest.raises(ValueError, match="must be positive"):
        bits_from_bpnzac(0, 26000)


def test_rejects_a_carrier_with_nothing_to_embed_in():
    with pytest.raises(ValueError, match="nothing to embed in"):
        bpnzac_from_bits(100, 0)


def test_ceiling_leaves_room_for_the_header():
    assert max_payload_bits(26000) == 13000 - HEADER_BITS


def test_a_tiny_carrier_has_no_room_at_all():
    assert max_payload_bits(10) == 0


def test_check_capacity_passes_a_payload_that_fits():
    assert check_capacity(2600, 26000) > 2600


def test_check_capacity_fails_closed_with_the_real_ceiling():
    """Refusing before the cost model runs saves seconds of work on a large image."""
    with pytest.raises(CapacityError) as error:
        check_capacity(20000, 26000)

    assert error.value.max_bits == 13000 - HEADER_BITS
    assert error.value.requested_bits == 20000
