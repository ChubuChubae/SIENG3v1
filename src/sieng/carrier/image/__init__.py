"""Image carriers. Phase 1 has jpeg and png.

Phase 2: bmp, tiff and lossless webp. All three are spatial and reuse HillCost as it is,
so they are mostly a new file each rather than new machinery.
"""

from sieng.carrier.image.jpeg import JpegCarrier
from sieng.carrier.image.png import PngCarrier

__all__ = ["JpegCarrier", "PngCarrier"]
