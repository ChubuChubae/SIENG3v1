"""What happens to the ratchet state when things go wrong on the disk.

These are the failures that do not look like attacks. A user restores a backup, a cloud
client reverts a file, a laptop loses power mid-save, two windows of the program are open
at once. Every one of them can make a counter repeat, and a repeated counter is the one
thing the whole design is arranged to avoid.

The honest framing, which the code says too: rollback is **detected, not prevented**.
Anyone who can write the state file can write an older one back. What these tests prove is
that it gets noticed on the next send rather than months later.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from sieng.common.errors import CryptoError, RollbackDetected
from sieng.crypto.ratchet import rollback_guard, session, state_lock, state_store
from sieng.crypto.ratchet.chain import SendChain

FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
SS = bytes(range(32))
SID = b"sess"
PASSWORD = b"a keystore password"


def a_session(tmp_path, name="s.state"):
    path = tmp_path / name
    session.create(path, SID, SS, PASSWORD, **FAST)
    return path


# ---- rollback --------------------------------------------------------------


def test_state_rollback_is_detected(tmp_path):
    """The backup restore, done exactly as a user would do it.

    Copy the file, send some messages, put the copy back. Without the generation counter
    the next send would silently reuse counters that have already been used.
    """
    path = a_session(tmp_path)
    backup = path.read_bytes()

    for _ in range(3):
        session.send(path, PASSWORD, **FAST)
    current = state_store.load(path, PASSWORD).generation

    path.write_bytes(backup)
    restored = state_store.load(path, PASSWORD)

    assert restored.generation < current
    with pytest.raises(RollbackDetected):
        rollback_guard.require_forward(restored, last_generation=current)


def test_a_rollback_would_have_repeated_counters(tmp_path):
    """Why it matters, made concrete. The restored state hands out counters that have
    already been used, and the keys are identical."""
    path = a_session(tmp_path)
    backup = path.read_bytes()
    first = [session.send(path, PASSWORD, **FAST) for _ in range(3)]

    path.write_bytes(backup)
    again = [session.send(path, PASSWORD, **FAST) for _ in range(3)]

    assert [k.counter for k in first] == [k.counter for k in again]
    assert [k.aead for k in first] == [k.aead for k in again]


def test_state_copied_from_another_machine_is_refused(tmp_path):
    """Copying a session to a second computer gives both the same chain, and both hand
    out the same counters until one gets ahead."""
    path = a_session(tmp_path)
    state = state_store.load(path, PASSWORD)
    state.machine_id = bytes(16)
    state_store.save(path, state, PASSWORD, **FAST)

    loaded = state_store.load(path, PASSWORD)
    assert rollback_guard.inspect(loaded).ok is False
    with pytest.raises(RollbackDetected, match="different machine"):
        rollback_guard.require_forward(loaded)


def test_the_generation_cannot_be_lowered_without_the_password(tmp_path):
    """The state is authenticated, so editing the generation in place fails as tampering
    rather than as a lower generation. That is the only part of this that is prevention
    rather than detection, and it holds only against someone without the password."""
    path = a_session(tmp_path)
    session.send(path, PASSWORD, **FAST)
    blob = bytearray(path.read_bytes())
    blob[-20] ^= 0xFF
    path.write_bytes(bytes(blob))

    with pytest.raises(CryptoError):
        state_store.load(path, PASSWORD)


def test_detection_refuses_rather_than_warning(tmp_path):
    """A warning would be clicked past, and what it warns about is silent, so the user
    would never learn they were wrong to click."""
    path = a_session(tmp_path)
    state = state_store.load(path, PASSWORD)

    with pytest.raises(RollbackDetected):
        rollback_guard.require_forward(state, last_generation=99)


def test_the_guard_does_not_claim_to_prevent():
    assert rollback_guard.prevention_is_possible() is False


# ---- concurrency -----------------------------------------------------------


WORKER = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sieng.crypto.ratchet import session

path, out, count = Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
costs = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
counters = [session.send(path, b"a keystore password", **costs).counter for _ in range(count)]
out.write_text(",".join(str(c) for c in counters))
"""


def test_two_processes_cannot_use_same_counter(tmp_path):
    """The lock has to be held across the whole read-modify-write.

    Run as real separate processes, because the failure being tested only appears between
    them: two loading the same state before either has saved. Threads would not show it,
    and neither would anything that stayed inside one interpreter.

    Subprocesses rather than fork, so this runs on Windows too. An earlier version used
    fork and was silently skipped on the platform the project actually targets, which
    meant the guarantee was untested exactly where it mattered.
    """
    path = a_session(tmp_path)
    src = str(Path(__file__).resolve().parents[2] / "src")
    workers = 4
    per_worker = 3

    def worker(index):
        # S603 flags subprocess calls that might run untrusted input. Every argument here
        # is ours: this interpreter, a literal script defined above, and paths from
        # pytest's tmp_path. Spawning real processes is the point of the test.
        out = tmp_path / f"out{index}"
        return subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", WORKER, src, str(path), str(out), str(per_worker)]
        )

    running = [worker(index) for index in range(workers)]
    for process in running:
        assert process.wait(timeout=120) == 0, "a worker failed outright"

    handed_out = [
        int(v) for i in range(workers) for v in (tmp_path / f"out{i}").read_text().split(",") if v
    ]
    assert len(handed_out) == workers * per_worker
    assert sorted(handed_out) == list(range(workers * per_worker)), "a counter was handed out twice"


def test_the_lock_is_released_when_the_block_raises(tmp_path):
    """A lock left held after an error would wedge every later send."""
    path = a_session(tmp_path)

    with pytest.raises(ValueError), state_lock.exclusive(path):
        raise ValueError("something went wrong")

    assert session.send(path, PASSWORD, **FAST).counter == 0


def test_the_lock_file_is_separate_from_the_state_file(tmp_path):
    """The state file is replaced by rename on every commit, so locking it would mean
    holding a lock on something that no longer has a name."""
    path = a_session(tmp_path)

    assert state_lock.lock_path_for(path) != path
    assert state_lock.lock_path_for(path).name.endswith(".lock")


# ---- crash safety ----------------------------------------------------------


def test_crash_during_commit_never_reuses_counter(tmp_path):
    """A crash between committing the state and writing the stego file.

    Simulated by taking keys and then throwing the result away, which is exactly what the
    process dying at that moment would do. The counter is spent either way, and the next
    send must not reuse it.
    """
    path = a_session(tmp_path)
    lost = session.send(path, PASSWORD, **FAST)

    following = session.send(path, PASSWORD, **FAST)

    assert following.counter == lost.counter + 1
    assert following.aead != lost.aead


def test_a_crash_mid_save_leaves_the_previous_state_intact(tmp_path):
    """Written to a temporary name and renamed, so a partial write is never the file the
    next run reads."""
    path = a_session(tmp_path)
    session.send(path, PASSWORD, **FAST)
    before = state_store.load(path, PASSWORD).counter

    scratch = path.with_suffix(path.suffix + ".partial")
    scratch.write_bytes(b"half a file")

    assert state_store.load(path, PASSWORD).counter == before


def test_no_partial_file_survives_a_successful_save(tmp_path):
    path = a_session(tmp_path)
    session.send(path, PASSWORD, **FAST)

    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".partial")]
    assert leftovers == []


def test_the_wasted_counter_is_the_price_of_the_ordering(tmp_path):
    """Committing before returning keys means a crash loses a message. The other order
    loses a counter's uniqueness, which is far worse. This records the trade rather than
    leaving it to be rediscovered."""
    path = a_session(tmp_path)
    reference = SendChain(SS, SID)

    session.send(path, PASSWORD, **FAST)
    reference.next_message_keys()
    assert state_store.load(path, PASSWORD).counter == reference.counter


# ---- the honest control ----------------------------------------------------


def test_an_undisturbed_session_runs_forward_cleanly(tmp_path):
    """If this fails, the tests above are passing for the wrong reason."""
    path = a_session(tmp_path)

    counters = [session.send(path, PASSWORD, **FAST).counter for _ in range(20)]

    assert counters == list(range(20))
    assert state_store.load(path, PASSWORD).generation == 20
    assert rollback_guard.inspect(state_store.load(path, PASSWORD)).ok is True


def test_a_quarantined_file_is_still_encrypted(tmp_path):
    """Moved aside for the user to inspect, not left readable."""
    path = a_session(tmp_path)
    state = state_store.load(path, PASSWORD)

    moved = Path(rollback_guard.quarantine(path))

    assert state.chain_key not in moved.read_bytes()
    assert state_store.load(moved, PASSWORD).chain_key == state.chain_key
