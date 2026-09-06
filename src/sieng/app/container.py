"""Composition root: the one place that wires implementations together.

Everything else knows only interfaces, so adding a carrier, cost model or engine
means editing this file and nothing else.

This file may import from any layer. That breaks the rule in PROJECT_CONTEXT.md 2.1
on purpose, because wiring is its whole job.
"""

from dataclasses import dataclass, field

from sieng.app.settings import load_settings
from sieng.carrier.image.jpeg import JpegCarrier
from sieng.carrier.image.png import PngCarrier
from sieng.carrier.registry import CarrierRegistry
from sieng.cost.base import CostRegistry
from sieng.cost.hill import HillCost
from sieng.cost.juniward import JUniwardCost
from sieng.cost.legacy_texture import LegacyTextureCost
from sieng.cost.si_uniward import SiUniwardCost
from sieng.cost.uerd import UerdCost


@dataclass
class Container:
    """The assembled system, handed to the ui and cli.

    engines stays a plain dict until its registry arrives with 8.1.
    """

    settings: object
    carriers: CarrierRegistry = field(default_factory=CarrierRegistry)
    costs: CostRegistry = field(default_factory=CostRegistry)
    engines: dict = field(default_factory=dict)

    def summary(self):
        """One line status.

        e.g. "carriers=1 (.png) costs=0 engines=0 workspace=/home/u/.sieng/workspace"
        """
        suffixes = ", ".join(self.carriers.suffixes()) or "none"
        return (
            f"carriers={len(self.carriers.all())} ({suffixes}) "
            f"costs={len(self.costs.names())} engines={len(self.engines)} "
            f"workspace={self.settings.workspace_dir}"
        )


def build_container(settings=None):
    """Assemble the system. Call once at startup and pass the container around."""
    container = Container(settings=settings or load_settings())

    container.carriers.register(JpegCarrier)
    container.carriers.register(PngCarrier)

    for model in (JUniwardCost, UerdCost, SiUniwardCost, HillCost, LegacyTextureCost):
        container.costs.register(model)

    # Phase 8.1 - engines: JUniwardStcEngine, HillStcEngine
    #   The ui builds its dropdown from these registries, so never hardcode names there.

    return container
