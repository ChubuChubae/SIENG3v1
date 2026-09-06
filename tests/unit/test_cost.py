"""cost: the filter bank, the two DCT models, the two spatial ones, and the rules shared by all.

There is no published cost map to compare against here, so correctness is pinned three
ways instead: the filter bank is checked against the properties a wavelet must have, the
geometry is checked against the sizes the papers state, and each model is checked against
the behaviour it exists to produce. A model that ranked flat regions as cheap would pass
none of these.
"""

import inspect
import time

import numpy as np
import pytest

from sieng.cost import _dct
from sieng.cost.base import MIN_COST, WET, CostModel, CostRegistry
from sieng.cost.hill import HillCost
from sieng.cost.juniward import SIGMA, WINDOW, JUniwardCost, mode_impact
from sieng.cost.legacy_texture import LegacyTextureCost
from sieng.cost.si_uniward import SiUniwardCost
from sieng.cost.uerd import UerdCost, block_energy, dc_adjusted, spread_energy
from sieng.cost.wavelet import HPDF, LPDF, TAPS, convolve2_same, daubechies8_filters
from sieng.domain.plane import Plane
from sieng.domain.selection import build_changeable_mask

QUANT = np.full((8, 8), 4.0)
SIZE = 64


def spatial_image(size=SIZE, seed=1):
    """Smooth on the left, noisy on the right. Every model must tell the two apart."""
    rng = np.random.default_rng(seed)
    image = 128 + 40 * np.sin(2 * np.pi * np.arange(size)[None, :] / 90) * np.ones((size, 1))
    image[:, size // 2 :] += rng.normal(0, 35, (size, size // 2))
    return image


def dct_plane(size=SIZE, seed=1, quant=QUANT):
    image = spatial_image(size, seed)
    blocks = _dct.as_blocks(image - _dct.LEVEL_SHIFT)
    exact = np.einsum("ix,rcxy,jy->rcij", _dct.DCT, blocks, _dct.DCT)
    grid = np.round(exact / quant).astype(np.int16).swapaxes(1, 2).reshape(size, size)
    mask = build_changeable_mask(grid, "dct")
    return Plane(grid, mask, {"quant_table": quant})


def spatial_plane(size=SIZE, seed=1):
    values = np.clip(np.rint(spatial_image(size, seed)), 0, 255).astype(np.uint8)
    return Plane(values, np.ones(values.shape, dtype=np.bool_), {"channels": 1})


def changeable_positions(plane, count):
    """The first few positions the models will actually score. Zeros are wet everywhere,
    so a test that pokes at a fixed coordinate would often be testing nothing."""
    rows, cols = np.nonzero(plane.changeable)
    return list(zip(rows[:count].tolist(), cols[:count].tolist(), strict=True))


def halves(rho, size=SIZE):
    """Median finite cost of the smooth half and of the textured half."""
    left, right = rho[:, : size // 2], rho[:, size // 2 :]
    return np.median(left[np.isfinite(left)]), np.median(right[np.isfinite(right)])


# ---- the filter bank -------------------------------------------------------


def test_the_low_pass_filter_preserves_a_constant():
    """A scaling filter sums to sqrt(2). If this is wrong the whole bank is a different one."""
    assert LPDF.sum() == pytest.approx(np.sqrt(2.0), abs=1e-9)


def test_the_high_pass_filter_removes_a_constant():
    """This is why the brightness shift in to_spatial() does not reach the cost."""
    assert HPDF.sum() == pytest.approx(0.0, abs=1e-9)


def test_the_two_filters_are_orthogonal_and_normalised():
    assert HPDF @ LPDF == pytest.approx(0.0, abs=1e-9)
    assert HPDF @ HPDF == pytest.approx(1.0, abs=1e-9)


def test_the_kernels_are_sixteen_square():
    """16 taps is what makes the window 23 wide, which the whole cost loop is built around."""
    assert TAPS == 16
    assert [k.shape for k in daubechies8_filters()] == [(16, 16)] * 3
    assert WINDOW == 23


def test_convolution_matches_a_hand_summed_one():
    """Pinned against the slow definition, because a wrong trim offset shifts every cost."""
    rng = np.random.default_rng(0)
    image = rng.random((20, 20))
    column, row = np.array([1.0, 2.0, 3.0, 4.0]), np.array([1.0, -1.0, 2.0, 0.5])

    got = convolve2_same(image, column, row)

    kernel = np.outer(column, row)
    full = np.zeros((23, 23))
    for i in range(20):
        for j in range(20):
            full[i : i + 4, j : j + 4] += image[i, j] * kernel
    assert np.allclose(got, full[2:22, 2:22])


# ---- the transform ---------------------------------------------------------


def test_the_dct_matrix_is_orthonormal():
    assert np.allclose(_dct.DCT @ _dct.DCT.T, np.eye(8))


def test_a_plane_survives_the_round_trip():
    """to_spatial() has to be the exact inverse, or every cost is scored on a wrong image."""
    image = spatial_image()
    blocks = _dct.as_blocks(image - _dct.LEVEL_SHIFT)
    coefficients = np.einsum("ix,rcxy,jy->rcij", _dct.DCT, blocks, _dct.DCT)
    grid = coefficients.swapaxes(1, 2).reshape(SIZE, SIZE)

    assert np.allclose(_dct.to_spatial(grid, np.ones((8, 8))), image)


def test_the_impact_table_covers_every_mode_and_window():
    impact = mode_impact(QUANT)

    assert impact.shape == (3, 64, WINDOW * WINDOW)
    assert np.all(impact >= 0)
    assert impact.sum() > 0


def test_the_impact_table_scales_with_the_quantisation_step():
    """A coarser table means a change of 1 moves the pixels further, so it must cost more."""
    assert mode_impact(QUANT * 3).sum() == pytest.approx(mode_impact(QUANT).sum() * 3)


# ---- what every model must do ----------------------------------------------

MODELS = [JUniwardCost(), UerdCost()]
SPATIAL_MODELS = [HillCost(), LegacyTextureCost()]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_a_smooth_region_costs_more_than_a_textured_one(model):
    """The one claim a cost model makes. If this fails nothing else about it matters."""
    smooth, textured = halves(model.costs(dct_plane())[0])

    assert smooth > textured * 5


@pytest.mark.parametrize("model", SPATIAL_MODELS, ids=lambda m: m.name)
def test_spatial_models_also_prefer_texture(model):
    smooth, textured = halves(model.costs(spatial_plane())[0])

    assert smooth > textured


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_unchangeable_positions_are_infinite(model):
    """Not merely expensive. The trellis will take an expensive edge when nothing else fits."""
    plane = dct_plane()

    rho_p1, rho_m1 = model.costs(plane)

    assert np.all(np.isinf(rho_p1[~plane.changeable]))
    assert np.all(np.isinf(rho_m1[~plane.changeable]))


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_the_dc_coefficient_is_never_offered(model):
    """It shifts the brightness of a whole block, which is visible without any statistics."""
    rho, _ = model.costs(dct_plane())

    assert np.all(np.isinf(rho[::8, ::8]))


@pytest.mark.parametrize("model", MODELS + SPATIAL_MODELS, ids=lambda m: m.name)
def test_costs_are_positive_and_never_free(model):
    plane = dct_plane() if model.domain == "dct" else spatial_plane()

    rho, _ = model.costs(plane)

    assert np.all(rho >= MIN_COST)
    assert not np.any(np.isnan(rho))


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_the_same_cover_always_scores_the_same(model):
    """No key and no payload reach this layer, so two runs cannot differ."""
    first, _ = model.costs(dct_plane())
    second, _ = model.costs(dct_plane())

    assert np.array_equal(first, second)


@pytest.mark.parametrize("model", MODELS + SPATIAL_MODELS, ids=lambda m: m.name)
def test_no_model_can_see_the_payload_or_a_key(model):
    """A cost map is a property of the cover alone. Enforced structurally: costs() takes a
    plane and nothing else, so there is nowhere for a payload or a seed to enter."""
    parameters = list(inspect.signature(type(model).compute).parameters)

    assert parameters == ["self", "plane"]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_a_coefficient_at_the_limit_may_only_move_inwards(model):
    """1023 is the top of the 12 bit range. Going further would not survive the encoder."""
    plane = dct_plane()
    plane.values[1, 1] = 1023
    plane.values[1, 2] = -1023
    plane.changeable[1, 1] = plane.changeable[1, 2] = True

    rho_p1, rho_m1 = model.costs(plane)

    assert np.isinf(rho_p1[1, 1]) and np.isfinite(rho_m1[1, 1])
    assert np.isinf(rho_m1[1, 2]) and np.isfinite(rho_p1[1, 2])


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_a_plane_without_a_quantisation_table_is_refused(model):
    plane = dct_plane()
    plane.meta.pop("quant_table")

    with pytest.raises(ValueError, match="quant_table"):
        model.costs(plane)


# ---- uerd ------------------------------------------------------------------


def test_uerd_is_much_faster_than_juniward():
    """It is the baseline, so it has to be cheap enough to run over a whole dataset."""
    plane = dct_plane(128)
    start = time.perf_counter()
    UerdCost().costs(plane)
    uerd = time.perf_counter() - start
    start = time.perf_counter()
    JUniwardCost().costs(plane)
    juniward = time.perf_counter() - start

    assert uerd * 5 < juniward


def test_the_dc_step_is_replaced_by_its_neighbours_mean():
    """The real DC step dwarfs every AC one, and would make DC look absurdly cheap."""
    quant = np.arange(64, dtype=np.float64).reshape(8, 8) + 1

    assert dc_adjusted(quant)[0, 0] == pytest.approx(0.5 * (quant[1, 0] + quant[0, 1]))
    assert dc_adjusted(quant)[0, 1] == quant[0, 1]


def test_block_energy_ignores_the_dc_coefficient():
    """DC is the block's brightness, which says nothing about whether it hides a change."""
    values = np.zeros((8, 8), dtype=np.int16)
    values[0, 0] = 500

    assert block_energy(values, np.ones((8, 8))).item() == 0.0


def test_a_flat_block_borrows_energy_from_its_neighbours():
    """Without this a flat block beside a busy one is fully wet, and that boundary is
    exactly where an examiner looks first."""
    energy = np.array([[0.0, 100.0], [0.0, 0.0]])

    spread = spread_energy(energy)

    assert spread[0, 0] > 0
    assert spread[0, 1] > spread[1, 0]


# ---- si-uniward ------------------------------------------------------------


def test_si_uniward_refuses_to_run_without_the_original():
    """Side informed embedding without side information is a different algorithm, not a
    less accurate one, so there is no fallback."""
    with pytest.raises(ValueError, match="unquantised DCT"):
        SiUniwardCost().costs(dct_plane())


def test_si_uniward_refuses_a_precover_of_the_wrong_shape():
    with pytest.raises(ValueError, match="not the source"):
        SiUniwardCost(np.zeros((8, 8))).costs(dct_plane())


def precover_of(plane, offsets):
    """The original coefficients this cover was rounded from, with chosen rounding errors.

    offsets maps a changeable position to how far, in quantisation steps, the exact value
    sat from the integer the encoder picked.
    """
    exact = plane.values.astype(np.float64) * np.tile(QUANT, (SIZE // 8, SIZE // 8))
    for (row, col), fraction in offsets.items():
        exact[row, col] += fraction * QUANT[row % 8, col % 8]
    return exact


def test_si_uniward_only_offers_the_direction_the_rounding_went():
    plane = dct_plane()
    up, down = changeable_positions(plane, 2)

    rho_p1, rho_m1 = SiUniwardCost(precover_of(plane, {up: 0.4, down: -0.4})).costs(plane)

    assert np.isfinite(rho_p1[up]) and np.isinf(rho_m1[up])
    assert np.isfinite(rho_m1[down]) and np.isinf(rho_p1[down])


def test_a_coefficient_the_encoder_nearly_could_not_decide_is_cheapest():
    """That is the whole point of holding the original: a rounding at 0.5 was arbitrary."""
    plane = dct_plane()
    undecided, certain = changeable_positions(plane, 2)

    rho_p1, _ = SiUniwardCost(precover_of(plane, {undecided: 0.49, certain: 0.01})).costs(plane)

    assert rho_p1[undecided] < rho_p1[certain]


def test_si_uniward_declares_that_it_needs_a_precover():
    """The pipeline reads this flag to refuse early rather than half way through a run."""
    assert SiUniwardCost.requires_precover is True
    assert JUniwardCost.requires_precover is False


# ---- the shared rules ------------------------------------------------------


def test_a_model_returning_the_wrong_shape_is_caught():
    class Broken(CostModel):
        name = "broken"
        domain = "dct"

        def compute(self, plane):
            return np.ones(3), np.ones(3)

    with pytest.raises(ValueError, match="must describe the same elements"):
        Broken().costs(dct_plane())


def test_a_nan_becomes_wet_rather_than_reaching_the_coder():
    class Nanny(CostModel):
        name = "nanny"
        domain = "dct"

        def compute(self, plane):
            broken = np.full(plane.values.shape, np.nan)
            return broken, broken

    rho, _ = Nanny().costs(dct_plane())

    assert np.all(np.isinf(rho))


def test_an_absurdly_large_cost_is_treated_as_wet():
    """The reference implementations cap instead of using infinity, and mean the same thing."""

    class Huge(CostModel):
        name = "huge"
        domain = "dct"

        def compute(self, plane):
            big = np.full(plane.values.shape, 1e20)
            return big, big

    rho, _ = Huge().costs(dct_plane())

    assert np.all(rho == WET)


# ---- the registry ----------------------------------------------------------


def test_a_model_can_be_looked_up_by_name():
    registry = CostRegistry()
    registry.register(UerdCost)

    assert registry.get("uerd") is UerdCost
    assert registry.names() == ["uerd"]


def test_two_models_may_not_share_a_name():
    class Impostor(CostModel):
        name = "uerd"
        domain = "dct"

        def compute(self, plane):
            return np.ones(1), np.ones(1)

    registry = CostRegistry()
    registry.register(UerdCost)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(Impostor)


def test_an_unknown_name_lists_the_known_ones():
    registry = CostRegistry()
    registry.register(UerdCost)

    with pytest.raises(KeyError, match="uerd"):
        registry.get("nonsense")


def test_the_registry_separates_the_two_domains():
    registry = CostRegistry()
    registry.register(UerdCost)
    registry.register(HillCost)

    assert registry.for_domain("dct") == [UerdCost]
    assert registry.for_domain("spatial") == [HillCost]


def test_sigma_is_the_published_value():
    """Pinned. It sets how sharply flat regions are punished, and every published J-UNIWARD
    number assumes this one."""
    assert SIGMA == 2.0**-6
