"""Key lifecycle: generate -> store -> load -> use -> rotate -> revoke -> destroy.

Applies to every kind of key, with no exceptions (PROJECT_STRUCTURE.md 4.6).
"""

from sieng.crypto.lifecycle.destroy import DestroyReport, destroy_session
from sieng.crypto.lifecycle.key_state import KeyState, ManagedKey

__all__ = [
    "DestroyReport",
    "KeyState",
    "ManagedKey",
    "destroy_session",
]
