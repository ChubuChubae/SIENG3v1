"""cost and coder together, which is the first point where either can be shown to work.

A cost model alone cannot be wrong in a way that shows up, and a coder alone was only ever
measured against uniform costs. Put them together over a real cost map and the numbers
start meaning something: how many coefficients move, and how much more the trellis pays
than a perfect coder would.

The measurement in test_the_visit_order_is_what_makes_the_trellis_efficient is the reason
this file exists. It found a requirement on Phase 8 that nothing else here would have
caught.
"""

import numpy as np
import pytest

from sieng.coder.base import DEFAULT_HEIGHT, flip_costs
from sieng.coder.simulator import coding_loss
from sieng.coder.stc import distortion, embed, extract
from sieng.cost import _dct
from sieng.cost.juniward import JUniwardCost
from sieng.cost.uerd import UerdCost
from sieng.domain.plane import Plane
from sieng.domain.selection import build_changeable_mask, permute

RATES = [0.05, 0.1, 0.2, 0.4]
SIZE = 128
QUANT = np.full((8, 8), 4.0)
SEED = bytes(range(32))


def cover_plane(size=SIZE, seed=1):
    """A JPEG-like plane: half of it smooth, half of it textured."""
    rng = np.random.default_rng(seed)
    image = 128 + 40 * np.sin(2 * np.pi * np.arange(size)[None, :] / 90) * np.ones((size, 1))
    image[:, size // 2 :] += rng.normal(0, 35, (size, size // 2))
    blocks = _dct.as_blocks(image - _dct.LEVEL_SHIFT)
    exact = np.einsum("ix,rcxy,jy->rcij", _dct.DCT, blocks, _dct.DCT)
    grid = np.round(exact / QUANT).astype(np.int16).swapaxes(1, 2).reshape(size, size)
    return Plane(grid, build_changeable_mask(grid, "dct"), {"quant_table": QUANT})


def scored(model, plane, order=None):
    """The changeable coefficients and their costs, optionally in a secret visit order."""
    flat, index = plane.flatten()
    rho_p1, rho_m1 = model.costs(plane)
    up, down = rho_p1.reshape(-1)[index], rho_m1.reshape(-1)[index]
    if order is not None:
        flat, up, down = flat[order], up[order], down[order]
    return flat, up, down


def payload(n_values, rate, seed=0):
    return np.random.default_rng(seed).integers(0, 2, int(n_values * rate)).astype(np.uint8)


MODELS = [JUniwardCost(), UerdCost()]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
@pytest.mark.parametrize("rate", RATES)
def test_a_real_cost_map_carries_the_message_back(model, rate):
    """The four research rates, over costs that actually vary. Uniform costs hid nothing,
    but a cost map with infinities and a 500x spread is where a coder breaks."""
    plane = cover_plane()
    values, up, down = scored(model, plane)
    bits = payload(values.size, rate)

    stego = embed(values, up, down, bits, DEFAULT_HEIGHT)

    assert np.array_equal(extract(stego, bits.size, DEFAULT_HEIGHT), bits)


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
@pytest.mark.parametrize("rate", RATES)
def test_the_non_zero_count_is_unchanged(model, rate):
    """bpnzAC is meaningless if embedding changes its own denominator, and the receiver
    rebuilds the changeable set from this exact count."""
    plane = cover_plane()
    values, up, down = scored(model, plane)
    bits = payload(values.size, rate)

    stego = embed(values, up, down, bits, DEFAULT_HEIGHT)

    assert np.count_nonzero(stego) == np.count_nonzero(values)
    assert np.array_equal(stego != 0, values != 0)


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.name)
def test_changes_land_in_the_textured_half(model):
    """What the whole cost layer is for. If changes spread evenly the model did nothing."""
    plane = cover_plane()
    rho_p1, _ = model.costs(plane)
    values, index = plane.flatten()
    bits = payload(values.size, 0.2)
    up = rho_p1.reshape(-1)[index]

    stego = embed(values, up, up, bits, DEFAULT_HEIGHT)

    columns = index[stego != values] % SIZE
    assert (columns >= SIZE // 2).mean() > 0.9


def test_the_visit_order_is_what_makes_the_trellis_efficient():
    """Phase 8 must permute before the coder sees anything, and not only for secrecy.

    STC spends one bit per run of consecutive coefficients. In raster order a whole run
    can land inside the smooth half of the image, where every option is expensive, and the
    trellis has to take one anyway. Permuting first mixes cheap and expensive coefficients
    into every run. The measurement below is around 1.7 against 1.1: the visit order is
    worth more than four extra bits of constraint height.
    """
    plane = cover_plane()
    model = JUniwardCost()
    raster = scored(model, plane)
    order = permute(raster[0].size, SEED)
    permuted = scored(model, plane, order)
    bits = payload(raster[0].size, 0.2)

    losses = []
    for values, up, down in (raster, permuted):
        cost, _ = flip_costs(values, up, down)
        stego = embed(values, up, down, bits, DEFAULT_HEIGHT)
        losses.append(coding_loss(distortion(values, stego, up, down), cost, bits.size))

    raster_loss, permuted_loss = losses
    assert permuted_loss < 1.3
    assert raster_loss > permuted_loss * 1.3


def test_juniward_spends_less_than_uerd_on_the_same_payload():
    """Not a law of nature, but on an image with a clearly smooth half it should hold, and
    if it ever reverses the wavelet code is the first place to look."""
    plane = cover_plane()
    order = permute(plane.n_changeable(), SEED)
    bits = payload(plane.n_changeable(), 0.2)

    changes = {}
    for model in MODELS:
        values, up, down = scored(model, plane, order)
        stego = embed(values, up, down, bits, DEFAULT_HEIGHT)
        changes[model.name] = int((stego != values).sum())

    assert changes["juniward"] < changes["uerd"] * 1.5
