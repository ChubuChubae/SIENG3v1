"""Turns files into numbers. The only layer that knows JPEG and PNG differ.

Phase 1 supports .jpg and .png only (PROJECT_STRUCTURE.md 1.6). Anything else is refused
by name, never guessed at and never quietly handled by a weaker method.
"""

from sieng.carrier.base import SNIFF_BYTES, Carrier
from sieng.carrier.detect import open_carrier, read_head, sniff
from sieng.carrier.registry import CarrierRegistry

__all__ = [
    "SNIFF_BYTES",
    "Carrier",
    "CarrierRegistry",
    "open_carrier",
    "read_head",
    "sniff",
]
