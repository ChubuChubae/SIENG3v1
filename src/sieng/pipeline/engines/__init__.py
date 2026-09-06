"""One engine is one working combination of carrier, cost model and coder.

Engines assemble; they do not calculate. Arithmetic that lives in an engine is arithmetic
no test below it covers.
"""

from sieng.pipeline.engines.base import (
    EmbedRequest,
    EmbedResult,
    Engine,
    ExtractRequest,
    ExtractResult,
)

__all__ = [
    "EmbedRequest",
    "EmbedResult",
    "Engine",
    "ExtractRequest",
    "ExtractResult",
]
