"""run_embed: the entry point everything above the pipeline calls.

The engine already knows how to hide a payload. What this adds is the three decisions that
have to be made before an engine can be chosen at all, and the one guarantee that has to
hold whichever engine is chosen.

    identify   the carrier comes from the file's bytes, never its name
    resolve    the engine is checked against that carrier's domain before anything opens
    validate   the arguments are checked before any expensive work starts

The guarantee is that a run either produces a stego file and a spent counter, or produces
neither. The engine commits the ratchet state before it writes the file, so the only crash
window leaves a counter spent and no file: a lost message, never a reused key. This layer
does not widen that window, which is why it does no work of its own between the engine
returning and the caller getting the result.

Nothing here does arithmetic. If a calculation appears in this file it belongs in a layer
that has tests for it.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from pathlib import Path

from sieng.carrier.detect import sniff
from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import PipelineValidationError
from sieng.pipeline.context import RunContext
from sieng.pipeline.engines.base import EmbedRequest, EmbedResult
from sieng.pipeline.registry import EngineRegistry


def run_embed(
    request: EmbedRequest,
    engine_id: str,
    carriers: CarrierRegistry,
    engines: EngineRegistry,
    context: RunContext | None = None,
) -> EmbedResult:
    """Hide a payload, choosing the engine against what the cover actually is.

    Raises before opening anything if the request cannot work: a missing file, a rate
    outside the range, an engine that does not handle this kind of carrier. Those are all
    mistakes the caller can fix, and finding them early costs nothing.
    """
    context = context or RunContext()
    validate(request)

    context.step(0, "Identifying the cover")
    carrier_class = sniff(request.cover, carriers)
    engine_class = engines.resolve(engine_id, carrier_class.domain)

    if engine_class.requires_precover and request.precover is None:
        raise PipelineValidationError(
            f"Engine '{engine_id}' needs the original uncompressed image as well as the "
            f"cover. Side informed embedding without side information is a different "
            f"algorithm, not a less accurate one, so there is no fallback."
        )

    context.logger.info("Embedding into %s with %s", request.cover.name, engine_id)
    return engine_class(carriers).embed(request, context.scoped(0, 100, engine_id))


def validate(request: EmbedRequest) -> None:
    """Check what can be checked without opening a file.

    Separated so the ui can call it as the user types, and so the reasons live in one
    place rather than being rediscovered in each caller.
    """
    if not Path(request.cover).is_file():
        raise PipelineValidationError(f"Cover file not found: {request.cover}")
    if request.precover is not None and not Path(request.precover).is_file():
        raise PipelineValidationError(f"Precover file not found: {request.precover}")
    if not 0 < request.payload_rate <= 1:
        raise PipelineValidationError(
            f"Payload rate {request.payload_rate} is outside 0 to 1 bpnzAC. Above 0.5 the "
            f"coder cannot route around expensive coefficients and the result is easy to "
            f"detect, which is why the capacity check refuses it later as well."
        )
    if not Path(request.state_path).is_file():
        raise PipelineValidationError(
            f"No session state at {request.state_path}. A session has to be created "
            f"before anything can be sent through it."
        )
    if Path(request.destination) == Path(request.cover):
        raise PipelineValidationError(
            "The destination is the same file as the cover. Overwriting the cover destroys "
            "the only copy of the original, which is also the thing an examiner would most "
            "like to compare against."
        )
    if not request.password:
        raise PipelineValidationError("A password is needed to open the session state")
