"""The whole stack below crypto, on real files: carrier, cost, selection, coder, carrier.

Every layer here already has its own tests, and all of them pass on synthetic input. This
file is the first thing that connects them, and it is deliberately written the way Phase 8
will drive them:

    load -> planes -> cost -> permute -> STC embed -> apply -> save
                                                                 |
    load -> planes -> permute -> STC extract <-------------------+

No crypto and no header, so the message is raw bits and the bit count is passed in by hand.
Phase 8 replaces those two things and nothing else about this sequence.

What only shows up here:
  - the quantisation table the carrier attaches, on a real table rather than a flat one,
    including the separate table the chroma components use
  - real bpnzAC counts, so the capacity numbers are the ones a user would actually hit
  - a full embedding, hundreds of changes at once, still splicing back into the original
    headers byte for byte. The unit tests move one coefficient.

JPEG only. The spatial path does not survive this loop yet, for reasons that live in the
coder rather than in the cost layer: see PROJECT_CONTEXT.md 8.4.

The small colour fixture does most of the work here. The trellis is O(n * 2**h) in a Python
loop, so a 512x512 plane takes tens of seconds per embed, and running every case against it
would make this suite something nobody runs.
"""

from pathlib import Path

import numpy as np
import pytest

from sieng.carrier.image._jpeg_codec import find_sos
from sieng.coder.base import DEFAULT_HEIGHT
from sieng.coder.stc import embed, extract
from sieng.common.errors import CapacityError
from sieng.cost.juniward import JUniwardCost
from sieng.cost.uerd import UerdCost
from sieng.domain.selection import inverse_permute, permute

jpeglib = pytest.importorskip("jpeglib", reason="JPEG support needs jpeglib")

from sieng.carrier.image.jpeg import JpegCarrier  # noqa: E402  needs the skip above

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# 64x64 colour. Fast enough to run every case against, and it has chroma planes.
SMALL = "rgb_64_q75.jpg"

# 512x512 grey, which is the size the experiments actually use. Kept for the cases where
# realism is the point rather than mechanics.
LARGE = "grey_512_q75.jpg"

QUALITIES = ["grey_512_q50.jpg", "grey_512_q75.jpg", "grey_512_q95.jpg"]
RATES = [0.05, 0.1, 0.2, 0.4]

# Phase 8 derives this from the message key. Here it only has to be the same on both sides.
SEED = bytes(range(32))


def loaded(path):
    carrier = JpegCarrier(Path(path))
    carrier.load()
    return carrier


def message(n_bits, seed=7):
    return np.random.default_rng(seed).integers(0, 2, n_bits).astype(np.uint8)


def hide(carrier, model, bits, component=0, height=DEFAULT_HEIGHT):
    """Embed into one plane and hand back the carrier.

    This is Phase 8.3 in miniature, and the order of the five steps is the part that
    matters: score the cover, permute, embed, unpermute, give the plane back.
    """
    planes = carrier.planes()
    plane = planes[component]
    values, index = plane.flatten()

    rho_p1, rho_m1 = model.costs(plane)
    order = permute(values.size, SEED)
    stego = embed(
        values[order],
        rho_p1.reshape(-1)[index][order],
        rho_m1.reshape(-1)[index][order],
        bits,
        height,
    )

    plane.unflatten(stego[inverse_permute(order)], index)
    carrier.apply(planes)
    return carrier


def seek(carrier, n_bits, component=0, height=DEFAULT_HEIGHT):
    """Read the message back knowing only the file and the seed, as a receiver would."""
    values, _ = carrier.planes()[component].flatten()
    return extract(values[permute(values.size, SEED)], n_bits, height)


def hidden_and_reloaded(name, model, rate, tmp_path, **kwargs):
    """Run the whole loop and hand back the message and what came out of the file."""
    carrier = loaded(FIXTURES / name)
    base = carrier.nnz_ac(kwargs.get("component", 0))
    bits = message(int(base * rate))
    hide(carrier, model, bits, **kwargs).save(tmp_path / name)
    return bits, seek(loaded(tmp_path / name), bits.size, **kwargs)


# ---- the loop --------------------------------------------------------------


@pytest.mark.parametrize("rate", RATES)
def test_the_message_survives_a_save_and_a_reload(rate, tmp_path):
    """The claim the whole project rests on, at the four rates the experiments use."""
    bits, recovered = hidden_and_reloaded(SMALL, JUniwardCost(), rate, tmp_path)

    assert np.array_equal(recovered, bits)


@pytest.mark.parametrize("model", [JUniwardCost(), UerdCost()], ids=lambda m: m.name)
def test_both_dct_models_drive_the_coder(model, tmp_path):
    bits, recovered = hidden_and_reloaded(SMALL, model, 0.2, tmp_path)

    assert np.array_equal(recovered, bits)


@pytest.mark.parametrize("name", QUALITIES)
def test_every_quality_setting_works(name, tmp_path):
    """A q95 file holds several times the non-zero AC of a q50 one and hands the cost model
    a completely different quantisation table. Both ends of that range have to work."""
    bits, recovered = hidden_and_reloaded(name, UerdCost(), 0.05, tmp_path)

    assert np.array_equal(recovered, bits)


def test_the_full_size_image_works_too(tmp_path):
    """Everything else here runs on 64x64. This is the size the results will be reported
    at, and it is the only case where the wavelet code sees a realistic amount of image."""
    bits, recovered = hidden_and_reloaded(LARGE, JUniwardCost(), 0.05, tmp_path)

    assert np.array_equal(recovered, bits)


# ---- what the file looks like afterwards -----------------------------------


def test_nothing_outside_the_scan_data_moves(tmp_path):
    """A full embedding, not the single coefficient the unit test moves. If the headers
    shift at all the file has been re-encoded, and the payload is the least of the problem."""
    source = FIXTURES / SMALL
    carrier = loaded(source)
    bits = message(int(carrier.capacity_base() * 0.4))

    hide(carrier, JUniwardCost(), bits).save(tmp_path / SMALL)

    original = source.read_bytes()
    stego = (tmp_path / SMALL).read_bytes()
    assert stego[: find_sos(original).end] == original[: find_sos(original).end]
    assert stego != original


def test_the_non_zero_count_is_the_same_after_a_round_trip(tmp_path):
    """The receiver rebuilds the changeable set from the stego file alone. If this count
    moves, the two sides disagree about which coefficients carry the message."""
    carrier = loaded(FIXTURES / SMALL)
    before = carrier.capacity_base()

    hide(carrier, JUniwardCost(), message(int(before * 0.4))).save(tmp_path / SMALL)

    assert loaded(tmp_path / SMALL).capacity_base() == before


def test_no_coefficient_moves_by_more_than_one(tmp_path):
    carrier = loaded(FIXTURES / SMALL)
    before = loaded(FIXTURES / SMALL).planes()[0].values.astype(np.int64)

    hide(carrier, JUniwardCost(), message(int(carrier.capacity_base() * 0.2))).save(
        tmp_path / SMALL
    )
    after = loaded(tmp_path / SMALL).planes()[0].values.astype(np.int64)

    assert np.abs(after - before).max() == 1


def test_the_dc_coefficients_are_untouched(tmp_path):
    """DC is the brightness of a whole 8x8 block, and moving one is visible without any
    statistics at all."""
    carrier = loaded(FIXTURES / SMALL)
    before = loaded(FIXTURES / SMALL).planes()[0].values.copy()

    hide(carrier, JUniwardCost(), message(int(carrier.capacity_base() * 0.4))).save(
        tmp_path / SMALL
    )
    after = loaded(tmp_path / SMALL).planes()[0].values

    assert np.array_equal(after[::8, ::8], before[::8, ::8])


def test_the_changes_go_where_the_cost_model_sent_them(tmp_path):
    """Cheap coefficients should be the ones that moved. If the changes were spread evenly
    the cost map is not reaching the coder, and the whole of Phase 6 buys nothing."""
    carrier = loaded(FIXTURES / SMALL)
    plane = carrier.planes()[0]
    rho, _ = JUniwardCost().costs(plane)
    before = plane.values.copy()

    hide(carrier, JUniwardCost(), message(int(carrier.capacity_base() * 0.1))).save(
        tmp_path / SMALL
    )
    changed = loaded(tmp_path / SMALL).planes()[0].values != before

    assert np.median(rho[changed]) < np.median(rho[np.isfinite(rho)])


# ---- the chroma planes -----------------------------------------------------


def test_the_chroma_components_get_their_own_quantisation_table():
    """Luma and chroma are quantised differently. A cost model handed the wrong table
    scores every coefficient in that plane wrongly while looking perfectly healthy."""
    planes = loaded(FIXTURES / SMALL).planes()

    luma = planes[0].meta["quant_table"]
    chroma = planes[1].meta["quant_table"]
    assert luma.shape == (8, 8)
    assert not np.array_equal(luma, chroma)
    assert np.array_equal(chroma, planes[2].meta["quant_table"])


def test_a_message_can_be_hidden_in_a_chroma_plane(tmp_path):
    bits, recovered = hidden_and_reloaded(SMALL, JUniwardCost(), 0.1, tmp_path, component=1)

    assert np.array_equal(recovered, bits)


# ---- capacity --------------------------------------------------------------


def test_the_advertised_capacity_is_the_one_that_fits(tmp_path):
    """capacity_base() is the number the ui shows a user. One bit per non-zero AC
    coefficient is the ceiling, and it has to work rather than nearly work."""
    carrier = loaded(FIXTURES / SMALL)
    bits = message(carrier.capacity_base())

    hide(carrier, UerdCost(), bits, height=6).save(tmp_path / SMALL)

    assert np.array_equal(seek(loaded(tmp_path / SMALL), bits.size, height=6), bits)


def test_one_bit_past_the_capacity_is_refused():
    carrier = loaded(FIXTURES / SMALL)

    with pytest.raises(CapacityError):
        hide(carrier, UerdCost(), message(carrier.capacity_base() + 1))
