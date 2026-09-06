"""RunContext, cancellation, and the engine registry.

Small files with small tests, but the registry check is the one that decides whether a
user picking the wrong engine for their file gets a sentence they can act on or a crash
three layers down about array shapes.
"""

import threading
from pathlib import Path

import pytest

from sieng.common.errors import IncompatibleEngineError
from sieng.common.progress import ProgressReporter
from sieng.pipeline.context import Cancelled, CancelToken, RunContext
from sieng.pipeline.engines.base import (
    EmbedRequest,
    EmbedResult,
    Engine,
    ExtractRequest,
    ExtractResult,
)
from sieng.pipeline.registry import EngineRegistry


class FakeEngine(Engine):
    engine_id = "fake_dct"
    description = "A DCT engine that does nothing"
    supported_domains = ("dct",)

    def embed(self, request, context):
        raise NotImplementedError

    def extract(self, request, context):
        raise NotImplementedError


class FakeSpatialEngine(Engine):
    engine_id = "fake_spatial"
    description = "A spatial engine that does nothing"
    supported_domains = ("spatial",)

    def embed(self, request, context):
        raise NotImplementedError

    def extract(self, request, context):
        raise NotImplementedError


class FakeBothEngine(Engine):
    engine_id = "fake_both"
    description = "An engine for either domain"
    supported_domains = ("dct", "spatial")

    def embed(self, request, context):
        raise NotImplementedError

    def extract(self, request, context):
        raise NotImplementedError


def a_registry():
    registry = EngineRegistry()
    registry.register(FakeEngine)
    registry.register(FakeSpatialEngine)
    return registry


# ---- cancellation ----------------------------------------------------------


def test_a_fresh_token_is_not_cancelled():
    assert CancelToken().is_cancelled() is False


def test_checking_after_cancelling_raises():
    """Raises rather than returning a bool, because a caller that ignores a returned
    False keeps working and a caller that ignores an exception cannot."""
    token = CancelToken()
    token.cancel()

    with pytest.raises(Cancelled):
        token.check()


def test_checking_before_cancelling_does_nothing():
    CancelToken().check()


def test_a_token_can_be_reset_between_runs():
    token = CancelToken()
    token.cancel()
    token.reset()

    assert token.is_cancelled() is False
    token.check()


def test_cancelling_from_another_thread_is_seen():
    """The real usage: the ui sets it from the event loop while the pipeline reads it
    from a worker."""
    token = CancelToken()
    threading.Thread(target=token.cancel).start()

    for _ in range(1000):
        if token.is_cancelled():
            break
    else:
        pytest.fail("the cancellation was never observed")


# ---- the context -----------------------------------------------------------


def test_progress_reaches_the_callback():
    seen = []
    context = RunContext(progress=ProgressReporter(lambda pct, msg: seen.append((pct, msg))))

    context.step(50, "halfway")

    assert seen == [(50, "halfway")]


def test_a_step_checks_for_cancellation():
    """Reporting and checking belong at the same points. A step that reports progress
    without checking is a step that cannot be stopped."""
    context = RunContext()
    context.cancel.cancel()

    with pytest.raises(Cancelled):
        context.step(10, "starting")


def test_a_scoped_context_maps_into_its_share_of_the_range():
    """So an engine can report 0 to 100 of its own work without knowing it occupies 20 to
    60 of the whole run."""
    seen = []
    context = RunContext(progress=ProgressReporter(lambda pct, msg: seen.append(pct)))

    context.scoped(20, 60).step(50, "half of my part")

    assert seen == [40]


def test_a_scoped_context_shares_the_cancel_token():
    """One cancellation must stop everything, so the token is shared rather than copied."""
    context = RunContext()
    inner = context.scoped(0, 50)

    context.cancel.cancel()

    assert inner.cancel.is_cancelled() is True


def test_a_scoped_context_can_name_its_logger():
    context = RunContext()

    named = context.scoped(0, 50, "juniward_stc")

    assert named.logger.name.endswith("juniward_stc")


def test_a_default_context_needs_no_arguments():
    """The ui supplies real ones; a test or a script should not have to."""
    context = RunContext()

    context.step(1, "works")
    assert context.logger is not None


# ---- the registry ----------------------------------------------------------


def test_an_engine_can_be_looked_up_by_id():
    assert a_registry().get("fake_dct") is FakeEngine


def test_an_unknown_id_lists_the_known_ones():
    with pytest.raises(KeyError, match="fake_dct"):
        a_registry().get("nonsense")


def test_two_engines_may_not_share_an_id():
    class Impostor(Engine):
        engine_id = "fake_dct"
        description = ""
        supported_domains = ("dct",)

        def embed(self, request, context):
            raise NotImplementedError

        def extract(self, request, context):
            raise NotImplementedError

    with pytest.raises(ValueError, match="already registered"):
        a_registry().register(Impostor)


def test_resolving_a_matching_domain_works():
    assert a_registry().resolve("fake_dct", "dct") is FakeEngine


def test_resolving_the_wrong_domain_is_refused():
    """Caught before the file is opened. Later it would be a crash in the cost layer with
    a message about array shapes."""
    with pytest.raises(IncompatibleEngineError, match="works on dct carriers"):
        a_registry().resolve("fake_dct", "spatial")


def test_the_refusal_says_what_would_have_worked():
    """A user who picked the wrong engine needs the right one named, not just a no."""
    with pytest.raises(IncompatibleEngineError, match="fake_spatial"):
        a_registry().resolve("fake_dct", "spatial")


def test_nothing_is_substituted_silently():
    """Quietly using a different engine would mean the user's result is not the one they
    asked for, which in a research setting is worse than a failure."""
    registry = a_registry()

    with pytest.raises(IncompatibleEngineError):
        registry.resolve("fake_dct", "spatial")


def test_engines_are_listed_per_domain():
    registry = a_registry()
    registry.register(FakeBothEngine)

    assert {e.engine_id for e in registry.for_domain("dct")} == {"fake_dct", "fake_both"}
    assert {e.engine_id for e in registry.for_domain("spatial")} == {
        "fake_spatial",
        "fake_both",
    }


def test_an_engine_for_both_domains_resolves_either_way():
    registry = EngineRegistry()
    registry.register(FakeBothEngine)

    assert registry.resolve("fake_both", "dct") is FakeBothEngine
    assert registry.resolve("fake_both", "spatial") is FakeBothEngine


def test_the_ids_are_sorted():
    assert a_registry().ids() == ["fake_dct", "fake_spatial"]


def test_an_empty_registry_points_at_the_wiring():
    """An empty registry means the composition root registered nothing, which is a
    developer mistake. Saying so beats an empty list the reader has to interpret."""
    with pytest.raises(KeyError, match=r"container\.py registered nothing"):
        EngineRegistry().get("anything")


# ---- the request and result shapes -----------------------------------------


def test_an_embed_request_needs_only_the_essentials():
    """Everything else has a default, so a caller cannot get the optional arguments in
    the wrong order."""
    request = EmbedRequest(
        cover=Path("in.jpg"),
        destination=Path("out.jpg"),
        payload=b"secret",
        state_path=Path("s.state"),
        password=b"pw",
    )

    assert request.payload_rate == 0.1
    assert request.constraint_height is None
    assert request.precover is None
    assert request.component == 0


def test_a_result_reports_what_a_paper_would_need():
    result = EmbedResult(
        destination=Path("out.jpg"),
        payload_bytes=100,
        counter=0,
        changes=250,
        capacity_base=26_000,
        effective_rate=0.031,
        engine_id="juniward_stc",
        distortion=12.5,
        coding_loss=1.09,
    )

    assert "juniward_stc" in result.summary()
    assert "250 coefficients" in result.summary()
    assert "1.090" in result.summary()


def test_an_extract_request_and_result_round_trip_their_fields():
    request = ExtractRequest(stego=Path("s.jpg"), state_path=Path("s.state"), password=b"pw")
    result = ExtractResult(payload=b"secret", counter=3, engine_id="juniward_stc")

    assert request.component == 0
    assert result.payload == b"secret"
    assert result.counter == 3


def test_an_engine_declares_what_it_can_be_used_on():
    """On the class, so the registry can check before a file is opened and the ui can grey
    out an engine rather than offering it and failing."""
    assert FakeEngine().supports("dct") is True
    assert FakeEngine().supports("spatial") is False
