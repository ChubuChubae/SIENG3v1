"""Orchestration. The only layer that sees the whole system at once.

Nothing here does arithmetic. Every step is a call into a layer that has its own tests,
and the value this layer adds is the order those calls happen in, which is a security
property (PROJECT_STRUCTURE.md 2.3 and 2.4).

Note the asymmetry between the two entry points. `run_embed` reports its failures in
detail, because the person embedding owns the inputs and needs to fix them. `run_extract`
reports one indistinguishable error for anything about the file, because a distinguishable
one turns the program into a detector.
"""

from sieng.pipeline.context import Cancelled, CancelToken, RunContext
from sieng.pipeline.embed import run_embed
from sieng.pipeline.extract import holds_a_message, run_extract
from sieng.pipeline.registry import EngineRegistry
from sieng.pipeline.session import create_session, join_session

__all__ = [
    "CancelToken",
    "Cancelled",
    "EngineRegistry",
    "RunContext",
    "create_session",
    "holds_a_message",
    "join_session",
    "run_embed",
    "run_extract",
]
