"""Distortion models. They answer one question: which value is safest to change?

Low cost means a safe spot, such as edges and busy texture.
High cost means a risky one, such as flat sky.

Nothing in here sees the payload or a key, so the same cover always scores the same way.
"""

from sieng.cost.base import WET, CostModel, CostRegistry
from sieng.cost.hill import HillCost
from sieng.cost.juniward import JUniwardCost
from sieng.cost.legacy_texture import LegacyTextureCost
from sieng.cost.si_uniward import SiUniwardCost
from sieng.cost.uerd import UerdCost

__all__ = [
    "WET",
    "CostModel",
    "CostRegistry",
    "HillCost",
    "JUniwardCost",
    "LegacyTextureCost",
    "SiUniwardCost",
    "UerdCost",
]
