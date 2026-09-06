"""The keystore, zeroize, and the key lifecycle.

Argon2 at its real cost takes about a tenth of a second, and there are a lot of cases
here, so every test passes reduced parameters. The real defaults are checked once as
numbers in test_crypto_kdf.py, and the fact that the parameters travel with the file is
checked here, because that is a keystore property rather than a KDF one.
"""

from pathlib import Path

import pytest

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto import keystore, zeroize
from sieng.crypto.kem.hybrid import generate_identity
from sieng.crypto.lifecycle import DestroyReport, KeyState, ManagedKey, destroy_session

FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}
PASSWORD = b"correct horse battery staple"


@pytest.fixture(scope="module")
def identity():
    return generate_identity()


# ---- wrapping --------------------------------------------------------------


def test_a_wrapped_secret_comes_back():
    wrapped = keystore.wrap(b"secret material", PASSWORD, **FAST)

    assert keystore.unwrap(wrapped, PASSWORD) == b"secret material"


def test_the_wrapped_file_does_not_contain_the_secret():
    """The point of the whole file. If the plaintext appears anywhere in the output, the
    wrapping did nothing."""
    secret = b"THIS-IS-THE-SECRET-VALUE"

    blob = keystore.wrap(secret, PASSWORD, **FAST).to_bytes()

    assert secret not in blob


def test_the_wrong_password_is_refused():
    wrapped = keystore.wrap(b"secret", PASSWORD, **FAST)

    with pytest.raises(DecryptError):
        keystore.unwrap(wrapped, b"wrong password")


def test_two_wraps_of_the_same_secret_differ():
    """A fresh salt each time, so an observer cannot tell that two files hold the same
    key, and two users with the same password get different ciphertext."""
    first = keystore.wrap(b"secret", PASSWORD, **FAST).to_bytes()
    second = keystore.wrap(b"secret", PASSWORD, **FAST).to_bytes()

    assert first != second


def test_wrapping_nothing_is_refused():
    with pytest.raises(CryptoError, match="Refusing to wrap nothing"):
        keystore.wrap(b"", PASSWORD, **FAST)


# ---- the file format -------------------------------------------------------


def test_a_wrapped_key_survives_the_wire_format():
    wrapped = keystore.wrap(b"secret", PASSWORD, **FAST)

    parsed = keystore.WrappedKey.from_bytes(wrapped.to_bytes())

    assert parsed == wrapped
    assert keystore.unwrap(parsed, PASSWORD) == b"secret"


def test_a_file_that_is_not_a_keystore_is_refused():
    """Refused as a wrong file, not a wrong password. Telling a user their password is
    wrong when they opened the wrong file sends them looking in the wrong place."""
    with pytest.raises(CryptoError, match="not a SIENG3 keystore"):
        keystore.WrappedKey.from_bytes(b"NOPE" + bytes(100))


def test_a_truncated_file_is_refused():
    with pytest.raises(CryptoError, match="too short"):
        keystore.WrappedKey.from_bytes(b"SI3K" + bytes(4))


def test_an_unknown_version_is_refused():
    """This format will change. A reader that guesses would produce nonsense keys."""
    blob = bytearray(keystore.wrap(b"secret", PASSWORD, **FAST).to_bytes())
    blob[4] = 99

    with pytest.raises(CryptoError, match="version 99"):
        keystore.WrappedKey.from_bytes(bytes(blob))


def test_a_tampered_ciphertext_is_refused():
    wrapped = keystore.wrap(b"secret", PASSWORD, **FAST)
    blob = bytearray(wrapped.to_bytes())
    blob[-1] ^= 1

    with pytest.raises(DecryptError):
        keystore.unwrap(keystore.WrappedKey.from_bytes(bytes(blob)), PASSWORD)


# ---- the argon2 parameters travel with the file ----------------------------


def test_the_parameters_are_stored_and_read_back():
    """Why they are on disk at all: Argon2 output depends on them, so a file written at
    one cost and read at another fails exactly like a wrong password."""
    wrapped = keystore.wrap(b"secret", PASSWORD, **FAST)

    assert wrapped.parameters() == FAST
    assert keystore.WrappedKey.from_bytes(wrapped.to_bytes()).parameters() == FAST


def test_a_file_written_at_one_cost_opens_at_that_cost():
    """A file must keep opening after the defaults are raised, which is only possible
    because the settings it was written with are in it."""
    weak = keystore.wrap(b"secret", PASSWORD, time_cost=1, memory_cost_kib=8, lanes=1)
    stronger = keystore.wrap(b"secret", PASSWORD, time_cost=2, memory_cost_kib=8, lanes=1)

    assert keystore.unwrap(weak, PASSWORD) == b"secret"
    assert keystore.unwrap(stronger, PASSWORD) == b"secret"


def test_lowering_the_parameters_in_the_file_is_refused():
    """The attack the associated data prevents. Editing three bytes would otherwise turn
    a 64 MiB derivation into a trivial one and the file would still open."""
    wrapped = keystore.wrap(b"secret", PASSWORD, time_cost=2, memory_cost_kib=8, lanes=1)
    weakened = keystore.WrappedKey(
        version=wrapped.version,
        time_cost=1,
        memory_cost_kib=8,
        lanes=1,
        salt=wrapped.salt,
        nonce=wrapped.nonce,
        ciphertext=wrapped.ciphertext,
    )

    with pytest.raises(DecryptError):
        keystore.unwrap(weakened, PASSWORD)


def test_a_file_written_at_weaker_settings_is_flagged_for_rewrap():
    weak = keystore.wrap(b"secret", PASSWORD, **FAST)
    current = keystore.wrap(b"secret", PASSWORD)

    assert keystore.needs_rewrap(weak) is True
    assert keystore.needs_rewrap(current) is False


# ---- identities on disk ----------------------------------------------------


def test_an_identity_survives_a_save_and_a_load(tmp_path, identity):
    path = tmp_path / "identity.key"
    keystore.save_identity(path, identity, PASSWORD, **FAST)

    assert keystore.load_identity(path, PASSWORD) == identity


def test_the_saved_identity_is_not_readable_without_the_password(tmp_path, identity):
    path = tmp_path / "identity.key"
    keystore.save_identity(path, identity, PASSWORD, **FAST)

    blob = path.read_bytes()
    assert identity.mlkem_seed not in blob
    assert identity.x25519_secret not in blob


def test_loading_with_the_wrong_password_is_refused(tmp_path, identity):
    path = tmp_path / "identity.key"
    keystore.save_identity(path, identity, PASSWORD, **FAST)

    with pytest.raises(DecryptError):
        keystore.load_identity(path, b"not the password")


def test_no_partial_file_is_left_behind(tmp_path, identity):
    """Written to a temporary name and renamed, so a crash midway leaves the previous key
    intact rather than a half written file that opens as neither."""
    path = tmp_path / "identity.key"
    keystore.save_identity(path, identity, PASSWORD, **FAST)

    assert [p.name for p in tmp_path.iterdir()] == ["identity.key"]


def test_a_payload_of_the_wrong_size_is_refused(tmp_path):
    """A file that decrypts but does not hold an identity is still a failure."""
    path = tmp_path / "identity.key"
    path.write_bytes(keystore.wrap(b"too short", PASSWORD, **FAST).to_bytes())

    with pytest.raises(DecryptError):
        keystore.load_identity(path, PASSWORD)


def test_an_identity_can_be_used_after_a_round_trip(tmp_path, identity):
    """The seeds have to rebuild the same public key, or the identity is a different one."""
    path = tmp_path / "identity.key"
    keystore.save_identity(path, identity, PASSWORD, **FAST)

    assert keystore.load_identity(path, PASSWORD).public() == identity.public()


# ---- zeroize ---------------------------------------------------------------


def test_a_buffer_is_actually_overwritten():
    buffer = bytearray(b"secret material")

    zeroize.zeroize(buffer)

    assert bytes(buffer) == bytes(15)


def test_wiping_immutable_bytes_is_refused():
    """A call that appears to wipe a secret and does not is worse than no call: it makes
    the reader believe the secret is gone."""
    with pytest.raises(TypeError, match="cannot be overwritten"):
        zeroize.zeroize(b"immutable")


def test_several_buffers_are_all_wiped():
    first, second = bytearray(b"aaa"), bytearray(b"bbb")

    zeroize.zeroize_all(first, second)

    assert bytes(first) == bytes(second) == bytes(3)


def test_an_empty_buffer_is_fine():
    zeroize.zeroize(bytearray())


def test_the_limitations_are_stated_rather_than_implied():
    """The project promises this in THREAT_MODEL.md, so it is checked mechanically."""
    assert zeroize.memory_wiping_is_reliable() is False
    assert "cannot guarantee" in zeroize.limitations()


# ---- key lifecycle ---------------------------------------------------------


def test_a_key_starts_generated_and_can_be_activated():
    key = ManagedKey("identity")

    assert key.state is KeyState.GENERATED
    key.transition(KeyState.ACTIVE)
    assert key.state is KeyState.ACTIVE


def test_a_revoked_key_cannot_come_back():
    """The move that looks harmless and is not. Undoing a revocation made in a hurry for
    a good reason would go unnoticed."""
    key = ManagedKey("identity")
    key.transition(KeyState.ACTIVE)
    key.transition(KeyState.REVOKED)

    with pytest.raises(CryptoError, match="cannot go from REVOKED to ACTIVE"):
        key.transition(KeyState.ACTIVE)


def test_a_destroyed_key_has_nowhere_left_to_go():
    key = ManagedKey("identity")
    key.transition(KeyState.DESTROYED)

    with pytest.raises(CryptoError, match="the only moves are: nothing"):
        key.transition(KeyState.REVOKED)


@pytest.mark.parametrize("state", [KeyState.REVOKED, KeyState.DESTROYED, KeyState.GENERATED])
def test_an_unusable_key_is_refused(state):
    key = ManagedKey("identity")
    if state is not KeyState.GENERATED:
        key.transition(state)

    with pytest.raises(CryptoError):
        key.require_usable()
    assert key.is_usable() is False


def test_a_rotating_key_still_reads_but_does_not_send():
    """It has to open messages sent before it was replaced, and must never be picked for
    a new one."""
    key = ManagedKey("identity")
    key.transition(KeyState.ACTIVE)
    key.transition(KeyState.ROTATING)

    key.require_usable(for_sending=False)
    with pytest.raises(CryptoError, match="rotated out"):
        key.require_usable(for_sending=True)


def test_the_history_records_every_move():
    key = ManagedKey("identity")
    key.transition(KeyState.ACTIVE)
    key.transition(KeyState.REVOKED)

    assert key.history == [
        (KeyState.GENERATED, KeyState.ACTIVE),
        (KeyState.ACTIVE, KeyState.REVOKED),
    ]


# ---- destroying a session --------------------------------------------------


def test_destroying_removes_every_file(tmp_path):
    paths = [tmp_path / f"{name}.bin" for name in ("state", "skipped", "cache")]
    for path in paths:
        path.write_bytes(b"key material")

    report = destroy_session(b"\x01\x02\x03\x04", paths)

    assert report.complete is True
    assert set(report.removed) == set(paths)
    assert not any(path.exists() for path in paths)


def test_a_file_that_was_never_there_is_reported_separately(tmp_path):
    """Missing is not the same as failed. One means already gone, the other means still
    on disk, and a user acting on the report needs to tell them apart."""
    present = tmp_path / "state.bin"
    present.write_bytes(b"x")
    absent = tmp_path / "gone.bin"

    report = destroy_session(b"sess", [present, absent])

    assert report.removed == [present]
    assert report.missing == [absent]
    assert report.complete is True


def test_the_summary_names_what_could_not_be_removed():
    """A silent failure here is the worst outcome: the user acts as though the material
    is gone when it is still on disk."""
    report = DestroyReport(session_id=b"\xaa\xbb", failed=[(Path("locked.bin"), "in use")])

    assert report.complete is False
    assert "locked.bin" in report.summary()


def test_the_contents_are_overwritten_before_the_file_goes(tmp_path):
    """Best effort, and documented as such: on a copy-on-write filesystem or an SSD the
    old blocks may survive anyway."""
    path = tmp_path / "state.bin"
    path.write_bytes(b"key material")

    destroy_session(b"sess", [path])

    assert not path.exists()


def test_an_identity_saved_and_destroyed_leaves_nothing(tmp_path, identity):
    path = tmp_path / "identity.key"
    keystore.save_identity(path, identity, PASSWORD, **FAST)

    report = destroy_session(b"sess", [path])

    assert report.complete is True
    assert list(tmp_path.iterdir()) == []
