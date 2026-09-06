"""The ratchet. One set of keys per message, and the old ones destroyed as it goes.

Two halves with different failure modes, kept apart:

    chain          the derivation. Pure, has no idea a disk exists, fully testable.
    state file     the part that survives a restart, and therefore the part that can be
                   restored from a backup, copied to another machine, or half written by
                   a crash. session.py fixes the order those operations happen in.
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
from sieng.crypto.ratchet.generation import RollbackError, machine_id
from sieng.crypto.ratchet.rollback_guard import GuardReport, inspect, quarantine, require_forward
from sieng.crypto.ratchet.session import (
    create,
    header_material,
    mark_received,
    opened,
    receive,
    send,
    start,
)
from sieng.crypto.ratchet.state_store import RatchetState

__all__ = [
    "MAX_COUNTER",
    "GuardReport",
    "MessageKeys",
    "RatchetState",
    "RecvChain",
    "RollbackError",
    "SendChain",
    "advance",
    "create",
    "derive_message_key",
    "header_material",
    "header_session_key",
    "inspect",
    "machine_id",
    "mark_received",
    "opened",
    "quarantine",
    "receive",
    "require_forward",
    "root_chain_key",
    "send",
    "start",
]
