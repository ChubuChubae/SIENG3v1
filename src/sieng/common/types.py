"""Names that several layers share, kept here so nobody redefines them slightly differently.

The constants are Final so mypy narrows them to their literal type. Without that,
`domain = SPATIAL_DOMAIN` in a carrier is just a str and fails the Literal in the base class.
"""

from typing import Final, Literal

# What kind of numbers a carrier exposes. Phase 1 has these two only.
Domain = Literal["dct", "spatial"]

# How much a carrier can be trusted for real hiding. Phase 1 ships only "strong",
# the other two exist so the warning path is ready before Phase 2 adds weaker carriers.
SecurityTier = Literal["strong", "weak", "none"]

# Payload rate unit. bpnzAC counts bits per non-zero AC coefficient and is what the
# steganography literature reports, so results stay comparable.
RateUnit = Literal["bpnzAC", "bpp", "bits"]

DCT_DOMAIN: Final = "dct"
SPATIAL_DOMAIN: Final = "spatial"

STRONG_TIER: Final = "strong"

# JPEG works on 8x8 blocks. The DC coefficient sits at index (0, 0) of each block.
BLOCK_SIZE: Final = 8
