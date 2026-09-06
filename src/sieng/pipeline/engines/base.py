"""The Engine contract: what a complete embedding strategy has to provide.

An engine is one working combination of the layers below it. `juniward_stc` is JPEG plus
J-UNIWARD plus STC; `hill_stc` would be PNG plus HILL plus STC. Everything an engine does
is assembly: no engine contains arithmetic of its own, because arithmetic in an engine is
arithmetic that no unit test below it covers.

The requests and results are dataclasses rather than long argument lists so that adding a
field later does not silently reorder anyone's positional arguments. They also give the ui
one shape to build and one shape to read.

`supported_domains` is on the class rather than checked inside `embed`, so the registry
can refuse a bad pairing before a file is opened, and so the ui can grey out an engine it
cannot use rather than offering it and failing.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from sieng.carrier.registry import CarrierRegistry
from sieng.common.types import Domain
from sieng.pipeline.context import RunContext


@dataclass
class EmbedRequest:
    """Everything needed to hide one payload in one cover."""

    cover: Path
    destination: Path
    payload: bytes
    state_path: Path
    password: bytes

    # bpnzAC for JPEG. The engine converts it to a bit count against the carrier's own
    # capacity base, so the same number means the same thing across carriers.
    payload_rate: float = 0.1

    # None means the engine's default height. Present so a research run can sweep it.
    constraint_height: int | None = None

    # The original uncompressed image, for side informed embedding. Only SI-UNIWARD uses
    # it, and it refuses to run without it rather than falling back.
    precover: Path | None = None

    # Which colour component to embed in. Luma is what the literature reports.
    component: int = 0

    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedResult:
    """What happened, in enough detail to report and to reproduce."""

    destination: Path
    payload_bytes: int
    counter: int
    changes: int
    capacity_base: int
    effective_rate: float
    engine_id: str

    # Distortion actually paid, and how much more that is than a perfect coder would have
    # paid. Reported next to detection results so a bad number can be attributed.
    distortion: float = 0.0
    coding_loss: float = 1.0

    def summary(self) -> str:
        return (
            f"{self.payload_bytes} bytes hidden in {self.destination.name} using "
            f"{self.engine_id}: {self.changes} coefficients changed at "
            f"{self.effective_rate:.3f} bpnzAC, coding loss {self.coding_loss:.3f}"
        )


@dataclass
class ExtractRequest:
    """Everything needed to read a payload back out."""

    stego: Path
    state_path: Path
    password: bytes
    component: int = 0

    # Must match the height the sender used. The trellis is not self describing, so a
    # different height reads the same coefficients as different bits.
    constraint_height: int | None = None

    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractResult:
    payload: bytes
    counter: int
    engine_id: str


class Engine(ABC):
    """One complete strategy for hiding and recovering a payload.

    Implementations assemble the layers in the order given by PROJECT_STRUCTURE.md 2.3
    and 2.4. That order is a security property, not a style choice, so an engine that
    reorders it is wrong even if its tests pass.
    """

    engine_id: ClassVar[str]
    description: ClassVar[str]

    # Which carrier domains this engine can be used with. Checked by the registry before
    # anything is opened.
    supported_domains: ClassVar[tuple[Domain, ...]]

    # True when the engine needs the original uncompressed image as well as the cover.
    requires_precover: ClassVar[bool] = False

    def __init__(self, carriers: CarrierRegistry | None = None) -> None:
        """Take the carrier registry the pipeline resolved this engine against.

        Every engine accepts it, and the pipeline always passes it, because an engine that
        builds its own registry can disagree with the one the pipeline used. The pipeline
        would then accept a file that the engine cannot open, and the error would come
        from two layers down with no sign of why. That happened once; hence this argument.
        """
        self.carriers = carriers if carriers is not None else CarrierRegistry()

    @abstractmethod
    def embed(self, request: EmbedRequest, context: RunContext) -> EmbedResult:
        """Hide the payload. Must not write the stego file before committing the state."""

    @abstractmethod
    def extract(self, request: ExtractRequest, context: RunContext) -> ExtractResult:
        """Recover the payload, or raise DecryptError with no detail about why."""

    def supports(self, domain: Domain) -> bool:
        return domain in self.supported_domains
