"""run_extract: pull a payload back out, or say nothing about why not.

The asymmetry with embed.py is the point of this file. Embedding is done by someone who
owns the inputs, so its errors should be specific and helpful: the cover is missing, the
rate is wrong, this engine does not handle PNG. Extraction is done against a file that may
have come from anywhere, and every distinguishable failure is something an examiner can
measure.

    "wrong password"        tells them the file holds something
    "no header found"       tells them the file holds nothing
    "wrong session"         tells them who it was not for
    "bad tag"               tells them it was tampered with

All four are the same answer here: DecryptError, with no detail. That is not politeness
towards an attacker, it is the difference between a program that can be used to test
whether a file is a stego file and one that cannot.

Mistakes the caller made, as opposed to facts about the file, are still reported plainly.
A missing file or a state path that does not exist says so, because knowing those does not
tell anyone anything about any file's contents.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from pathlib import Path

from sieng.carrier.detect import sniff
from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import (
    CarrierError,
    CryptoError,
    DecryptError,
    PipelineValidationError,
    RatchetLimitError,
    ReplayError,
)
from sieng.pipeline.context import Cancelled, RunContext
from sieng.pipeline.engines.base import ExtractRequest, ExtractResult
from sieng.pipeline.registry import EngineRegistry

# Failures that describe our own state rather than the file, and so may be reported as
# themselves. A replayed counter and an over-long ratchet jump are both facts the receiver
# already knows about its own session; neither reveals anything new about the file.
TRANSPARENT: tuple[type[Exception], ...] = (ReplayError, RatchetLimitError, Cancelled)


def run_extract(
    request: ExtractRequest,
    engine_id: str,
    carriers: CarrierRegistry,
    engines: EngineRegistry,
    context: RunContext | None = None,
) -> ExtractResult:
    """Recover a payload. Every failure about the file itself is one DecryptError.

    The engine is asked to do the work; this layer's job is to make sure that whatever
    comes back out of it, an observer learns only whether extraction succeeded.
    """
    context = context or RunContext()
    validate(request)

    context.step(0, "Identifying the file")
    carrier_class = sniff(request.stego, carriers)
    engine_class = engines.resolve(engine_id, carrier_class.domain)

    context.logger.info("Extracting from %s with %s", request.stego.name, engine_id)
    try:
        return engine_class().extract(request, context.scoped(0, 100, engine_id))
    except TRANSPARENT:
        raise
    except (CarrierError, CryptoError, ValueError):
        # Deliberately broad, and deliberately silent. Whatever went wrong, the caller
        # gets the same answer as for every other kind of wrong. The original is not
        # chained either: a traceback would name the module that failed.
        raise DecryptError from None


def validate(request: ExtractRequest) -> None:
    """Check what is about the caller rather than about the file.

    These may be specific. Whether a path exists on the caller's own machine says nothing
    about the contents of anything.
    """
    if not Path(request.stego).is_file():
        raise PipelineValidationError(f"File not found: {request.stego}")
    if not Path(request.state_path).is_file():
        raise PipelineValidationError(
            f"No session state at {request.state_path}. Without the session this file "
            f"cannot be read even if it does hold something."
        )
    if not request.password:
        raise PipelineValidationError("A password is needed to open the session state")


def holds_a_message(
    request: ExtractRequest,
    engine_id: str,
    carriers: CarrierRegistry,
    engines: EngineRegistry,
) -> bool:
    """Whether this file opens, as a bool, for a ui that wants to show a state.

    Named for what it actually answers. Anything that offers to tell a user "is there
    something hidden in this file" is a detector, and this one only works for the person
    who already holds the session. It is here so the ui does not build its own version by
    catching exceptions and getting the distinction wrong.
    """
    try:
        run_extract(request, engine_id, carriers, engines)
    except (DecryptError, PipelineValidationError, *TRANSPARENT):
        return False
    return True
