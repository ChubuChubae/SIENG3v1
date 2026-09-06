"""labels and argon2. The HKDF vectors live in tests/vectors/test_hkdf_kat.py.

Argon2 is deliberately expensive, so every test here passes reduced cost parameters. That
is what those arguments are for. The real defaults are checked once, as numbers, without
running a derivation at them.
"""

import pytest

from sieng.common.errors import CryptoError
from sieng.crypto.kdf import argon2, labels
from sieng.crypto.kdf.hkdf import expand_key

# Fast enough for a test suite, far too weak for a file. Never copy these into src/.
FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}


# ---- labels ----------------------------------------------------------------


def test_every_label_is_distinct():
    """Two derivations sharing a label produce the same key, silently. This is the single
    most important check in the file, and labels.py runs it again at import time."""
    assert len(set(labels.ALL_LABELS)) == len(labels.ALL_LABELS)


def test_the_duplicate_check_actually_catches_one():
    """A guard nobody has seen fail is a guard nobody knows works."""
    original = labels.ALL_LABELS
    try:
        labels.ALL_LABELS = (labels.MESSAGE_KEY, labels.MESSAGE_KEY)
        with pytest.raises(AssertionError, match="Duplicate KDF labels"):
            labels.check_labels_are_distinct()
    finally:
        labels.ALL_LABELS = original


def test_the_labels_are_the_ones_in_the_spec():
    """Pinned against FORMAT_SPEC.md 2.2. Changing any of these makes every stego file
    ever written unreadable, so a change has to be a deliberate edit to this test too."""
    assert labels.KEM_SUITE == b"sieng3/kem/x25519-mlkem768/v1"
    assert labels.HEADER_KEY == b"sieng3/hdrkey/v1"
    assert labels.CHAIN_INIT == b"sieng3/chain/v1"
    assert labels.RATCHET_STEP == b"sieng3/ratchet/v1"
    assert labels.MESSAGE_KEY == b"sieng3/msg/v1"
    assert labels.MESSAGE_KEYS == b"sieng3/msgkeys/v1"
    assert labels.HEADER_STREAM == b"sieng3/hdrstream/v1"
    assert labels.TRANSCRIPT == b"SIENG3-transcript-v1"
    assert labels.KEYSTORE_WRAP == b"sieng3/keystore/v1"
    assert labels.STATE_WRAP == b"sieng3/state/v1"


def test_the_message_key_and_the_next_chain_key_differ():
    """Both come from CK[n] and only the label separates them. If this fails, the key that
    encrypts a message is also the key that encrypts every message after it."""
    chain_key = bytes(range(32))

    assert expand_key(chain_key, labels.MESSAGE_KEY) != expand_key(chain_key, labels.RATCHET_STEP)


def test_the_header_key_and_the_chain_root_differ():
    """Both come from ss, same reasoning."""
    shared_secret = bytes(range(32))

    assert expand_key(shared_secret, labels.HEADER_KEY) != expand_key(
        shared_secret, labels.CHAIN_INIT
    )


def test_the_two_storage_labels_differ():
    """A stolen ratchet state file must not be openable by the keystore reader, or the
    other way round."""
    assert labels.KEYSTORE_WRAP != labels.STATE_WRAP


# ---- argon2 ----------------------------------------------------------------


def test_the_cost_parameters_follow_rfc_9106():
    """Checked as numbers rather than by running a derivation, because running one at
    these settings is the slow thing they exist to be."""
    assert argon2.TIME_COST == 3
    assert argon2.MEMORY_COST_KIB == 64 * 1024
    assert argon2.LANES == 4


def test_the_same_password_and_salt_give_the_same_key():
    salt = argon2.new_salt()

    first = argon2.derive_key(b"correct horse", salt, **FAST)
    second = argon2.derive_key(b"correct horse", salt, **FAST)

    assert first == second
    assert len(first) == 32


def test_a_different_password_gives_a_different_key():
    salt = argon2.new_salt()

    assert argon2.derive_key(b"password", salt, **FAST) != argon2.derive_key(
        b"passwore", salt, **FAST
    )


def test_a_different_salt_gives_a_different_key():
    """Why the salt exists: two people who picked the same password get different keys, so
    cracking one does not unlock the other."""
    password = b"same password"

    assert argon2.derive_key(password, argon2.new_salt(), **FAST) != argon2.derive_key(
        password, argon2.new_salt(), **FAST
    )


def test_salts_are_random_and_long_enough():
    assert argon2.new_salt() != argon2.new_salt()
    assert len(argon2.new_salt()) == argon2.SALT_BYTES == 16


def test_verify_accepts_the_right_password():
    salt = argon2.new_salt()
    key = argon2.derive_key(b"open sesame", salt, **FAST)

    assert argon2.verify(b"open sesame", salt, key, **FAST) is True


def test_verify_rejects_the_wrong_password():
    salt = argon2.new_salt()
    key = argon2.derive_key(b"open sesame", salt, **FAST)

    assert argon2.verify(b"open sesamf", salt, key, **FAST) is False


def test_verifying_at_the_wrong_cost_fails_even_for_the_right_password():
    """Argon2 output depends on the cost parameters, so a key derived at one setting does
    not verify at another. This is why 7.7 must store them beside the salt: otherwise the
    day the costs are raised, every existing file looks like a wrong password."""
    salt = argon2.new_salt()
    key = argon2.derive_key(b"open sesame", salt, **FAST)

    assert argon2.verify(b"open sesame", salt, key, **{**FAST, "time_cost": 2}) is False


def test_the_stored_parameters_are_the_ones_used():
    """The keystore writes current_parameters() next to the salt and reads it back into
    verify(). If these two ever disagree, old files stop opening."""
    stored = argon2.current_parameters()

    assert set(stored) == set(argon2.PARAMETER_FIELDS)
    assert stored == {"time_cost": 3, "memory_cost_kib": 64 * 1024, "lanes": 4}


def test_an_empty_password_is_refused():
    with pytest.raises(CryptoError, match="empty password"):
        argon2.derive_key(b"", argon2.new_salt(), **FAST)


def test_an_absurdly_long_password_is_refused():
    with pytest.raises(CryptoError, match="byte limit"):
        argon2.derive_key(bytes(2000), argon2.new_salt(), **FAST)


def test_a_short_salt_is_refused():
    """Not a style rule. A short salt is what makes a rainbow table worth building."""
    with pytest.raises(CryptoError, match="Salt is"):
        argon2.derive_key(b"password", b"abc", **FAST)
