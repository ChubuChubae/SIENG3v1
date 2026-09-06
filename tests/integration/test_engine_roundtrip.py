"""The whole system: cover in, stego out, payload back. Crypto included.

This is the first thing that connects the crypto stack to the carrier, cost and coder
path. Everything below has been tested on its own, and carrier plus cost plus coder have
been tested together, but until now nothing has run the ratchet, the AEAD, the header and
the selection channel through a real embed.

The carrier here is `tests/fake_carrier.py`, which stores DCT coefficients directly, so
these tests run whether or not jpeglib is installed. What they prove is that the engine
assembles the layers in the right order. That a JPEG survives byte identical is a
different question, proved with a real file in test_embed_roundtrip.py.
"""

import pytest

from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import CapacityError, DecryptError
from sieng.crypto.ratchet import session, state_store
from sieng.pipeline.context import RunContext
from sieng.pipeline.engines.base import EmbedRequest, ExtractRequest
from sieng.pipeline.engines.juniward_stc import (
    JUniwardStcEngine,
    header_span,
    payload_capacity,
)
from tests.fake_carrier import FakeDctCarrier, write_cover

FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
SS = bytes(range(32))
SID = b"sess"
PASSWORD = b"a keystore password"
PAYLOAD = b"the quick brown fox jumps over the lazy dog " * 3


def an_engine():
    registry = CarrierRegistry()
    registry.register(FakeDctCarrier)
    return JUniwardStcEngine(carriers=registry)


def a_setup(tmp_path, size=256):
    """A cover plus two state files, one per side, from the same shared secret."""
    cover = write_cover(tmp_path / "cover.fakedct", size)
    send_state = tmp_path / "send.state"
    recv_state = tmp_path / "recv.state"
    session.create(send_state, SID, SS, PASSWORD, **FAST)
    session.create(recv_state, SID, SS, PASSWORD, **FAST)
    return cover, send_state, recv_state


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


def test_a_payload_survives_the_whole_stack(tmp_path):
    """Everything at once: ratchet, AEAD, header whitening, selection channel, trellis."""
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"

    embed(engine, cover, stego, PAYLOAD, send_state)

    assert extract(engine, stego, recv_state).payload == PAYLOAD


def test_the_stego_file_differs_from_the_cover(tmp_path):
    cover, send_state, _ = a_setup(tmp_path)
    stego = tmp_path / "out.fakedct"

    embed(an_engine(), cover, stego, PAYLOAD, send_state)

    assert stego.read_bytes() != cover.read_bytes()


@pytest.mark.parametrize("size", [1, 100, 1000])
def test_payloads_of_different_sizes_all_come_back(tmp_path, size):
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    payload = bytes(range(256)) * (size // 256 + 1)
    payload = payload[:size]
    stego = tmp_path / "out.fakedct"

    embed(engine, cover, stego, payload, send_state)

    assert extract(engine, stego, recv_state).payload == payload


def test_an_empty_payload_still_works(tmp_path):
    """A zero length message is still sixteen bytes of tag, so the machinery all runs."""
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"

    embed(engine, cover, stego, b"", send_state)

    assert extract(engine, stego, recv_state).payload == b""


def test_several_messages_in_one_session(tmp_path):
    """The ratchet advances on the sending side and the receiver follows it."""
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()

    for index in range(3):
        payload = f"message number {index}".encode()
        stego = tmp_path / f"out{index}.fakedct"
        result = embed(engine, cover, stego, payload, send_state)
        assert result.counter == index
        assert extract(engine, stego, recv_state).payload == payload


def test_messages_can_arrive_out_of_order(tmp_path):
    """What the skipped pool is for, now through the whole engine."""
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    files = []
    for index in range(3):
        stego = tmp_path / f"out{index}.fakedct"
        embed(engine, cover, stego, f"message {index}".encode(), send_state)
        files.append(stego)

    assert extract(engine, files[2], recv_state).payload == b"message 2"
    assert extract(engine, files[0], recv_state).payload == b"message 0"


# ---- the secret order ------------------------------------------------------


def test_the_same_payload_twice_gives_different_files(tmp_path):
    """seed_sel comes from MK[n], so every message has its own selection channel. If two
    files were identical, an examiner comparing them would learn the layout of both."""
    cover, send_state, _ = a_setup(tmp_path)
    engine = an_engine()

    embed(engine, cover, tmp_path / "a.fakedct", PAYLOAD, send_state)
    embed(engine, cover, tmp_path / "b.fakedct", PAYLOAD, send_state)

    assert (tmp_path / "a.fakedct").read_bytes() != (tmp_path / "b.fakedct").read_bytes()


def test_the_header_and_payload_regions_do_not_overlap(tmp_path):
    """A coefficient carrying a header bit cannot also carry a payload bit."""
    from sieng.crypto.kdf import hkdf, labels
    from sieng.pipeline.engines.juniward_stc import Layout

    header_key = hkdf.expand_key(bytes(32), labels.HEADER_KEY)
    layout = Layout.build(10_000, header_key)

    assert set(layout.header_index.tolist()) & set(layout.payload_index.tolist()) == set()
    assert len(layout.header_index) + len(layout.payload_index) == 10_000


def test_the_split_depends_only_on_the_plane_size_and_the_session_key():
    """The receiver has to locate the header before it knows the payload length, so the
    split must not depend on anything inside the header."""
    from sieng.crypto.kdf import hkdf, labels
    from sieng.pipeline.engines.juniward_stc import Layout

    header_key = hkdf.expand_key(bytes(32), labels.HEADER_KEY)

    first = Layout.build(10_000, header_key)
    second = Layout.build(10_000, header_key)

    assert first.header_index.tolist() == second.header_index.tolist()
    assert header_span(10_000) == 1250
    assert payload_capacity(10_000) == 8750


def test_a_different_session_key_moves_the_header(tmp_path):
    from sieng.pipeline.engines.juniward_stc import Layout

    first = Layout.build(10_000, bytes(32))
    second = Layout.build(10_000, bytes(range(32)))

    assert first.header_index.tolist() != second.header_index.tolist()


# ---- what must fail --------------------------------------------------------


def test_a_payload_that_does_not_fit_is_refused_before_any_work(tmp_path):
    """Checked before the cost map is built, which on a real image takes seconds."""
    cover, send_state, _ = a_setup(tmp_path)

    with pytest.raises(CapacityError):
        embed(an_engine(), cover, tmp_path / "out.fakedct", bytes(100_000), send_state)


def test_a_failed_capacity_check_does_not_spend_a_counter(tmp_path):
    """The check comes before the keys are taken, so a message that never fits does not
    burn a counter every time the user tries."""
    cover, send_state, _ = a_setup(tmp_path)
    before = state_store.load(send_state, PASSWORD).counter

    with pytest.raises(CapacityError):
        embed(an_engine(), cover, tmp_path / "out.fakedct", bytes(100_000), send_state)

    assert state_store.load(send_state, PASSWORD).counter == before


def test_a_stego_file_from_another_session_is_refused(tmp_path):
    """Different shared secret, so a different header key: the header does not even parse."""
    cover, send_state, _ = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"
    embed(engine, cover, stego, PAYLOAD, send_state)

    other = tmp_path / "other.state"
    session.create(other, SID, bytes(32), PASSWORD, **FAST)

    with pytest.raises(DecryptError):
        extract(engine, stego, other)


def test_a_cover_with_nothing_hidden_in_it_is_refused(tmp_path):
    """The common case, and the one that must not hang. The counter search is bounded."""
    cover, _, recv_state = a_setup(tmp_path)

    with pytest.raises(DecryptError):
        extract(an_engine(), cover, recv_state)


def test_a_tampered_stego_file_is_refused(tmp_path):
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"
    embed(engine, cover, stego, PAYLOAD, send_state)

    blob = bytearray(stego.read_bytes())
    blob[5000] ^= 0xFF
    stego.write_bytes(bytes(blob))

    with pytest.raises(DecryptError):
        extract(engine, stego, recv_state)


def test_a_replayed_file_is_refused(tmp_path):
    """Extracting the same file twice. The counter was consumed the first time."""
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"
    embed(engine, cover, stego, PAYLOAD, send_state)
    extract(engine, stego, recv_state)

    with pytest.raises(Exception, match="already used"):
        extract(engine, stego, recv_state)


def test_the_wrong_height_reads_different_bits(tmp_path):
    """The trellis is not self describing, so the receiver has to be told the height the
    sender used. Getting it wrong is a failure, not a garbled payload."""
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"
    embed(engine, cover, stego, PAYLOAD, send_state, constraint_height=8)

    with pytest.raises(DecryptError):
        extract(engine, stego, recv_state, constraint_height=10)


def test_a_matching_height_works(tmp_path):
    cover, send_state, recv_state = a_setup(tmp_path)
    engine = an_engine()
    stego = tmp_path / "out.fakedct"
    embed(engine, cover, stego, PAYLOAD, send_state, constraint_height=8)

    assert extract(engine, stego, recv_state, constraint_height=8).payload == PAYLOAD


# ---- what the result says --------------------------------------------------


def test_the_result_reports_what_a_paper_would_need(tmp_path):
    cover, send_state, _ = a_setup(tmp_path)

    result = embed(an_engine(), cover, tmp_path / "out.fakedct", PAYLOAD, send_state)

    assert result.payload_bytes == len(PAYLOAD)
    assert result.changes > 0
    assert result.capacity_base > 0
    assert 0 < result.effective_rate < 1
    assert 1.0 <= result.coding_loss < 2.0
    assert result.engine_id == "juniward_stc"


def test_the_reported_rate_matches_the_bits_actually_embedded(tmp_path):
    """effective_rate is what a reader would compare against published numbers, so it has
    to count the header as well as the payload."""
    from sieng.crypto.aead import gcm_siv
    from sieng.pipeline.engines.juniward_stc import HEADER_BITS

    cover, send_state, _ = a_setup(tmp_path)

    result = embed(an_engine(), cover, tmp_path / "out.fakedct", PAYLOAD, send_state)

    total = HEADER_BITS + gcm_siv.sealed_length(len(PAYLOAD)) * 8
    assert result.effective_rate == pytest.approx(total / result.capacity_base, rel=1e-6)


def test_progress_runs_from_start_to_finish(tmp_path):
    cover, send_state, _ = a_setup(tmp_path)
    seen = []
    from sieng.common.progress import ProgressReporter

    context = RunContext(progress=ProgressReporter(lambda pct, msg: seen.append(pct)))
    an_engine().embed(
        EmbedRequest(
            cover=cover,
            destination=tmp_path / "out.fakedct",
            payload=PAYLOAD,
            state_path=send_state,
            password=PASSWORD,
        ),
        context,
    )

    assert seen[0] == 0
    assert seen[-1] == 100
    assert seen == sorted(seen)
