"""The ratchet state on disk: encrypted, versioned, and replaced atomically.

    +-------------------------------+--------+
    | magic  "SI3T"                 |    4 B |
    | version                       |    1 B |
    | argon2 parameters             |    9 B |
    | salt                          |   16 B |
    | nonce                         |   12 B |
    | ciphertext + tag              |    var |
    +-------------------------------+--------+

and inside the ciphertext:

    generation (8) | machine_id (16) | session_id (4) | chain_key (32)
    counter (3) | skipped count (2) | skipped [ctr(3) key(32)]... | consumed window

Two things here are not obvious.

**The consumed window is a window, not a bitmap of everything.** Replay protection needs to
know which counters have been used, and the counter space is twenty-four bits, so a full
bitmap would be two megabytes. It is also unnecessary: a counter more than `max_skip`
behind the current one is refused by RecvChain anyway, because its keys are long gone. So
only the last `max_skip` counters need tracking, which is 125 bytes at the default. The
window slides forward as the chain advances.

**Writing is temp, fsync, rename, fsync directory.** Each step is there for a failure:
without fsync on the temp file the rename can land before the contents; without fsync on
the directory the rename itself can be lost; without the rename at all a crash midway
leaves a truncated file that decrypts as nothing. Losing the state file means losing the
session, so the order matters more here than almost anywhere else in the project.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.aead import gcm_siv
from sieng.crypto.kdf import argon2, hkdf, labels
from sieng.crypto.ratchet import generation as gen

MAGIC: Final = b"SI3T"
VERSION: Final = 1

PARAMETER_FORMAT: Final = ">IIB"
PARAMETER_BYTES: Final = struct.calcsize(PARAMETER_FORMAT)
HEADER_FORMAT: Final = f">4sB{PARAMETER_BYTES}s"
HEADER_BYTES: Final = struct.calcsize(HEADER_FORMAT)

KEY_BYTES: Final = 32
COUNTER_BYTES: Final = 3
SKIPPED_ENTRY_BYTES: Final = COUNTER_BYTES + KEY_BYTES

# The default window, matching settings.max_ratchet_skip. 1000 bits is 125 bytes.
DEFAULT_WINDOW: Final = 1000


@dataclass
class RatchetState:
    """Everything needed to resume a session, as values."""

    session_id: bytes
    chain_key: bytes

    # K_hdr_session. Fixed for the whole session and stored because it cannot be recovered:
    # it is derived from `ss`, and `ss` is destroyed once CK[0] and this key exist
    # (FORMAT_SPEC.md 2.3). Without it on disk the receiver cannot unwhiten a header after
    # a restart, and the header is the only way to learn the counter. Found by assembling
    # the engine in 8.3, which is the first thing that needed both halves at once.
    header_key: bytes = b""

    counter: int = 0
    generation: int = 0
    machine_id: bytes = b""
    skipped: dict[int, bytes] = field(default_factory=dict)
    consumed: set[int] = field(default_factory=set)
    window: int = DEFAULT_WINDOW

    def __post_init__(self) -> None:
        if len(self.session_id) != 4:
            raise CryptoError(f"Session id must be 4 bytes, got {len(self.session_id)}")
        if len(self.chain_key) != KEY_BYTES:
            raise CryptoError(f"Chain key must be {KEY_BYTES} bytes, got {len(self.chain_key)}")
        if self.header_key and len(self.header_key) != KEY_BYTES:
            raise CryptoError(f"Header key must be {KEY_BYTES} bytes, got {len(self.header_key)}")
        if not self.machine_id:
            self.machine_id = gen.machine_id()

    def window_base(self) -> int:
        """The oldest counter the consumed window still remembers."""
        return max(0, self.counter - self.window)

    def prune(self) -> None:
        """Forget what can no longer be replayed.

        A counter below the window is already refused by RecvChain, because its message
        key was dropped from the skipped pool. Keeping it in the consumed set would grow
        the file forever for no protection.
        """
        base = self.window_base()
        self.consumed = {c for c in self.consumed if c >= base}
        self.skipped = {c: k for c, k in self.skipped.items() if c >= base}

    def serialise(self) -> bytes:
        """The plaintext that goes inside the AEAD."""
        self.prune()
        skipped = sorted(self.skipped.items())
        if len(skipped) > 0xFFFF:
            raise CryptoError(f"Too many skipped keys to record: {len(skipped)}")

        body = bytearray()
        body += self.generation.to_bytes(gen.GENERATION_BYTES, "big")
        body += self.machine_id
        body += self.session_id
        body += self.chain_key
        body += self.header_key.ljust(KEY_BYTES, b"\x00")
        body += self.counter.to_bytes(COUNTER_BYTES, "big")
        body += len(skipped).to_bytes(2, "big")
        for counter, key in skipped:
            body += counter.to_bytes(COUNTER_BYTES, "big") + key
        body += struct.pack(">I", self.window)
        body += _pack_window(self.consumed, self.window_base(), self.window)
        return bytes(body)

    @classmethod
    def deserialise(cls, raw: bytes) -> "RatchetState":
        """Read the plaintext back. Only ever called on bytes the AEAD has authenticated.

        That is why the checks here are for our own bugs rather than for attacks: nothing
        reaches this function unless it decrypted, and anything that decrypted was written
        by us.
        """
        view = memoryview(raw)
        offset = 0

        def take(n: int) -> bytes:
            nonlocal offset
            if offset + n > len(view):
                raise CryptoError("Ratchet state is truncated")
            chunk = bytes(view[offset : offset + n])
            offset += n
            return chunk

        generation = int.from_bytes(take(gen.GENERATION_BYTES), "big")
        machine = take(gen.MACHINE_ID_BYTES)
        session_id = take(4)
        chain_key = take(KEY_BYTES)
        header_key = take(KEY_BYTES)
        counter = int.from_bytes(take(COUNTER_BYTES), "big")

        skipped: dict[int, bytes] = {}
        for _ in range(int.from_bytes(take(2), "big")):
            entry_counter = int.from_bytes(take(COUNTER_BYTES), "big")
            skipped[entry_counter] = take(KEY_BYTES)

        window = struct.unpack(">I", take(4))[0]
        base = max(0, counter - window)
        consumed = _unpack_window(take(_window_bytes(window)), base)

        return cls(
            session_id=session_id,
            chain_key=chain_key,
            header_key=header_key,
            counter=counter,
            generation=generation,
            machine_id=machine,
            skipped=skipped,
            consumed=consumed,
            window=window,
        )


def save(path: Path, state: RatchetState, password: bytes, **costs: int) -> None:
    """Encrypt and write the state, replacing whatever was there atomically.

    The four steps are load bearing:
      1. write a temporary file
      2. fsync it, so the bytes are on the disk before anything points at them
      3. rename over the target, which is atomic on every filesystem this runs on
      4. fsync the directory, so the rename itself survives a power loss

    Skipping any of them turns a crash into a lost session rather than a lost message.
    """
    settings = {**argon2.current_parameters(), **costs}
    salt = argon2.new_salt()
    key = argon2.derive_key(password, salt, **settings)
    header = _header(settings)
    nonce = _nonce_for(key, salt)
    blob = header + salt + nonce + gcm_siv.seal(key, nonce, state.serialise(), header + salt)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix(path.suffix + ".partial")

    with scratch.open("wb") as handle:
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())
    scratch.replace(path)
    _fsync_directory(path.parent)


def load(path: Path, password: bytes) -> RatchetState:
    """Read and decrypt the state. Raises DecryptError for a wrong password."""
    raw = Path(path).read_bytes()
    minimum = HEADER_BYTES + argon2.SALT_BYTES + gcm_siv.NONCE_BYTES + gcm_siv.TAG_BYTES
    if len(raw) < minimum:
        raise CryptoError(f"Ratchet state file is {len(raw)} bytes, too short to be one")

    magic, version, packed = struct.unpack(HEADER_FORMAT, raw[:HEADER_BYTES])
    if magic != MAGIC:
        raise CryptoError(f"This is not a SIENG3 ratchet state: expected {MAGIC!r} at the start")
    if version != VERSION:
        raise CryptoError(f"Ratchet state version {version} is not supported, expected {VERSION}")

    time_cost, memory_cost_kib, lanes = struct.unpack(PARAMETER_FORMAT, packed)
    body = raw[HEADER_BYTES:]
    salt = body[: argon2.SALT_BYTES]
    nonce = body[argon2.SALT_BYTES : argon2.SALT_BYTES + gcm_siv.NONCE_BYTES]
    ciphertext = body[argon2.SALT_BYTES + gcm_siv.NONCE_BYTES :]

    key = argon2.derive_key(
        password, salt, time_cost=time_cost, memory_cost_kib=memory_cost_kib, lanes=lanes
    )
    if nonce != _nonce_for(key, salt):
        raise DecryptError
    aad = raw[:HEADER_BYTES] + salt
    return RatchetState.deserialise(gcm_siv.open_(key, nonce, ciphertext, aad))


def exists(path: Path) -> bool:
    return Path(path).exists()


def _header(settings: dict[str, int]) -> bytes:
    packed = struct.pack(
        PARAMETER_FORMAT, settings["time_cost"], settings["memory_cost_kib"], settings["lanes"]
    )
    return struct.pack(HEADER_FORMAT, MAGIC, VERSION, packed)


def _nonce_for(key: bytes, salt: bytes) -> bytes:
    """Derived, not stored. A fresh salt per save means a fresh key, so it never repeats."""
    return hkdf.expand(key, labels.STATE_WRAP + salt, gcm_siv.NONCE_BYTES)


def _fsync_directory(directory: Path) -> None:
    """Make the rename itself durable.

    Not available on Windows, where opening a directory is not allowed. The rename is
    still atomic there; what is lost is the guarantee that it survives a power cut, and
    that is a smaller gap than not renaming at all.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _window_bytes(window: int) -> int:
    return (window + 7) // 8


def _pack_window(consumed: set[int], base: int, window: int) -> bytes:
    """The consumed counters in [base, base + window) as a bitmap."""
    bits = bytearray(_window_bytes(window))
    for counter in consumed:
        offset = counter - base
        if 0 <= offset < window:
            bits[offset // 8] |= 1 << (offset % 8)
    return bytes(bits)


def _unpack_window(bits: bytes, base: int) -> set[int]:
    return {base + i for i in range(len(bits) * 8) if bits[i // 8] & (1 << (i % 8))}
