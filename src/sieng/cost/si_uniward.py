"""SI-UNIWARD: use the rounding the encoder already had to make, and hide inside it.

Side information means holding the image as it was *before* JPEG quantised it. Every
coefficient then has an exact value that had to be rounded to an integer, and how close
that value sat to the halfway point says how arbitrary the choice was.

    e = 0     the encoder was certain, and moving the coefficient undoes a real decision
    e = 0.5   the encoder was choosing between two equally good values, so taking the
              other one is very nearly free

Cost is scaled by (1 - 2e), which is 1 at e = 0 and 0 at e = 0.5. Only the direction the
rounding went away from is offered; the other direction is wet, because moving that way
means paying for the rounding twice.

This is by far the strongest model here, and also the one that is easiest to misuse: the
precover must be the actual source of this exact JPEG. Feeding it a different image gives
a cost map that looks fine and is meaningless, so the shapes are checked and there is no
fallback path. requires_precover exists so the pipeline refuses rather than degrades.
"""

from typing import ClassVar

import numpy as np

from sieng.common.types import BLOCK_SIZE, DCT_DOMAIN, Domain
from sieng.cost._dct import as_blocks, to_spatial
from sieng.cost.base import WET, CostModel
from sieng.cost.juniward import REFERENCE_OFFSET, wavelet_costs
from sieng.cost.uerd import quant_table_of, unblock
from sieng.domain.plane import Array, Plane

# The largest a rounding error can be. At exactly this the scaled cost reaches zero, which
# base.py then lifts to its floor: free is not allowed, only very cheap.
MAX_ROUNDING_ERROR = 0.5


class SiUniwardCost(CostModel):
    """Side informed UNIWARD. Needs the unquantised DCT coefficients of the source image."""

    name: ClassVar[str] = "si_uniward"
    domain: ClassVar[Domain] = DCT_DOMAIN
    requires_precover: ClassVar[bool] = True

    def __init__(
        self,
        precover: Array | None = None,
        *,
        use_reference_offset: bool = True,
        block: int = BLOCK_SIZE,
    ) -> None:
        """precover holds the DCT coefficients before quantisation, at full precision."""
        self.precover = None if precover is None else np.asarray(precover, dtype=np.float64)
        self.offset = REFERENCE_OFFSET if use_reference_offset else 8
        self.block = block

    def compute(self, plane: Plane) -> tuple[Array, Array]:
        exact = self.require_precover(plane)
        quant = quant_table_of(plane, self.block)

        # The score comes from the precover, not the cover: it is the image the encoder
        # started from, and it has not yet lost anything to quantisation.
        spatial = to_spatial(exact, np.ones_like(quant), self.block)
        base = wavelet_costs(spatial, quant, plane.values.shape, self.offset, self.block)

        # The quantisation table describes one 8x8 block, so it has to be divided out
        # block by block. Dividing the whole plane by it would be a silent mis-scaling.
        scaled = unblock(as_blocks(exact, self.block) / quant, plane.values.shape, self.block)
        error = scaled - np.round(scaled)
        weight = base * (1.0 - np.abs(error) / MAX_ROUNDING_ERROR)

        # Cheap only towards the value the encoder rejected. Away from it, the change adds
        # to an error that was already paid, so it is not offered at all.
        rho_p1 = np.where(error > 0, weight, WET)
        rho_m1 = np.where(error < 0, weight, WET)
        return rho_p1, rho_m1

    def require_precover(self, plane: Plane) -> Array:
        """The precover, or a refusal. Never a guess and never a degraded run."""
        exact = self.precover if self.precover is not None else plane.meta.get("precover")
        if exact is None:
            raise ValueError(
                f"{self.name} needs the unquantised DCT coefficients of the source image "
                f"and none were given. Use juniward if the original is not available: "
                f"running side informed embedding without side information is not the "
                f"same algorithm with less accuracy, it is a different one."
            )
        exact = np.asarray(exact, dtype=np.float64)
        if exact.shape != plane.values.shape:
            raise ValueError(
                f"Precover shape {exact.shape} does not match the cover's "
                f"{plane.values.shape}. This is not the source of this JPEG."
            )
        return exact
