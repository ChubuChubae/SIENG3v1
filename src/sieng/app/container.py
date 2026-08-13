"""Composition root: the one place that wires implementations together.

Everything else knows only interfaces, so adding a carrier, cost model or engine
means editing this file and nothing else.

This file may import from any layer. That breaks the rule in PROJECT_CONTEXT.md 2.1
on purpose, because wiring is its whole job.
"""

from dataclasses import dataclass, field

from sieng.app.settings import load_settings


@dataclass
class Container:
    """The assembled system, handed to the ui and cli.

    Registries are plain dicts in Phase 0. Real classes arrive with 3.1, 6.1 and 8.1.
    """

    settings: object
    carriers: dict = field(default_factory=dict)
    costs: dict = field(default_factory=dict)
    engines: dict = field(default_factory=dict)

    def summary(self):
        """One-line status, e.g. "carriers=2 costs=3 engines=2 workspace=/home/u/.sieng"."""
        return (
            f"carriers={len(self.carriers)} costs={len(self.costs)} "
            f"engines={len(self.engines)} workspace={self.settings.workspace_dir}"
        )


def build_container(settings=None):
    """Assemble the system. Call once at startup and pass the container around."""
    container = Container(settings=settings or load_settings())

    # Phase 3.1 - carriers: JpegCarrier, PngCarrier.
    #   Only these two in Phase 1. Anything else must raise UnsupportedCarrierError,
    #   never guess and never fall back to a weaker method.
    # Phase 6.1 - costs: JUniwardCost (dct), UerdCost (dct baseline), HillCost (spatial).
    # Phase 8.1 - engines: JUniwardStcEngine, HillStcEngine.
    #   The ui builds its dropdown from this registry, so never hardcode engine names there.

    return container
