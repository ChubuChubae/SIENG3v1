"""Plane: the one representation every layer below carrier agrees on.

This is the narrow waist of the whole system. A JPEG hands over quantized DCT
coefficients, a PNG hands over pixels, and from here down nothing knows the difference.
cost, coder and crypto only ever see an array and a mask.

FROZEN after Phase 2. Changing this file touches every layer from 5 downwards
(PROJECT_STRUCTURE.md 6.2), so a change here needs a deliberate decision, not a patch.

This layer runs under mypy --strict, so annotations are complete here even though the
rest of the project keeps them light (PROJECT_CONTEXT.md 2.2.1).
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[Any]
BoolArray = npt.NDArray[np.bool_]
IndexArray = npt.NDArray[np.int64]


@dataclass
class Plane:
    """One channel of changeable numbers plus the mask of which ones may move.

    values      int16 for DCT coefficients, uint8 for spatial samples
    changeable  bool, same shape as values. False means the element is wet.
    meta        carrier specific extras: qtable, component id, block grid, subsampling
    """

    values: Array
    changeable: BoolArray
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.values.shape != self.changeable.shape:
            raise ValueError(
                f"Plane shape mismatch: values{self.values.shape} vs "
                f"changeable{self.changeable.shape}. They must describe the same grid."
            )
        if self.changeable.dtype != np.bool_:
            raise ValueError(
                f"Plane.changeable must be a boolean mask, got dtype {self.changeable.dtype}"
            )

    def n_changeable(self) -> int:
        """How many elements may actually be modified. This is the real capacity base."""
        return int(np.count_nonzero(self.changeable))

    def flatten(self) -> tuple[Array, IndexArray]:
        """Return the changeable values as a 1-D array plus the index that puts them back.

        The index is a flat index into values, so unflatten() does not need the shape.
        """
        index: IndexArray = np.flatnonzero(self.changeable).astype(np.int64)
        flat: Array = self.values.reshape(-1)[index].copy()
        return flat, index

    def unflatten(self, flat: Array, index: IndexArray) -> None:
        """Write a 1-D array of new values back into the positions given by index."""
        if flat.shape != index.shape:
            raise ValueError(
                f"Cannot unflatten: {flat.size} values for {index.size} positions. "
                f"The array must come from the matching flatten() call."
            )
        self.values.reshape(-1)[index] = flat

    def copy(self) -> "Plane":
        """Deep copy. Used when a cost model or an experiment must not touch the original."""
        return Plane(self.values.copy(), self.changeable.copy(), dict(self.meta))
