"""Which engines exist, and whether the one asked for can be used on this file.

The check that matters is `resolve`. A user picks an engine from a list and a file from a
dialog, and nothing stops them picking `juniward_stc` for a PNG. Caught here, before the
file is opened, that is a clear message. Caught later it is a crash somewhere in the cost
layer with a message about array shapes.

Registration happens in app/container.py, the one place that knows about implementations.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from sieng.common.errors import IncompatibleEngineError
from sieng.common.types import Domain
from sieng.pipeline.engines.base import Engine


class EngineRegistry:
    """Maps engine ids to implementations, and answers what works with what."""

    def __init__(self) -> None:
        self._engines: dict[str, type[Engine]] = {}

    def register(self, engine: type[Engine]) -> None:
        """Add an engine. Two under one id is a wiring bug, not a fallback."""
        existing = self._engines.get(engine.engine_id)
        if existing is not None and existing is not engine:
            raise ValueError(
                f"Engine id '{engine.engine_id}' is already registered to "
                f"{existing.__name__}, {engine.__name__} cannot take it as well."
            )
        self._engines[engine.engine_id] = engine

    def get(self, engine_id: str) -> type[Engine]:
        """Look up by id, or say which ids exist."""
        engine = self._engines.get(engine_id)
        if engine is None:
            known = ", ".join(self.ids()) or "none, which means app/container.py registered nothing"
            raise KeyError(f"No engine named '{engine_id}'. Registered: {known}")
        return engine

    def resolve(self, engine_id: str, domain: Domain) -> type[Engine]:
        """The engine for this id, if it can be used on a carrier of this domain.

        Raises IncompatibleEngineError rather than falling back to something that would
        work. Quietly substituting an engine would mean the user's result is not the one
        they asked for, and in a research setting that is worse than a failure.
        """
        engine = self.get(engine_id)
        if domain not in engine.supported_domains:
            supported = ", ".join(engine.supported_domains)
            usable = ", ".join(e.engine_id for e in self.for_domain(domain)) or "none"
            raise IncompatibleEngineError(
                f"Engine '{engine_id}' works on {supported} carriers, but this file is "
                f"{domain}. Engines that would work here: {usable}."
            )
        return engine

    def ids(self) -> list[str]:
        """Every registered id, sorted. This is what the command line accepts."""
        return sorted(self._engines)

    def for_domain(self, domain: Domain) -> list[type[Engine]]:
        """Engines usable with this kind of carrier. The ui builds its dropdown from this."""
        return [e for e in self._engines.values() if domain in e.supported_domains]

    def all(self) -> list[type[Engine]]:
        return list(self._engines.values())

    def __len__(self) -> int:
        return len(self._engines)
