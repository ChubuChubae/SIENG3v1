"""coder: the trellis, the matrix that defines it, and the bound it is measured against.

Sizes here are kept small on purpose. The trellis is O(n * 2**h), so a realistic image at
h=12 belongs in a benchmark, not in a suite that runs on every change.
"""

import tracemalloc

import numpy as np
import pytest

from sieng.coder.base import (
    DEFAULT_HEIGHT,
    FORBIDDEN,
    MAX_HEIGHT,
    MIN_HEIGHT,
    bits_to_bytes,
    build_h_hat,
    bytes_to_bits,
    flip_costs,
    parity_of,
)
from sieng.coder.simulator import (
    binary_bound,
    binary_payload,
    coding_loss,
    simulate_embedding,
    ternary_bound,
    ternary_payload,
)
from sieng.coder import stc
from sieng.coder.stc import distortion, embed, extract, segment_bits, usable_length
from sieng.common.errors import CapacityError

RATES = [0.05, 0.1, 0.2, 0.4]


def cover(size=1200, seed=5):
    """Coefficients that are never zero, so every one of them is changeable."""
    rng = np.random.default_rng(seed)
    values = rng.integers(-30, 30, size).astype(np.int16)
    values[values == 0] = 3
    return values


def message(n_bits, seed=6):
    return np.random.default_rng(seed).integers(0, 2, n_bits).astype(np.uint8)


# ---- the matrix ------------------------------------------------------------


def test_h_hat_is_the_same_everywhere():
    """Pinned. A different matrix decodes every existing stego file to garbage."""
    assert build_h_hat(6, 4).tolist() == [51, 37, 57, 33]


def test_h_hat_is_deterministic():
    assert np.array_equal(build_h_hat(10, 7), build_h_hat(10, 7))


@pytest.mark.parametrize("height", [6, 8, 10, 12])
def test_every_column_reaches_the_top_and_the_bottom(height):
    """Without the top bit the trellis has unreachable states, which quietly costs
    efficiency. Without the bottom bit a column cannot affect its own syndrome bit."""
    columns = build_h_hat(height, 12)

    assert np.all(columns & (1 << (height - 1)))
    assert np.all(columns & 1)
    assert np.all(columns < (1 << height))


@pytest.mark.parametrize("height", [MIN_HEIGHT - 1, MAX_HEIGHT + 1, 0])
def test_height_outside_the_range_is_refused(height):
    with pytest.raises(ValueError, match="Constraint height"):
        build_h_hat(height, 4)


def test_zero_width_is_refused():
    with pytest.raises(ValueError, match="columns wide"):
        build_h_hat(8, 0)


# ---- costs and parity ------------------------------------------------------


def test_parity_is_right_for_negatives():
    """Two's complement gives the parity of the magnitude, which is what matters."""
    assert parity_of(np.array([-3, -2, -1, 0, 1, 2, 3])).tolist() == [1, 0, 1, 0, 1, 0, 1]


def test_a_one_may_not_be_pushed_to_zero():
    """It would leave the non-zero set, and the receiver builds that set from the stego
    file. The two sides would disagree about which coefficients carry the message."""
    values = np.array([1, -1], dtype=np.int16)

    cost, direction = flip_costs(values, np.ones(2), np.ones(2))

    assert direction.tolist() == [1, -1]
    assert np.isfinite(cost).all()


def test_a_zero_never_moves():
    cost, _ = flip_costs(np.array([0], np.int16), np.ones(1), np.ones(1))

    assert cost[0] == FORBIDDEN


def test_the_cheaper_direction_wins():
    values = np.array([9, 9], dtype=np.int16)

    _, direction = flip_costs(values, np.array([1.0, 5.0]), np.array([5.0, 1.0]))

    assert direction.tolist() == [1, -1]


def test_cost_shapes_must_match():
    with pytest.raises(ValueError, match="must match the values"):
        flip_costs(np.ones(4, np.int16), np.ones(4), np.ones(3))


def test_bits_and_bytes_are_inverses():
    payload = b"SIENG3 payload"

    assert bits_to_bytes(bytes_to_bits(payload)) == payload


def test_a_partial_byte_is_refused():
    with pytest.raises(ValueError, match="whole number of bytes"):
        bits_to_bytes(np.ones(9, np.uint8))


# ---- the trellis -----------------------------------------------------------


@pytest.mark.parametrize("rate", RATES)
@pytest.mark.parametrize("height", [10, 12])
def test_stc_roundtrip_all_rates(rate, height):
    """The four research payload rates, at the two heights the experiments use."""
    values = cover()
    bits = message(int(len(values) * rate))

    stego = embed(values, np.ones(len(values)), np.ones(len(values)), bits, height)

    assert np.array_equal(extract(stego, bits.size, height), bits)


@pytest.mark.parametrize("height", [6, 8, 10])
def test_roundtrip_at_every_height(height):
    values = cover()
    bits = message(120)

    stego = embed(values, np.ones(len(values)), np.ones(len(values)), bits, height)

    assert np.array_equal(extract(stego, bits.size, height), bits)


@pytest.mark.parametrize("rate", RATES)
def test_the_non_zero_set_never_changes(rate):
    """The single most important property here. If it fails, extraction silently
    desynchronises after the first coefficient that crossed zero."""
    values = cover()
    values[::7] = 1
    values[3::7] = -1
    bits = message(int(len(values) * rate))

    stego = embed(values, np.ones(len(values)), np.ones(len(values)), bits, 8)

    assert np.array_equal(stego != 0, values != 0)


def test_changes_are_only_ever_by_one():
    values = cover()
    bits = message(200)

    stego = embed(values, np.ones(len(values)), np.ones(len(values)), bits, 8)

    assert set(np.unique(stego.astype(int) - values.astype(int))) <= {-1, 0, 1}


def test_wet_coefficients_never_move():
    values = cover()
    rho = np.ones(len(values))
    rho[::3] = FORBIDDEN
    bits = message(100)

    stego = embed(values, rho, rho, bits, 8)

    assert np.array_equal(stego[::3], values[::3])
    assert np.array_equal(extract(stego, bits.size, 8), bits)


def test_an_empty_message_changes_nothing():
    values = cover()

    stego = embed(values, np.ones(len(values)), np.ones(len(values)), np.zeros(0, np.uint8), 8)

    assert np.array_equal(stego, values)


def test_capacity_error_reports_max():
    """The caller needs the real ceiling to tell the user what would have fitted."""
    with pytest.raises(CapacityError) as error:
        embed(np.array([3, 5, 7], np.int16), np.ones(3), np.ones(3), np.ones(10, np.uint8), 6)

    assert error.value.requested_bits == 10
    assert error.value.max_bits == 3
    assert "3 bits" in str(error.value)


def test_an_all_wet_cover_reports_nothing_movable():
    values = cover(200)
    rho = np.full(200, FORBIDDEN)

    with pytest.raises(CapacityError) as error:
        embed(values, rho, rho, message(20), 6)

    assert error.value.max_bits == 0


def test_block_width_and_usable_length():
    assert usable_length(1000, 100) == (10, 1000)
    assert usable_length(1005, 100) == (10, 1000)


# ---- the bound -------------------------------------------------------------


@pytest.mark.parametrize("target", [100, 400, 900])
def test_the_simulator_hits_the_payload_it_was_asked_for(target):
    rng = np.random.default_rng(3)
    cost = rng.random(2000) * 2 + 0.05

    from sieng.coder.simulator import binary_lambda

    assert binary_payload(cost, binary_lambda(cost, target)) == pytest.approx(target, rel=1e-6)


def test_wet_coefficients_carry_nothing():
    rng = np.random.default_rng(3)
    rho = rng.random(400) * 2 + 0.05
    rho[::2] = FORBIDDEN

    up, down = simulate_embedding(rho, rho, 100)

    assert up[::2].max() == 0.0
    assert down[::2].max() == 0.0


def test_asking_for_more_than_the_cover_holds_is_refused():
    rho = np.full(100, FORBIDDEN)
    rho[:10] = 1.0

    with pytest.raises(ValueError, match="No lambda carries"):
        binary_bound(rho, 500)


def test_ternary_beats_binary_at_the_same_payload():
    """Treating +1 and -1 as separate symbols buys freedom, so the bound is lower.
    The gap is what a double layered coder could still recover."""
    rng = np.random.default_rng(4)
    rho = rng.random(2000) * 2 + 0.05

    assert ternary_bound(rho, rho, 500) < binary_bound(rho, 500)


def test_ternary_carries_more_per_coefficient():
    rho = np.ones(100)

    assert ternary_payload(rho, rho, 1e-9) > binary_payload(rho, 1e-9)


def test_a_taller_trellis_gives_a_smaller_loss():
    """The whole reason the height is configurable. If this ever reverses, the trellis
    or the matrix is wrong, not the bound."""
    values = cover(2000)
    rng = np.random.default_rng(8)
    rho = rng.random(2000) * 2 + 0.05
    bits = message(400)
    cost, _ = flip_costs(values, rho, rho)

    losses = []
    for height in (6, 10):
        stego = embed(values, rho, rho, bits, height)
        losses.append(coding_loss(distortion(values, stego, rho, rho), cost, bits.size))

    assert losses[1] < losses[0]


def test_the_loss_is_close_to_the_bound():
    """Published STC sits near 1.1 at this height. Well above 1.5 means something broke."""
    values = cover(2000)
    rho = np.ones(2000)
    bits = message(400)
    cost, _ = flip_costs(values, rho, rho)

    stego = embed(values, rho, rho, bits, DEFAULT_HEIGHT)
    loss = coding_loss(distortion(values, stego, rho, rho), cost, bits.size)

    assert 1.0 <= loss < 1.5


# ---- segmenting the trellis ------------------------------------------------
#
# The trellis used to be held whole, which is n * 2**h decisions. On a 1200x960 photo at
# the default height that is 3.2 GiB, so an ordinary picture could not be used as a cover
# at all. It is now solved in segments. These say what that is allowed to cost.


def test_segmenting_changes_nothing_about_the_answer(monkeypatch):
    """The whole point: the segments are a memory trick, not a different algorithm.

    Anything less than exact equality would mean stego files depend on how much memory
    the machine that made them happened to have.
    """
    values, rho = cover(4000), np.random.default_rng(9).random(4000) + 0.1
    bits = message(200)

    whole = embed(values, rho, rho, bits, MIN_HEIGHT)
    monkeypatch.setattr(stc, "SEGMENT_COLUMNS", 128)
    in_pieces = embed(values, rho, rho, bits, MIN_HEIGHT)

    assert np.array_equal(whole, in_pieces)


def test_a_segmented_message_still_reads_back(monkeypatch):
    """The receiver is never told where the segments were, so the joins must be invisible."""
    monkeypatch.setattr(stc, "SEGMENT_COLUMNS", 64)
    values, rho = cover(4000), np.random.default_rng(10).random(4000) + 0.1
    bits = message(200)

    stego = embed(values, rho, rho, bits, MIN_HEIGHT)

    assert np.array_equal(extract(stego, bits.size, MIN_HEIGHT), bits)


def test_memory_follows_the_segment_and_not_the_image(monkeypatch):
    """The bug, in one assertion: holding the whole trellis is what made photos impossible.

    Measured against itself rather than against a fixed number of bytes, because what
    must be true is the shape of the growth, not a figure that depends on the machine.
    """
    values, rho = cover(8000), np.random.default_rng(11).random(8000) + 0.1
    bits = message(400)

    def peak_bytes():
        tracemalloc.start()
        embed(values, rho, rho, bits, DEFAULT_HEIGHT)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return peak

    monkeypatch.setattr(stc, "SEGMENT_COLUMNS", 8000 * 2)
    whole = peak_bytes()
    monkeypatch.setattr(stc, "SEGMENT_COLUMNS", 512)
    segmented = peak_bytes()

    assert segmented < whole / 2


def test_a_segment_is_at_least_one_block_and_never_more_than_the_message():
    assert segment_bits(width=10_000_000, height=10, n_bits=50) == 1
    assert segment_bits(width=1, height=10, n_bits=20) == 20
