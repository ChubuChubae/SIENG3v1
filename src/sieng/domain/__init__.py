"""The shared representation. The smallest package here and the most important one.

Plane is the narrow waist that lets JPEG and PNG share one cost, coder and crypto stack.
Nothing below this layer knows the word JPEG.

FROZEN after Phase 2. Editing plane.py touches every layer from 5 downwards (6.2).
"""

from sieng.domain.capacity import (
    HEADER_BITS,
    bits_from_bpnzac,
    bpnzac_from_bits,
    check_capacity,
    max_payload_bits,
)
from sieng.domain.plane import Plane
from sieng.domain.selection import (
    build_changeable_mask,
    count_nonzero_ac,
    inverse_permute,
    permute,
)

__all__ = [
    "HEADER_BITS",
    "Plane",
    "bits_from_bpnzac",
    "bpnzac_from_bits",
    "build_changeable_mask",
    "check_capacity",
    "count_nonzero_ac",
    "inverse_permute",
    "max_payload_bits",
    "permute",
]
