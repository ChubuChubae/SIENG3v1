"""The real engine on a real JPEG. The one combination nothing else covers.

The other integration files each leave something out, and until this file existed the gap
between them was invisible:

    test_embed_roundtrip.py    real JPEG, but drives carrier, cost and coder directly.
                               No engine, no crypto, no header.
    test_engine_roundtrip.py   the whole engine including crypto, but on the fake DCT
                               carrier, so nothing entropy-coded is ever written.
    test_pipeline_runs.py      the entry points, also on the fake carrier.
    test_cli.py                the command line, also on the fake carrier.

So the engine had never opened a .jpg. Everything JPEG-specific about the assembled system
was untested: the quantisation table reaching the cost model through the engine rather than
through a hand-built Plane, byte-exactness after a full embed that writes into two separate
regions, and capacity arithmetic against a real non-zero AC count rather than a synthetic
one.

Skipped where jpeglib is not installed, which is why the fake carrier exists at all. A skip
here is not a pass: this file is the one that says the product works.
"""

import numpy as np
import pytest

from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import CapacityError, DecryptError
from sieng.crypto.ratchet import session
from sieng.pipeline.context import RunContext
from sieng.pipeline.engines.base import EmbedRequest, ExtractRequest
from sieng.pipeline.engines.juniward_stc import JUniwardStcEngine

jpeglib = pytest.importorskip("jpeglib", reason="the real JPEG path needs jpeglib")

from pathlib import Path  # noqa: E402

from sieng.carrier.image._jpeg_codec import find_sos  # noqa: E402
from sieng.carrier.image.jpeg import JpegCarrier  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
COVER = FIXTURES / "grey_512_q75.jpg"
COLOUR = FIXTURES / "rgb_64_q75.jpg"
QUALITIES = ["grey_512_q50.jpg", "grey_512_q75.jpg", "grey_512_q95.jpg"]

FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
SS = bytes(range(32))
SID = b"sess"
PASSWORD = b"a keystore password"
RATES = [0.05, 0.1, 0.2, 0.4]


def an_engine():
    registry = CarrierRegistry()
    registry.register(JpegCarrier)
    return JUniwardStcEngine(carriers=registry)


def two_sessions(tmp_path):
    send = tmp_path / "send.state"
    recv = tmp_path / "recv.state"
    session.create(send, SID, SS, PASSWORD, **FAST)
    session.create(recv, SID, SS, PASSWORD, **FAST)
    return send, recv


def payload_for(cover, rate):
    """A payload that fills most of what the rate allows, minus the header and the tag.

    Sized from the carrier's own capacity base rather than a guess, so these tests exercise
    the arithmetic the product uses instead of a number that happens to fit.
    """
    carrier = JpegCarrier(cover)
    carrier.load()
    bits = int(carrier.capacity_base() * rate)
    return bytes((bits // 8) - 32)


def embed(engine, cover, destination, payload, state, **kwargs):
    return engine.embed(
        EmbedRequest(
            cover=cover,
            destination=destination,
            payload=payload,
            state_path=state,
            password=PASSWORD,
            **kwargs,
        ),
        RunContext(),
    )


def extract(engine, stego, state, **kwargs):
    return engine.extract(
        ExtractRequest(stego=stego, state_path=state, password=PASSWORD, **kwargs),
        RunContext(),
    )


# ---- the loop --------------------------------------------------------------


@pytest.mark.parametrize("rate", RATES)
def test_a_payload_survives_a_real_jpeg(tmp_path, rate):
    """The four research rates, through the whole assembled system, on a real file."""
    send, recv = two_sessions(tmp_path)
    engine = an_engine()
    payload = payload_for(COVER, rate)
    stego = tmp_path / "out.jpg"

    embed(engine, COVER, stego, payload, send)

    assert extract(engine, stego, recv).payload == payload


@pytest.mark.parametrize("name", QUALITIES)
def test_every_quality_setting_works(tmp_path, name):
    """A q95 file holds several times the non-zero AC of a q50 one and hands the cost model
    a completely different quantisation table. This is the first test where that table
    reaches J-UNIWARD through the engine rather than through a hand-built Plane."""
    send, recv = two_sessions(tmp_path)
    engine = an_engine()
    cover = FIXTURES / name
    payload = payload_for(cover, 0.05)
    stego = tmp_path / name

    embed(engine, cover, stego, payload, send)

    assert extract(engine, stego, recv).payload == payload


def test_a_colour_jpeg_works(tmp_path):
    send, recv = two_sessions(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.jpg"

    embed(engine, COLOUR, stego, b"a short message", send)

    assert extract(engine, stego, recv).payload == b"a short message"


def test_several_messages_through_one_session(tmp_path):
    send, recv = two_sessions(tmp_path)
    engine = an_engine()

    for index in range(3):
        payload = f"message number {index}".encode()
        stego = tmp_path / f"out{index}.jpg"
        assert embed(engine, COVER, stego, payload, send).counter == index
        assert extract(engine, stego, recv).payload == payload


# ---- what the JPEG looks like afterwards -----------------------------------


def test_nothing_outside_the_scan_data_moves(tmp_path):
    """The rule the whole project rests on, now after a full embed rather than the single
    changed coefficient the unit test uses. If the headers shift, the file has been
    re-encoded and DCTR finds that with nothing hidden in it at all."""
    send, _ = two_sessions(tmp_path)
    stego = tmp_path / "out.jpg"

    embed(an_engine(), COVER, stego, payload_for(COVER, 0.4), send)

    original = COVER.read_bytes()
    written = stego.read_bytes()
    assert written[: find_sos(original).end] == original[: find_sos(original).end]
    assert written != original


def test_the_non_zero_count_is_unchanged(tmp_path):
    """bpnzAC is meaningless if embedding changes its own denominator, and the receiver
    rebuilds the changeable set from this exact count."""
    send, _ = two_sessions(tmp_path)
    before = JpegCarrier(COVER)
    before.load()
    stego = tmp_path / "out.jpg"

    embed(an_engine(), COVER, stego, payload_for(COVER, 0.1), send)

    after = JpegCarrier(stego)
    after.load()
    assert after.capacity_base() == before.capacity_base()


def test_no_coefficient_moves_by_more_than_one(tmp_path):
    send, _ = two_sessions(tmp_path)
    original = JpegCarrier(COVER)
    original.load()
    before = original.planes()[0].values.astype(np.int64)
    stego = tmp_path / "out.jpg"

    embed(an_engine(), COVER, stego, payload_for(COVER, 0.1), send)

    reloaded = JpegCarrier(stego)
    reloaded.load()
    after = reloaded.planes()[0].values.astype(np.int64)
    assert np.abs(after - before).max() == 1


def test_the_dc_coefficients_are_untouched(tmp_path):
    send, _ = two_sessions(tmp_path)
    original = JpegCarrier(COVER)
    original.load()
    before = original.planes()[0].values.copy()
    stego = tmp_path / "out.jpg"

    embed(an_engine(), COVER, stego, payload_for(COVER, 0.1), send)

    reloaded = JpegCarrier(stego)
    reloaded.load()
    assert np.array_equal(reloaded.planes()[0].values[::8, ::8], before[::8, ::8])


# ---- the numbers a paper would report --------------------------------------


@pytest.mark.parametrize("rate", RATES)
def test_the_reported_rate_is_close_to_the_rate_asked_for(tmp_path, rate):
    """effective_rate counts the header as well as the payload, so it should land just
    under the requested rate rather than over it."""
    send, _ = two_sessions(tmp_path)

    result = embed(an_engine(), COVER, tmp_path / "out.jpg", payload_for(COVER, rate), send)

    assert result.effective_rate <= rate
    assert result.effective_rate > rate * 0.9


def test_the_coding_loss_is_in_the_range_published_work_reports(tmp_path):
    """Around 1.1 at these heights. Well above 1.5 would mean the trellis or the secret
    order is not doing its job, and the cost model would take the blame in Phase 10."""
    send, _ = two_sessions(tmp_path)

    result = embed(an_engine(), COVER, tmp_path / "out.jpg", payload_for(COVER, 0.2), send)

    assert 1.0 <= result.coding_loss < 1.5


def test_the_changes_are_a_fraction_of_the_bits_embedded(tmp_path):
    """What the coder buys. Without STC every bit costs about half a change; with it the
    ratio should be far better than that."""
    send, _ = two_sessions(tmp_path)
    payload = payload_for(COVER, 0.2)

    result = embed(an_engine(), COVER, tmp_path / "out.jpg", payload, send)

    bits = len(payload) * 8
    assert result.changes < bits * 0.4


# ---- what must fail --------------------------------------------------------


def test_a_payload_that_does_not_fit_is_refused(tmp_path):
    send, _ = two_sessions(tmp_path)
    carrier = JpegCarrier(COVER)
    carrier.load()

    with pytest.raises(CapacityError):
        embed(an_engine(), COVER, tmp_path / "out.jpg", bytes(carrier.capacity_base()), send)


def test_a_plain_jpeg_holds_nothing(tmp_path):
    """The common case, and the one that must not hang: the counter search is bounded."""
    _, recv = two_sessions(tmp_path)

    with pytest.raises(DecryptError):
        extract(an_engine(), COVER, recv)


def test_a_ciphertext_moved_to_another_image_is_refused(tmp_path):
    """The aad carries the carrier fingerprint, so coefficients lifted out of one file and
    dropped into another do not open (THREAT_MODEL.md S10)."""
    send, recv = two_sessions(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.jpg"
    embed(engine, COVER, stego, b"a message", send)

    donor = JpegCarrier(stego)
    donor.load()
    host = JpegCarrier(FIXTURES / "grey_512_q95.jpg")
    host.load()
    planes = host.planes()
    if planes[0].values.shape == donor.planes()[0].values.shape:
        planes[0].values[:] = donor.planes()[0].values
        host.apply(planes)
        host.save(tmp_path / "transplanted.jpg")

        with pytest.raises(DecryptError):
            extract(engine, tmp_path / "transplanted.jpg", recv)
