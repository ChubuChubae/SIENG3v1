"""Syndrome coding: turn a cost map and a message into the cheapest set of changes.

This layer knows nothing about formats and nothing about crypto. It sees an array of
numbers, two cost arrays and a bit string, and that is the whole of its world.
"""

from sieng.coder.base import DEFAULT_HEIGHT, MAX_HEIGHT, MIN_HEIGHT, build_h_hat, flip_costs
from sieng.coder.simulator import (
    binary_bound,
    coding_loss,
    simulate_embedding,
    ternary_bound,
)
from sieng.coder.stc import distortion, embed, extract

__all__ = [
    "DEFAULT_HEIGHT",
    "MAX_HEIGHT",
    "MIN_HEIGHT",
    "binary_bound",
    "build_h_hat",
    "coding_loss",
    "distortion",
    "embed",
    "extract",
    "flip_costs",
    "simulate_embedding",
    "ternary_bound",
]
