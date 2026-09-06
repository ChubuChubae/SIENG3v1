"""The contract every cost model honours, plus the rules that apply to all of them.

A cost model answers one question per element: how much does changing this by +1 or by -1
give the game away? Low means safe, infinite means do not touch. It never sees the payload
and never sees a key, so the same cover always produces the same cost map. That is not a
convenience, it is what makes an experiment reproducible.

The wet mask is applied here rather than in each model, so a model that forgets it cannot
silently leak changes into the DC coefficient or into a zero.

This file runs under mypy --strict, so annotations are complete. The models themselves do
not: they are numpy arithmetic from top to bottom (PROJECT_CONTEXT.md 2.2.1).
"""

from abc import ABC, abstractmethod
from typing import ClassVar

import numpy as np

from sieng.common.types import DCT_DOMAIN, Domain
from sieng.domain.plane import Array, Plane

# Unmovable. The coder reads this straight through to the trellis, where an infinite edge
# is simply never taken. A large finite number would be taken when nothing else fits.
WET = float(np.inf)

# The reference implementations cap at 1e13 instead of using infinity, so a cost above
# this came from a division by an almost flat neighbourhood and means the same thing.
WET_THRESHOLD = 1e13

# No cost may be exactly zero. A free change makes the simulator's lambda meaningless and
# lets one coefficient absorb the whole payload.
MIN_COST = 1e-10

# JPEG coefficients are stored in 12 bits. Pushing one past the edge would not survive
# the entropy coder, so the outermost values may only move inwards.
COEFF_LIMIT = 1023


class CostModel(ABC):
    """Turns a Plane into two cost arrays, one per direction.

    The two are separate because side informed models are asymmetric: SI-UNIWARD knows
    which way the original rounding went and makes that direction much cheaper. For the
    symmetric models both arrays are the same object's values.
    """

    name: ClassVar[str]
    domain: ClassVar[Domain]

    # True means the model needs the original uncompressed image as well as the cover.
    # Such a model must refuse to run without it rather than fall back to a weaker score.
    requires_precover: ClassVar[bool] = False

    @abstractmethod
    def compute(self, plane: Plane) -> tuple[Array, Array]:
        """Raw costs for +1 and for -1, same shape as plane.values. No masking here."""

    def costs(self, plane: Plane) -> tuple[Array, Array]:
        """Costs the coder should use: the model's numbers with every rule applied.

        Call this, not compute(). This is where the wet mask, the coefficient limit and
        the floor are enforced, so no model can skip them.
        """
        self.check_domain(plane)
        rho_p1, rho_m1 = self.compute(plane)
        rho_p1 = self.sanitise(rho_p1, plane)
        rho_m1 = self.sanitise(rho_m1, plane)
        if self.domain == DCT_DOMAIN:
            rho_p1 = np.where(plane.values >= COEFF_LIMIT, WET, rho_p1)
            rho_m1 = np.where(plane.values <= -COEFF_LIMIT, WET, rho_m1)
        return rho_p1, rho_m1

    def check_domain(self, plane: Plane) -> None:
        """A DCT model on pixels produces numbers, and every one of them is wrong."""
        if plane.values.ndim != 2:
            raise ValueError(f"{self.name} needs a 2-D plane, got {plane.values.ndim} dimensions")

    def sanitise(self, rho: Array, plane: Plane) -> Array:
        """Apply the shared rules: right shape, no nan, a floor, and the wet mask on top."""
        rho = np.asarray(rho, dtype=np.float64)
        if rho.shape != plane.values.shape:
            raise ValueError(
                f"{self.name} returned costs of shape {rho.shape} for a plane of shape "
                f"{plane.values.shape}. They must describe the same elements."
            )
        rho = np.where(np.isnan(rho) | (rho > WET_THRESHOLD), WET, rho)
        rho = np.maximum(rho, MIN_COST)
        masked: Array = np.where(plane.changeable, rho, WET)
        return masked


class CostRegistry:
    """Which cost models exist. The ui and the research runner read this, not a hardcoded list.

    Registration happens in app/container.py, the one place that knows about implementations.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, type[CostModel]] = {}

    def register(self, model: type[CostModel]) -> None:
        """Add a model. Two models under one name is a wiring bug, not a fallback."""
        existing = self._by_name.get(model.name)
        if existing is not None and existing is not model:
            raise ValueError(
                f"Cost model name '{model.name}' is already registered to "
                f"{existing.__name__}, {model.__name__} cannot take it as well."
            )
        self._by_name[model.name] = model

    def get(self, name: str) -> type[CostModel]:
        """Look a model up by name, or say which names exist."""
        model = self._by_name.get(name)
        if model is None:
            raise KeyError(f"No cost model named '{name}'. Registered: {', '.join(self.names())}")
        return model

    def names(self) -> list[str]:
        """Every registered name, sorted. This is what the command line accepts."""
        return sorted(self._by_name)

    def for_domain(self, domain: Domain) -> list[type[CostModel]]:
        """Models that work on this kind of plane. JPEG and PNG cannot share one."""
        return [m for m in self._by_name.values() if m.domain == domain]
