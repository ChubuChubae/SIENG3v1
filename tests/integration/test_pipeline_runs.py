"""run_embed and run_extract: the entry points, and the asymmetry between them.

Most of these are about what the two functions are allowed to say. Embedding is done by
someone who owns the inputs, so its errors name the problem. Extraction is done against a
file that may have come from anywhere, and any failure it can distinguish is something an
examiner can measure, so every one of them is the same error.

The engine underneath is already covered by test_engine_roundtrip.py. What is new here is
the identification, the resolution and the silence.
"""

import pytest

from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import (
    DecryptError,
    IncompatibleEngineError,
    PipelineValidationError,
    RatchetLimitError,
    ReplayError,
)
from sieng.crypto.ratchet import session
from sieng.pipeline import extract as extract_module
from sieng.pipeline.context import Cancelled
from sieng.pipeline.embed import run_embed
from sieng.pipeline.engines.base import EmbedRequest, Engine, ExtractRequest
from sieng.pipeline.engines.juniward_stc import JUniwardStcEngine
from sieng.pipeline.extract import holds_a_message, run_extract
from sieng.pipeline.registry import EngineRegistry
from tests.fake_carrier import FakeDctCarrier, write_cover

FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
SS = bytes(range(32))
SID = b"sess"
PASSWORD = b"a keystore password"
PAYLOAD = b"a message that has to survive the whole pipeline"
ENGINE_ID = "juniward_stc"


class FakeEngineForFake(JUniwardStcEngine):
    """The real engine, pointed at the fake carrier so these run without jpeglib."""

    def __init__(self):
        registry = CarrierRegistry()
        registry.register(FakeDctCarrier)
        super().__init__(carriers=registry)


class SpatialOnlyEngine(Engine):
    engine_id = "spatial_only"
    description = "For testing the domain check"
    supported_domains = ("spatial",)

    def embed(self, request, context):
        raise NotImplementedError

    def extract(self, request, context):
        raise NotImplementedError


class NeedsPrecoverEngine(JUniwardStcEngine):
    engine_id = "needs_precover"
    description = "For testing the precover check"
    requires_precover = True


def registries():
    carriers = CarrierRegistry()
    carriers.register(FakeDctCarrier)
    engines = EngineRegistry()
    engines.register(FakeEngineForFake)
    engines.register(SpatialOnlyEngine)
    engines.register(NeedsPrecoverEngine)
    return carriers, engines


def a_setup(tmp_path):
    cover = write_cover(tmp_path / "cover.fakedct", 256)
    send_state = tmp_path / "send.state"
    recv_state = tmp_path / "recv.state"
    session.create(send_state, SID, SS, PASSWORD, **FAST)
    session.create(recv_state, SID, SS, PASSWORD, **FAST)
    return cover, send_state, recv_state


def an_embed_request(tmp_path, cover, state, **kwargs):
    fields = {
        "cover": cover,
        "destination": tmp_path / "out.fakedct",
        "payload": PAYLOAD,
        "state_path": state,
        "password": PASSWORD,
    }
    return EmbedRequest(**{**fields, **kwargs})


# ---- the loop through the entry points -------------------------------------


def test_embed_extract_roundtrip(tmp_path):
    cover, send_state, recv_state = a_setup(tmp_path)
    carriers, engines = registries()

    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)
    result = run_extract(
        ExtractRequest(stego=tmp_path / "out.fakedct", state_path=recv_state, password=PASSWORD),
        ENGINE_ID,
        carriers,
        engines,
    )

    assert result.payload == PAYLOAD


def test_the_carrier_is_identified_from_its_bytes(tmp_path):
    """Not from the name. A renamed file is common and a deliberately misnamed one is a
    standard way to push a parser down the wrong path."""
    cover, send_state, _ = a_setup(tmp_path)
    renamed = tmp_path / "actually_a_fakedct.png"
    renamed.write_bytes(cover.read_bytes())
    carriers, engines = registries()

    result = run_embed(
        an_embed_request(tmp_path, renamed, send_state), ENGINE_ID, carriers, engines
    )

    assert result.payload_bytes == len(PAYLOAD)


def test_state_saved_before_output_written(tmp_path):
    """The counter is spent the moment it is handed out. A crash between committing the
    state and writing the file loses a message; the other order reuses a key."""
    from sieng.crypto.ratchet import state_store

    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)

    assert state_store.load(send_state, PASSWORD).counter == 1


# ---- what embed is allowed to say ------------------------------------------


def test_a_missing_cover_says_so(tmp_path):
    """The person embedding owns the inputs and needs to fix them, so these are specific."""
    _, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="Cover file not found"):
        run_embed(
            an_embed_request(tmp_path, tmp_path / "nope.fakedct", send_state),
            ENGINE_ID,
            carriers,
            engines,
        )


def test_a_missing_session_says_so(tmp_path):
    cover, _, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="No session state"):
        run_embed(
            an_embed_request(tmp_path, cover, tmp_path / "nope.state"),
            ENGINE_ID,
            carriers,
            engines,
        )


@pytest.mark.parametrize("rate", [0, -0.1, 1.5])
def test_a_rate_outside_the_range_is_refused(tmp_path, rate):
    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="outside 0 to 1"):
        run_embed(
            an_embed_request(tmp_path, cover, send_state, payload_rate=rate),
            ENGINE_ID,
            carriers,
            engines,
        )


def test_writing_over_the_cover_is_refused(tmp_path):
    """Overwriting destroys the only copy of the original, which is also the thing an
    examiner would most like to compare against."""
    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="same file as the cover"):
        run_embed(
            an_embed_request(tmp_path, cover, send_state, destination=cover),
            ENGINE_ID,
            carriers,
            engines,
        )


def test_the_wrong_engine_for_the_carrier_is_refused(tmp_path):
    """Caught before the file is opened, with the engine that would have worked named."""
    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(IncompatibleEngineError, match="juniward_stc"):
        run_embed(an_embed_request(tmp_path, cover, send_state), "spatial_only", carriers, engines)


def test_an_engine_that_needs_a_precover_refuses_without_one(tmp_path):
    """Side informed embedding without side information is a different algorithm, not a
    less accurate one, so there is no fallback."""
    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="no fallback"):
        run_embed(
            an_embed_request(tmp_path, cover, send_state), "needs_precover", carriers, engines
        )


def test_an_empty_password_is_refused(tmp_path):
    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="password"):
        run_embed(
            an_embed_request(tmp_path, cover, send_state, password=b""),
            ENGINE_ID,
            carriers,
            engines,
        )


# ---- what extract is allowed to say ----------------------------------------


def extract_from(path, state, carriers, engines):
    return run_extract(
        ExtractRequest(stego=path, state_path=state, password=PASSWORD),
        ENGINE_ID,
        carriers,
        engines,
    )


def test_a_file_with_nothing_in_it_is_one_error(tmp_path):
    cover, _, recv_state = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(DecryptError):
        extract_from(cover, recv_state, carriers, engines)


def test_the_wrong_session_is_the_same_error(tmp_path):
    """Saying "wrong session" would tell an examiner who the file was not for."""
    cover, send_state, _ = a_setup(tmp_path)
    carriers, engines = registries()
    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)
    other = tmp_path / "other.state"
    session.create(other, SID, bytes(32), PASSWORD, **FAST)

    with pytest.raises(DecryptError):
        extract_from(tmp_path / "out.fakedct", other, carriers, engines)


def test_a_tampered_file_is_the_same_error(tmp_path):
    cover, send_state, recv_state = a_setup(tmp_path)
    carriers, engines = registries()
    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)
    stego = tmp_path / "out.fakedct"
    blob = bytearray(stego.read_bytes())
    blob[6000] ^= 0xFF
    stego.write_bytes(bytes(blob))

    with pytest.raises(DecryptError):
        extract_from(stego, recv_state, carriers, engines)


def test_every_failure_about_the_file_is_indistinguishable(tmp_path):
    """The property the whole file exists for. Four different causes, one answer, so the
    program cannot be used to test whether a file is a stego file."""
    cover, send_state, recv_state = a_setup(tmp_path)
    carriers, engines = registries()
    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)
    stego = tmp_path / "out.fakedct"

    damaged = tmp_path / "damaged.fakedct"
    blob = bytearray(stego.read_bytes())
    blob[6000] ^= 0xFF
    damaged.write_bytes(bytes(blob))

    other = tmp_path / "other.state"
    session.create(other, SID, bytes(32), PASSWORD, **FAST)

    failures = set()
    for path, state in ((cover, recv_state), (stego, other), (damaged, recv_state)):
        with pytest.raises(DecryptError) as error:
            extract_from(path, state, carriers, engines)
        failures.add((type(error.value), str(error.value)))

    assert len(failures) == 1


def test_the_traceback_does_not_name_the_module_that_failed(tmp_path):
    """Raised with `from None`, so a traceback printed by a caller does not say which
    layer gave up and therefore how far the file got."""
    cover, _, recv_state = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(DecryptError) as error:
        extract_from(cover, recv_state, carriers, engines)

    assert error.value.__cause__ is None
    assert error.value.__context__ is None or error.value.__suppress_context__


def test_a_replay_is_reported_as_itself(tmp_path):
    """A fact about our own session, which the receiver already knows. It reveals nothing
    new about the file, and hiding it would leave the user unable to understand why a file
    they just read will not read again."""
    cover, send_state, recv_state = a_setup(tmp_path)
    carriers, engines = registries()
    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)
    stego = tmp_path / "out.fakedct"
    extract_from(stego, recv_state, carriers, engines)

    with pytest.raises(ReplayError):
        extract_from(stego, recv_state, carriers, engines)


def test_a_missing_file_is_a_caller_mistake_not_a_decrypt_failure(tmp_path):
    """Whether a path exists on the caller's own machine says nothing about any file's
    contents, so it may be reported plainly."""
    _, _, recv_state = a_setup(tmp_path)
    carriers, engines = registries()

    with pytest.raises(PipelineValidationError, match="File not found"):
        extract_from(tmp_path / "nope.fakedct", recv_state, carriers, engines)


# ---- the question a ui actually wants to ask -------------------------------


def test_holds_a_message_answers_yes_for_a_real_stego_file(tmp_path):
    cover, send_state, recv_state = a_setup(tmp_path)
    carriers, engines = registries()
    run_embed(an_embed_request(tmp_path, cover, send_state), ENGINE_ID, carriers, engines)

    answer = holds_a_message(
        ExtractRequest(stego=tmp_path / "out.fakedct", state_path=recv_state, password=PASSWORD),
        ENGINE_ID,
        carriers,
        engines,
    )

    assert answer is True


def test_holds_a_message_answers_no_for_a_plain_cover(tmp_path):
    cover, _, recv_state = a_setup(tmp_path)
    carriers, engines = registries()

    answer = holds_a_message(
        ExtractRequest(stego=cover, state_path=recv_state, password=PASSWORD),
        ENGINE_ID,
        carriers,
        engines,
    )

    assert answer is False


def test_the_transparent_errors_are_the_ones_about_our_own_state():
    """Pinned, because adding to this list is how the silence would quietly be lost.

    Each of these is something the receiver already knows about its own session. Anything
    that is a fact about the file belongs on the other side of the line.
    """
    assert extract_module.TRANSPARENT == (ReplayError, RatchetLimitError, Cancelled)
