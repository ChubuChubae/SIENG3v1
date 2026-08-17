"""Which carriers exist. The ui reads this instead of keeping its own list.

Registration happens in app/container.py, the one place that knows about implementations.
"""

from sieng.carrier.base import Carrier
from sieng.common.types import Domain


class CarrierRegistry:
    """Maps suffixes and magic bytes to carrier classes."""

    def __init__(self) -> None:
        self._by_suffix: dict[str, type[Carrier]] = {}
        self._registered: list[type[Carrier]] = []

    def register(self, carrier: type[Carrier]) -> None:
        """Add a carrier. Two carriers claiming the same suffix is a wiring bug, not a fallback."""
        for suffix in carrier.suffixes:
            existing = self._by_suffix.get(suffix)
            if existing is not None and existing is not carrier:
                raise ValueError(
                    f"Suffix '{suffix}' is already registered to {existing.__name__}, "
                    f"{carrier.__name__} cannot take it as well. "
                    f"Two carriers for one suffix means the choice would be arbitrary."
                )
            self._by_suffix[suffix] = carrier
        if carrier not in self._registered:
            self._registered.append(carrier)

    def all(self) -> list[type[Carrier]]:
        """Every registered carrier, in registration order."""
        return list(self._registered)

    def for_domain(self, domain: Domain) -> list[type[Carrier]]:
        """Carriers working in one domain. The ui builds its dropdown from this."""
        return [c for c in self._registered if c.domain == domain]

    def suffixes(self) -> list[str]:
        """Every suffix that can be embedded in, sorted. Shown in file dialogs."""
        return sorted(self._by_suffix)

    def match_magic(self, head: bytes) -> type[Carrier] | None:
        """First carrier that recognises these bytes, or None."""
        for carrier in self._registered:
            if carrier.sniff(head):
                return carrier
        return None
