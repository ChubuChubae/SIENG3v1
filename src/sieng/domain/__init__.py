"""The shared data representation. Smallest package here, and the most important.

Plane is the bottleneck that lets JPEG and PNG share one cost, coder and crypto stack.
Nothing below this layer knows the word JPEG.

Freeze plane.py after Phase 2. Changing it touches every layer from 5 down (6.2).
"""

# TODO(skeleton): from sieng.domain.plane import Plane

# TODO(skeleton): __all__ = ["Plane"]
