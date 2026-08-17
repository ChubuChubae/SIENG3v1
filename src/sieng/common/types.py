"""Names that several layers share, kept here so nobody redefines them slightly differently."""

from typing import Literal

# What kind of numbers a carrier exposes. Phase 1 has these two only.
Domain = Literal["dct", "spatial"]

# How much a carrier can be trusted for real hiding. Phase 1 ships only "strong",
# the other two exist so the warning path is ready before Phase 2 adds weaker carriers.
SecurityTier = Literal["strong", "weak", "none"]

# Payload rate unit. bpnzAC counts bits per non-zero AC coefficient and is what the
# steganography literature reports, so results stay comparable.
RateUnit = Literal["bpnzAC", "bpp", "bits"]

DCT_DOMAIN = "dct"
SPATIAL_DOMAIN = "spatial"

# JPEG works on 8x8 blocks. The DC coefficient sits at index (0, 0) of each block.
BLOCK_SIZE = 8
