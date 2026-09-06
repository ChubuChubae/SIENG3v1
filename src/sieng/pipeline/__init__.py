"""Orchestration. The only layer that sees the whole system at once.

Nothing here does arithmetic. Every step is a call into a layer that has its own tests,
and the value this layer adds is the order those calls happen in, which is a security
property (PROJECT_STRUCTURE.md 2.3 and 2.4).
"""

from sieng.pipeline.context import Cancelled, CancelToken, RunContext
from sieng.pipeline.registry import EngineRegistry

__all__ = [
    "CancelToken",
    "Cancelled",
    "EngineRegistry",
    "RunContext",
]
