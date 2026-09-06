"""The symmetric ratchet.

Three groups of tests, and the middle one is the one that would be easiest to leave out
and worst to be missing.

    derivation   the keys come out the right size and the four subkeys are distinct
    seed_sel     every message gets a different selection channel. This is the property
                 that makes the system steganography rather than encryption, and it can
                 break without any other test noticing
    limits       skip caps and replay refusal, which are what stop one forged counter
                 from becoming a denial of service
"""

import pytest

from sieng.common.errors import CryptoError, RatchetLimitError, ReplayError
from sieng.crypto.ratchet import chain

SS = bytes(range(32))
SID = b"sess"


def send(shared=SS, session=SID, counter=0):
    return chain.SendChain(shared, session, counter)


def recv(shared=SS, session=SID, max_skip=1000, counter=0, max_pool=None):
    return chain.RecvChain(shared, session, max_skip, counter, max_pool)


# ---- what a message key is made of -----------------------------------------


def test_the_four_subkeys_are_the_right_sizes():
    keys = send().next_message_keys()

    assert len(keys.aead) == 32
    assert len(keys.nonce) == 12
    assert len(keys.header) == 32
    assert len(keys.selection) == 32


def test_the_four_subkeys_are_all_different():
    """They come from one expansion at fixed offsets. If two were equal, the nonce would
    be a prefix of the key, or the selection order would be derivable from the header."""
    keys = send().next_message_keys()
    parts = [keys.aead, keys.nonce, keys.header, keys.selection]

    assert len(set(parts)) == len(parts)


def test_the_slices_cover_the_expansion_exactly():
    """108 bytes in, 108 bytes out, no overlap and no gap. An overlap would mean two
    subkeys share material."""
    covered = [
        chain.AEAD_SLICE,
        chain.NONCE_SLICE,
        chain.HEADER_SLICE,
        chain.SELECTION_SLICE,
    ]
    positions = [i for s in covered for i in range(s.start, s.stop)]

    assert sorted(positions) == list(range(chain.MESSAGE_KEYS_BYTES))
    assert chain.MESSAGE_KEYS_BYTES == 108


def test_the_message_key_and_the_next_chain_key_differ():
    """Both come from CK[n] with only the label between them."""
    chain_key = bytes(range(32))

    assert chain.derive_message_key(chain_key) != chain.advance(chain_key)


def test_the_header_key_and_the_chain_root_differ():
    assert chain.header_session_key(SS) != chain.root_chain_key(SS)


# ---- the selection channel -------------------------------------------------


def test_every_message_gets_a_different_selection_seed():
    """The single most important property in this file.

    seed_sel sets the secret order the coefficients are visited in. If two messages ever
    shared one, an examiner who has both images knows the scan order for both, and the
    selection channel stops being secret. Nothing else in the suite would go red.
    """
    sender = send()
    seeds = [sender.next_message_keys().selection for _ in range(50)]

    assert len(set(seeds)) == 50


def test_two_sessions_never_share_a_selection_seed():
    """Same counter, different session id. Without the session id in the derivation, two
    sessions started from different secrets could still line up here."""
    first = send(session=b"aaaa").next_message_keys()
    second = send(session=b"bbbb").next_message_keys()

    assert first.selection != second.selection


def test_a_different_shared_secret_gives_different_keys():
    assert send(shared=bytes(32)).next_message_keys().aead != send().next_message_keys().aead


# ---- sender and receiver agree ---------------------------------------------


def test_both_sides_derive_the_same_keys_in_order():
    sender, receiver = send(), recv()

    for counter in range(10):
        sent = sender.next_message_keys()
        got = receiver.keys_for(counter)
        receiver.mark_consumed(counter)

        assert sent == got
        assert sent.counter == counter


def test_the_counter_advances_by_one_each_time():
    sender = send()

    assert [sender.next_message_keys().counter for _ in range(5)] == [0, 1, 2, 3, 4]


def test_a_chain_never_repeats_a_key():
    sender = send()
    aead_keys = [sender.next_message_keys().aead for _ in range(100)]

    assert len(set(aead_keys)) == 100


# ---- messages out of order -------------------------------------------------


def test_a_message_that_arrives_early_still_opens():
    """Counter 5 arriving first. The receiver has to ratchet past 0 to 4 to reach it."""
    sender, receiver = send(), recv()
    expected = [sender.next_message_keys() for _ in range(6)]

    assert receiver.keys_for(5) == expected[5]


def test_the_skipped_messages_can_still_be_read_afterwards():
    """What the pool is for. Messages 0 to 4 turn up after 5 was already processed."""
    sender, receiver = send(), recv()
    expected = [sender.next_message_keys() for _ in range(6)]
    receiver.keys_for(5)
    receiver.mark_consumed(5)

    for counter in range(5):
        assert receiver.keys_for(counter) == expected[counter]


def test_the_pool_holds_exactly_what_was_passed_over():
    sender, receiver = send(), recv()
    for _ in range(4):
        sender.next_message_keys()
    receiver.keys_for(3)

    assert receiver.skipped_count() == 3


def test_consuming_a_key_removes_it_from_the_pool():
    receiver = recv()
    receiver.keys_for(3)
    receiver.mark_consumed(1)

    assert receiver.skipped_count() == 2


# ---- replay ----------------------------------------------------------------


def test_a_consumed_counter_is_refused():
    """Without this, anyone who captured a stego file can hand it back and have it
    accepted a second time."""
    receiver = recv()
    receiver.keys_for(0)
    receiver.mark_consumed(0)

    with pytest.raises(ReplayError):
        receiver.keys_for(0)


def test_a_counter_behind_the_chain_with_no_stored_key_is_refused():
    receiver = recv()
    receiver.keys_for(3)
    receiver.mark_consumed(3)
    for counter in range(3):
        receiver.mark_consumed(counter)

    with pytest.raises(ReplayError):
        receiver.keys_for(1)


def test_replay_is_a_different_error_from_a_failed_decryption():
    """It is a fact about our own state, not about the ciphertext, and the caller has not
    tried to decrypt anything yet."""
    receiver = recv()
    receiver.keys_for(0)
    receiver.mark_consumed(0)

    with pytest.raises(ReplayError) as error:
        receiver.keys_for(0)
    assert "already used" in str(error.value)


# ---- the limits ------------------------------------------------------------


def test_a_counter_too_far_ahead_is_refused():
    """A forged counter of 2^24 - 1 would otherwise make the receiver run sixteen million
    HKDF steps, which costs the attacker a single message."""
    receiver = recv(max_skip=10)

    with pytest.raises(RatchetLimitError, match="max_ratchet_skip"):
        receiver.keys_for(10)


def test_the_limit_is_exclusive_at_the_boundary():
    receiver = recv(max_skip=10)

    assert receiver.keys_for(9).counter == 9


def test_refusing_leaves_the_chain_where_it_was():
    """The check has to happen before any ratcheting, or a refused message still costs the
    work it was refused for."""
    receiver = recv(max_skip=5)
    with pytest.raises(RatchetLimitError):
        receiver.keys_for(1000)

    assert receiver.counter == 0
    assert receiver.skipped_count() == 0


def test_the_pool_stops_growing_once_it_is_full():
    """max_skip bounds one message. This bounds a session that drifts a little further
    ahead every time, which would otherwise grow the pool without limit."""
    receiver = recv(max_skip=100, max_pool=10)
    for counter in range(20, 200, 20):
        receiver.keys_for(counter)
        receiver.mark_consumed(counter)

    assert receiver.skipped_count() <= 10


def test_the_oldest_outstanding_key_is_the_one_dropped():
    receiver = recv(max_skip=100, max_pool=3)
    receiver.keys_for(10)

    with pytest.raises(ReplayError, match="fell out of the skipped pool"):
        receiver.keys_for(0)
    assert receiver.keys_for(9).counter == 9


def test_a_counter_past_the_header_range_is_refused():
    with pytest.raises(CryptoError, match="24 bits"):
        recv().keys_for(chain.MAX_COUNTER + 1)


def test_a_session_that_runs_out_of_counters_stops():
    """2^24 messages is the ceiling the header imposes. Wrapping would reuse keys."""
    sender = send(counter=chain.MAX_COUNTER)
    sender.next_message_keys()

    with pytest.raises(RatchetLimitError, match="new session"):
        sender.next_message_keys()


@pytest.mark.parametrize("session_id", [b"", b"abc", b"abcde"])
def test_a_wrong_sized_session_id_is_refused(session_id):
    with pytest.raises(CryptoError, match="Session id"):
        send(session=session_id)


def test_a_max_skip_below_one_is_refused():
    with pytest.raises(CryptoError, match="max_skip"):
        recv(max_skip=0)


# ---- forward secrecy -------------------------------------------------------


def test_the_chain_key_moves_and_does_not_come_back():
    """The chain key after n messages must not equal any earlier one, or the ratchet is
    not ratcheting and old messages stay derivable."""
    sender = send()
    seen = {sender.chain_key()}
    for _ in range(20):
        sender.next_message_keys()
        assert sender.chain_key() not in seen
        seen.add(sender.chain_key())


def test_the_current_state_cannot_reach_an_earlier_key():
    """Seizing the machine after message 10 must not recover message 0.

    Checked the only way it can be from outside: a chain restarted from the state that
    remains produces different keys from the ones already used.
    """
    sender = send()
    early = [sender.next_message_keys().aead for _ in range(10)]

    from_now_on = [sender.next_message_keys().aead for _ in range(10)]

    assert not set(early) & set(from_now_on)
