"""The ratchet state on disk: serialisation, the consumed window, and the commit order.

Argon2 runs on every save and load here, so every test passes reduced cost parameters.
The real defaults are checked as numbers in test_crypto_kdf.py.

The rollback and concurrency cases are in tests/security/test_ratchet_state_attacks.py.
"""

from pathlib import Path

import pytest

from sieng.common.errors import CryptoError, DecryptError, ReplayError
from sieng.crypto.ratchet import generation as gen
from sieng.crypto.ratchet import rollback_guard, session, state_store
from sieng.crypto.ratchet.chain import RecvChain, SendChain
from sieng.crypto.ratchet.state_store import RatchetState

FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
SS = bytes(range(32))
SID = b"sess"
PASSWORD = b"a keystore password"


def a_state(**kwargs):
    fields = {"session_id": SID, "chain_key": bytes(range(32)), "window": 100}
    return RatchetState(**{**fields, **kwargs})


# ---- serialisation ---------------------------------------------------------


def test_a_state_survives_a_round_trip(tmp_path):
    state = a_state(counter=5, generation=3)
    state.skipped = {2: bytes(32), 3: bytes(range(32))}
    state.consumed = {1, 4}
    path = tmp_path / "s.state"

    state_store.save(path, state, PASSWORD, **FAST)
    loaded = state_store.load(path, PASSWORD)

    assert loaded.counter == 5
    assert loaded.generation == 3
    assert loaded.chain_key == state.chain_key
    assert loaded.skipped == state.skipped
    assert loaded.consumed == state.consumed


def test_the_state_file_holds_no_plaintext(tmp_path):
    """The chain key is the one value that would let someone read every message from here
    on. If it appears in the file, the encryption did nothing."""
    state = a_state()
    path = tmp_path / "s.state"
    state_store.save(path, state, PASSWORD, **FAST)

    blob = path.read_bytes()
    assert state.chain_key not in blob
    assert SID not in blob


def test_the_wrong_password_is_refused(tmp_path):
    path = tmp_path / "s.state"
    state_store.save(path, a_state(), PASSWORD, **FAST)

    with pytest.raises(DecryptError):
        state_store.load(path, b"wrong")


def test_a_tampered_state_file_is_refused(tmp_path):
    path = tmp_path / "s.state"
    state_store.save(path, a_state(), PASSWORD, **FAST)
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 1
    path.write_bytes(bytes(blob))

    with pytest.raises(DecryptError):
        state_store.load(path, PASSWORD)


def test_a_file_that_is_not_a_state_file_is_refused(tmp_path):
    """Refused as a wrong file, not a wrong password, so the user looks in the right
    place."""
    path = tmp_path / "s.state"
    path.write_bytes(b"NOPE" + bytes(200))

    with pytest.raises(CryptoError, match="not a SIENG3 ratchet state"):
        state_store.load(path, PASSWORD)


def test_an_unknown_version_is_refused(tmp_path):
    path = tmp_path / "s.state"
    state_store.save(path, a_state(), PASSWORD, **FAST)
    blob = bytearray(path.read_bytes())
    blob[4] = 99
    path.write_bytes(bytes(blob))

    with pytest.raises(CryptoError, match="version 99"):
        state_store.load(path, PASSWORD)


def test_the_machine_id_is_recorded_automatically(tmp_path):
    path = tmp_path / "s.state"
    state_store.save(path, a_state(), PASSWORD, **FAST)

    assert state_store.load(path, PASSWORD).machine_id == gen.machine_id()


# ---- the consumed window ---------------------------------------------------


def test_the_window_forgets_what_can_no_longer_be_replayed():
    """A counter more than max_skip behind is refused by RecvChain anyway, because its
    keys are gone. Keeping it would grow the file forever for no protection."""
    state = a_state(counter=500, window=100)
    state.consumed = {5, 399, 400, 450}

    state.prune()

    assert state.consumed == {400, 450}
    assert state.window_base() == 400


def test_the_window_covers_everything_when_the_counter_is_low():
    state = a_state(counter=10, window=100)
    state.consumed = {0, 5, 9}

    state.prune()

    assert state.consumed == {0, 5, 9}
    assert state.window_base() == 0


def test_the_window_survives_the_round_trip(tmp_path):
    state = a_state(counter=500, window=100)
    state.consumed = {400, 425, 499}
    path = tmp_path / "s.state"

    state_store.save(path, state, PASSWORD, **FAST)

    assert state_store.load(path, PASSWORD).consumed == {400, 425, 499}


def test_the_file_stays_small_with_a_full_window(tmp_path):
    """1000 counters is 125 bytes as a bitmap, against 3000 as a list of three byte
    counters. The whole point of the window is that this cannot grow without bound."""
    state = a_state(counter=2000, window=1000)
    state.consumed = set(range(1000, 2000))
    path = tmp_path / "s.state"

    state_store.save(path, state, PASSWORD, **FAST)

    assert path.stat().st_size < 500
    assert len(state_store.load(path, PASSWORD).consumed) == 1000


def test_skipped_keys_outside_the_window_are_dropped():
    state = a_state(counter=500, window=100)
    state.skipped = {350: bytes(32), 450: bytes(32)}

    state.prune()

    assert sorted(state.skipped) == [450]


# ---- resuming a chain ------------------------------------------------------


def test_a_resumed_send_chain_continues_where_it_stopped():
    """The stored key is CK[counter], not CK[0], so the normal constructor would derive
    the wrong keys and nothing would look wrong."""
    original = SendChain(SS, SID)
    for _ in range(3):
        original.next_message_keys()
    expected = original.next_message_keys()

    fresh = SendChain(SS, SID)
    for _ in range(3):
        fresh.next_message_keys()
    resumed = SendChain.resume(SID, fresh.chain_key(), fresh.counter)

    assert resumed.next_message_keys() == expected


def test_a_resumed_receive_chain_keeps_its_pool():
    chain = RecvChain(SS, SID)
    chain.keys_for(3)
    chain.mark_consumed(3)
    key, counter, skipped, consumed = chain.snapshot()

    resumed = RecvChain.resume(SID, key, counter, skipped, consumed)

    assert resumed.skipped_count() == 3
    with pytest.raises(ReplayError):
        resumed.keys_for(3)


def test_resuming_with_a_wrong_sized_key_is_refused():
    with pytest.raises(CryptoError, match="Chain key must be 32 bytes"):
        SendChain.resume(SID, bytes(16), 0)


# ---- the session commit order ----------------------------------------------


def test_sends_match_an_in_memory_chain_exactly(tmp_path):
    """The whole point of the state file: a session that survives a restart derives the
    same keys it would have derived without one."""
    path = tmp_path / "s.state"
    session.create(path, SID, SS, PASSWORD, **FAST)
    reference = SendChain(SS, SID)

    for _ in range(5):
        assert session.send(path, PASSWORD, **FAST) == reference.next_message_keys()


def test_the_counter_never_repeats_across_restarts(tmp_path):
    """Each send reloads the file from scratch, which is what a restart looks like."""
    path = tmp_path / "s.state"
    session.create(path, SID, SS, PASSWORD, **FAST)

    counters = [session.send(path, PASSWORD, **FAST).counter for _ in range(10)]

    assert counters == list(range(10))


def test_the_state_is_committed_before_the_keys_are_returned(tmp_path):
    """Written this way round on purpose. A crash between committing and writing the
    stego file wastes a counter; the other order reuses one."""
    path = tmp_path / "s.state"
    session.create(path, SID, SS, PASSWORD, **FAST)

    keys = session.send(path, PASSWORD, **FAST)

    assert state_store.load(path, PASSWORD).counter == keys.counter + 1


def test_the_generation_advances_on_every_write(tmp_path):
    path = tmp_path / "s.state"
    session.create(path, SID, SS, PASSWORD, **FAST)
    for _ in range(3):
        session.send(path, PASSWORD, **FAST)

    assert state_store.load(path, PASSWORD).generation == 3


def test_creating_over_an_existing_session_is_refused(tmp_path):
    """Overwriting resets the counter on a chain that has already used it, which is the
    same damage as a rollback and much easier to do by accident."""
    path = tmp_path / "s.state"
    session.create(path, SID, SS, PASSWORD, **FAST)

    with pytest.raises(CryptoError, match="already exists"):
        session.create(path, SID, SS, PASSWORD, **FAST)


# ---- receiving -------------------------------------------------------------


def test_a_received_counter_gets_the_keys_the_sender_used(tmp_path):
    sender = SendChain(SS, SID)
    expected = [sender.next_message_keys() for _ in range(6)]
    path = tmp_path / "r.state"
    session.create(path, SID, SS, PASSWORD, **FAST)

    assert session.receive(path, PASSWORD, 5, **FAST) == expected[5]


def test_the_skipped_pool_is_persisted(tmp_path):
    path = tmp_path / "r.state"
    session.create(path, SID, SS, PASSWORD, **FAST)
    session.receive(path, PASSWORD, 3, **FAST)

    assert len(state_store.load(path, PASSWORD).skipped) == 3


def test_a_skipped_message_can_be_read_after_a_restart(tmp_path):
    sender = SendChain(SS, SID)
    expected = [sender.next_message_keys() for _ in range(6)]
    path = tmp_path / "r.state"
    session.create(path, SID, SS, PASSWORD, **FAST)
    session.receive(path, PASSWORD, 5, **FAST)
    session.mark_received(path, PASSWORD, 5, **FAST)

    assert session.receive(path, PASSWORD, 2, **FAST) == expected[2]


def test_marking_is_separate_from_receiving(tmp_path):
    """Marking inside receive would let anyone burn a counter by sending garbage, turning
    a replay defence into a denial of service."""
    path = tmp_path / "r.state"
    session.create(path, SID, SS, PASSWORD, **FAST)
    session.receive(path, PASSWORD, 0, **FAST)

    assert state_store.load(path, PASSWORD).consumed == set()
    session.mark_received(path, PASSWORD, 0, **FAST)
    assert state_store.load(path, PASSWORD).consumed == {0}


def test_a_replayed_counter_is_refused_after_a_restart(tmp_path):
    path = tmp_path / "r.state"
    session.create(path, SID, SS, PASSWORD, **FAST)
    session.receive(path, PASSWORD, 0, **FAST)
    session.mark_received(path, PASSWORD, 0, **FAST)

    with pytest.raises(ReplayError):
        session.receive(path, PASSWORD, 0, **FAST)


# ---- generation and machine id ---------------------------------------------


def test_a_generation_that_goes_backwards_is_refused():
    with pytest.raises(gen.RollbackError, match="moved backwards"):
        gen.check_generation(loaded=3, last_seen=7)


def test_an_equal_generation_is_allowed():
    gen.check_generation(loaded=7, last_seen=7)


def test_the_generation_cannot_wrap():
    """A wrapped counter is a rollback that looks like progress."""
    with pytest.raises(CryptoError, match="cannot advance"):
        gen.next_generation(gen.MAX_GENERATION)


def test_the_machine_id_is_stable_and_the_right_size():
    assert gen.machine_id() == gen.machine_id()
    assert len(gen.machine_id()) == gen.MACHINE_ID_BYTES == 16


def test_state_from_another_machine_is_refused():
    with pytest.raises(CryptoError, match="different machine"):
        gen.check_machine(bytes(16))


# ---- the rollback guard ----------------------------------------------------


def test_the_guard_reports_rather_than_raising():
    """The ui needs to show a status before the user commits to anything."""
    state = a_state(generation=3)

    assert rollback_guard.inspect(state, 3).ok is True
    assert rollback_guard.inspect(state, 9).ok is False
    assert "generation 9 was already used" in rollback_guard.inspect(state, 9).reason


def test_the_enforcing_version_refuses(tmp_path):
    from sieng.common.errors import RollbackDetected

    with pytest.raises(RollbackDetected, match="reuse message counters"):
        rollback_guard.require_forward(a_state(generation=3), last_generation=9)


def test_suspect_state_is_moved_aside_not_deleted(tmp_path):
    """A user who has just been told their state went backwards may need the file to work
    out what happened. Deleting the evidence to silence an error is not a service."""
    path = tmp_path / "s.state"
    state_store.save(path, a_state(), PASSWORD, **FAST)

    moved = rollback_guard.quarantine(path)

    assert not path.exists()
    assert moved.exists()
    assert moved.suffix == ".rollback"


def test_quarantining_twice_does_not_overwrite_the_first():
    """Two rollbacks in a row would otherwise destroy the evidence of the first."""
    import tempfile

    directory = Path(tempfile.mkdtemp())
    for _ in range(2):
        path = directory / "s.state"
        state_store.save(path, a_state(), PASSWORD, **FAST)
        rollback_guard.quarantine(path)

    assert len(list(directory.glob("*.rollback*"))) == 2


def test_the_guard_says_plainly_that_it_cannot_prevent():
    """Checked mechanically because it is the kind of limitation that gets quietly
    forgotten, and THREAT_MODEL.md 4 makes the same promise."""
    assert rollback_guard.prevention_is_possible() is False
    assert "does not prevent" in rollback_guard.__doc__.lower()
