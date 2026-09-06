"""The ratchet. One set of keys per message, and the old ones destroyed as it goes.

chain.py holds the derivation, which is pure and has no idea a disk exists. The state file
that survives a restart is a separate concern and a separate set of failure modes, and it
lives in its own modules.
"""

from sieng.crypto.ratchet.chain import (
    MAX_COUNTER,
    MessageKeys,
    RecvChain,
    SendChain,
    advance,
    derive_message_key,
    header_session_key,
    root_chain_key,
)

__all__ = [
    "MAX_COUNTER",
    "MessageKeys",
    "RecvChain",
    "SendChain",
    "advance",
    "derive_message_key",
    "header_session_key",
    "root_chain_key",
]
