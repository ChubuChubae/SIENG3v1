"""Identities, transcripts, dual signatures and the trust store.

The MITM and downgrade cases live in tests/security/test_auth_attacks.py, where the
negative results belong. This file covers the mechanics they rest on.
"""

import pytest

from sieng.common.errors import CryptoError
from sieng.crypto.auth import identity as ident
from sieng.crypto.auth import signatures, transcript
from sieng.crypto.auth.trust_store import TrustEntry, TrustStore

SID = b"\x01\x02\x03\x04"


@pytest.fixture(scope="module")
def alice():
    return ident.generate(signing=True)


@pytest.fixture(scope="module")
def bob():
    return ident.generate()


# ---- identity --------------------------------------------------------------


def test_an_identity_without_signing_keys_has_only_the_kem_pair(bob):
    public = bob.public()

    assert public.can_sign() is False
    assert public.ed25519_public == b""
    assert len(public.kem.mlkem) == 1184
    assert len(public.kem.x25519) == 32


def test_a_signing_identity_carries_all_four_keys(alice):
    public = alice.public()

    assert public.can_sign() is True
    assert len(public.ed25519_public) == ident.ED25519_PUBLIC_BYTES == 32
    assert len(public.mldsa_public) == ident.MLDSA_PUBLIC_BYTES == 1952


def test_the_secret_holds_seeds_not_expanded_keys(alice):
    """160 bytes for a full identity instead of about 6,500. The expansion is
    deterministic, so nothing is lost and there is less material to protect."""
    total = (
        len(alice.kem.mlkem_seed)
        + len(alice.kem.x25519_secret)
        + len(alice.ed25519_secret)
        + len(alice.mldsa_seed)
    )

    assert total == 64 + 32 + 32 + 32 == 160


def test_half_a_signing_pair_is_refused():
    """Both signatures must verify, so an identity with one signing key would look like
    protection it cannot provide."""
    with pytest.raises(CryptoError, match="both signing keys or neither"):
        ident.Identity(ident.generate().kem.public(), bytes(32), b"")


def test_a_signing_key_of_the_wrong_size_is_refused(bob):
    with pytest.raises(CryptoError, match="Ed25519 public key"):
        ident.Identity(bob.public().kem, bytes(31), bytes(1952))


def test_the_public_key_is_rebuilt_from_the_seeds(alice):
    assert alice.public() == alice.public()


def test_loading_from_raw_bytes_checks_each_key(alice):
    public = alice.public()

    loaded = ident.load_public(
        public.kem.x25519, public.kem.mlkem, public.ed25519_public, public.mldsa_public
    )

    assert loaded == public


def test_a_component_of_the_wrong_length_is_refused_at_load():
    """Caught here, where the message says which key was wrong, rather than several
    layers down in a handshake that only knows it failed."""
    with pytest.raises(CryptoError, match="ML-KEM-768 public key must be 1184 bytes"):
        ident.load_public(bytes(32), bytes(100))
    with pytest.raises(CryptoError, match="X25519 public key must be 32 bytes"):
        ident.load_public(bytes(31), bytes(1184))


def test_load_public_checks_length_and_encoding_but_not_sanity():
    """Recorded because the limit matters. Neither ML-KEM nor Ed25519 rejects an all-zero
    key of the right size, so load_public() cannot either.

    That is acceptable only because a public key is never trusted on the strength of
    parsing: it is trusted because a human compared its fingerprint (trust_store.py). If
    that ever stops being true, this is where the gap would be.
    """
    accepted = ident.load_public(bytes(32), bytes(1184), bytes(32), bytes(1952))

    assert accepted.can_sign() is True


# ---- fingerprints ----------------------------------------------------------


def test_a_fingerprint_is_thirty_two_bytes(alice):
    assert len(alice.public().fingerprint()) == ident.FINGERPRINT_BYTES == 32


def test_two_identities_have_different_fingerprints(alice, bob):
    assert alice.public().fingerprint() != bob.public().fingerprint()


def test_adding_signing_keys_changes_the_fingerprint(alice):
    """Correct rather than inconvenient. A user who verified a fingerprint verified those
    exact keys, and silently adding one they never saw would weaken what they checked."""
    kem_only = ident.Identity(alice.public().kem)

    assert kem_only.fingerprint() != alice.public().fingerprint()


def test_the_display_form_is_readable_aloud(alice):
    """Eight groups of four hex characters. Longer than this and nobody finishes
    comparing it, and a fingerprint nobody finishes comparing protects nobody."""
    shown = alice.public().display()

    assert len(shown.split()) == 8
    assert all(len(group) == 4 for group in shown.split())
    assert shown.replace(" ", "").isalnum()


def test_the_display_form_is_stable(alice):
    assert alice.public().display() == alice.public().display()


# ---- the transcript --------------------------------------------------------


def test_the_transcript_is_deterministic(alice, bob):
    """Both sides build it independently and must get identical bytes."""
    first = transcript.build(SID, alice.public(), bob.public())
    second = transcript.build(SID, alice.public(), bob.public())

    assert first == second


def test_swapping_the_two_sides_changes_the_transcript(alice, bob):
    """Direction matters. Sender and recipient are different roles."""
    assert transcript.build(SID, alice.public(), bob.public()) != transcript.build(
        SID, bob.public(), alice.public()
    )


@pytest.mark.parametrize("auth_mode", [transcript.AUTH_IMPLICIT, transcript.AUTH_PQ_EXPLICIT])
def test_the_auth_mode_is_bound_into_the_transcript(alice, bob, auth_mode):
    """Without this, a downgrade from explicit to implicit would leave the derived key
    unchanged and nothing would notice the mode had been altered."""
    other = 1 - auth_mode

    assert transcript.build(SID, alice.public(), bob.public(), auth_mode) != transcript.build(
        SID, alice.public(), bob.public(), other
    )


def test_the_session_id_is_bound_into_the_transcript(alice, bob):
    assert transcript.build(b"aaaa", alice.public(), bob.public()) != transcript.build(
        b"bbbb", alice.public(), bob.public()
    )


def test_every_field_is_length_prefixed(alice, bob):
    """The whole transcript is one length-prefixed join, so its size is the sum of the
    fields plus two bytes each. If a field were concatenated raw the total would be short
    by two and the canonicalisation guarantee would be gone."""
    built = transcript.build(SID, alice.public(), bob.public())

    fields = [
        len(b"SIENG3-transcript-v1"),
        1,
        1,
        1,
        len(SID),
        32,
        32,
        32,
        1184,
        32,
        1184,
    ]
    assert len(built) == sum(fields) + 2 * len(fields)


def test_a_wrong_sized_session_id_is_refused(alice, bob):
    with pytest.raises(CryptoError, match="Session id"):
        transcript.build(b"abc", alice.public(), bob.public())


def test_an_unknown_auth_mode_is_refused(alice, bob):
    with pytest.raises(CryptoError, match="Unknown auth mode"):
        transcript.build(SID, alice.public(), bob.public(), auth_mode=7)


# ---- signatures ------------------------------------------------------------


def test_a_signature_is_both_algorithms_together(alice, bob):
    message = transcript.build(SID, alice.public(), bob.public())

    signature = signatures.sign(alice, message)

    assert len(signature) == signatures.SIGNATURE_BYTES == 3373
    classical, quantum = signatures.split(signature)
    assert len(classical) == 64
    assert len(quantum) == 3309


def test_a_valid_signature_verifies(alice, bob):
    message = transcript.build(SID, alice.public(), bob.public())

    signatures.verify(alice.public(), message, signatures.sign(alice, message))


def test_a_signature_over_a_different_transcript_is_refused(alice, bob):
    message = transcript.build(SID, alice.public(), bob.public())
    signature = signatures.sign(alice, message)

    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message + b"!", signature)


def test_a_signature_from_someone_else_is_refused(alice, bob):
    other = ident.generate(signing=True)
    message = transcript.build(SID, alice.public(), bob.public())

    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message, signatures.sign(other, message))


def test_the_classical_half_alone_is_not_enough(alice, bob):
    """The reason both are required. Accepting either would mean an attacker only has to
    break the weaker one, which makes the pair worse than either alone."""
    message = transcript.build(SID, alice.public(), bob.public())
    signature = bytearray(signatures.sign(alice, message))
    signature[-1] ^= 1

    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message, bytes(signature))


def test_the_quantum_half_alone_is_not_enough(alice, bob):
    message = transcript.build(SID, alice.public(), bob.public())
    signature = bytearray(signatures.sign(alice, message))
    signature[0] ^= 1

    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message, bytes(signature))


def test_a_signature_of_the_wrong_length_is_refused(alice, bob):
    message = transcript.build(SID, alice.public(), bob.public())

    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message, bytes(100))


def test_an_identity_without_signing_keys_cannot_sign(bob):
    with pytest.raises(CryptoError, match="no signing keys"):
        signatures.sign(bob, b"transcript")


def test_a_signature_cannot_be_checked_against_a_kem_only_identity(bob):
    """Refused rather than treated as unsigned. Silently accepting would turn
    AUTH_PQ_EXPLICIT into AUTH_IMPLICIT without anyone asking."""
    with pytest.raises(CryptoError, match="cannot be checked"):
        signatures.verify(bob.public(), b"transcript", bytes(signatures.SIGNATURE_BYTES))


def test_the_error_does_not_say_which_half_failed(alice, bob):
    """Telling an attacker whether their Ed25519 forgery passed before ML-DSA was checked
    would let them attack the two halves separately."""
    message = transcript.build(SID, alice.public(), bob.public())
    signature = bytearray(signatures.sign(alice, message))

    messages = set()
    for position in (0, -1):
        damaged = bytearray(signature)
        damaged[position] ^= 1
        with pytest.raises(signatures.SignatureError) as error:
            signatures.verify(alice.public(), message, bytes(damaged))
        messages.add(str(error.value))

    assert len(messages) == 1


# ---- the trust store -------------------------------------------------------


def test_an_added_identity_is_trusted(alice):
    store = TrustStore()
    store.add(alice.public(), "qr", "Alice")

    assert store.is_trusted(alice.public().fingerprint()) is True
    assert len(store) == 1


def test_an_unknown_identity_is_not_trusted(alice, bob):
    store = TrustStore()
    store.add(alice.public(), "qr")

    assert store.is_trusted(bob.public().fingerprint()) is False


def test_asking_for_an_unknown_identity_says_what_to_do(bob):
    with pytest.raises(CryptoError, match="verified out of band"):
        TrustStore().get(bob.public().fingerprint())


def test_there_is_no_way_to_trust_without_verifying(alice):
    """If the option existed the interface would offer it, users would take it every
    time, and everything underneath would be decoration."""
    with pytest.raises(CryptoError, match="without comparing it"):
        TrustEntry(alice.public(), "clicked ok")


@pytest.mark.parametrize("method", ["qr", "voice", "manual"])
def test_the_documented_methods_are_accepted(alice, method):
    assert TrustEntry(alice.public(), method).verified_via == method


def test_how_it_was_verified_is_shown_every_time(alice):
    """Every time, not once at setup. Someone who verified a key by email six months ago
    should be reminded of that when they rely on it."""
    entry = TrustEntry(alice.public(), "manual", "Alice")

    assert "manual" in entry.describe()
    assert "Alice" in entry.describe()


# ---- revocation ------------------------------------------------------------


def test_a_revoked_identity_cannot_start_a_new_session(alice):
    store = TrustStore()
    store.add(alice.public(), "qr")
    store.revoke(alice.public().fingerprint(), "lost laptop")

    with pytest.raises(CryptoError, match="lost laptop"):
        store.require_for_new_session(alice.public())


def test_a_revoked_identity_can_still_be_looked_up(alice):
    """Revoking a key is not a reason to lose the messages it already protected."""
    store = TrustStore()
    store.add(alice.public(), "qr")
    store.revoke(alice.public().fingerprint())

    assert store.get(alice.public().fingerprint()).revoked is True


def test_revocation_is_visible_in_the_description(alice):
    store = TrustStore()
    store.add(alice.public(), "qr", "Alice")
    entry = store.revoke(alice.public().fingerprint(), "key compromised")

    assert "REVOKED" in entry.describe()
    assert "key compromised" in entry.describe()


def test_a_trusted_identity_passes_the_new_session_check(alice):
    store = TrustStore()
    store.add(alice.public(), "voice")

    assert store.require_for_new_session(alice.public()).verified_via == "voice"


# ---- persistence -----------------------------------------------------------


def test_a_trust_store_survives_a_round_trip(alice, bob):
    store = TrustStore()
    store.add(alice.public(), "qr", "Alice")
    store.add(bob.public(), "manual", "Bob")
    store.revoke(bob.public().fingerprint(), "rotated")

    restored = TrustStore.from_json(store.to_json())

    assert len(restored) == 2
    assert restored.is_trusted(alice.public().fingerprint()) is True
    assert restored.is_trusted(bob.public().fingerprint()) is False
    assert restored.get(bob.public().fingerprint()).revoked_reason == "rotated"


def test_a_trust_store_holds_nothing_secret(alice):
    """Public keys only. If a secret could end up here it would be the one file in the
    project written in plaintext."""
    store = TrustStore()
    store.add(alice.public(), "qr")

    text = store.to_json()
    assert alice.kem.mlkem_seed.hex() not in text
    assert alice.ed25519_secret.hex() not in text


def test_a_store_written_to_disk_reads_back(tmp_path, alice):
    path = tmp_path / "trust.json"
    store = TrustStore()
    store.add(alice.public(), "qr", "Alice")
    store.save(path)

    assert TrustStore.load(path).get(alice.public().fingerprint()).label == "Alice"


def test_no_partial_file_is_left_behind(tmp_path, alice):
    """A truncated trust store is worse than none: it drops identities silently, and the
    next handshake with one of them looks like an attack rather than a lost file."""
    path = tmp_path / "trust.json"
    store = TrustStore()
    store.add(alice.public(), "qr")
    store.save(path)

    assert [p.name for p in tmp_path.iterdir()] == ["trust.json"]


def test_an_unknown_format_version_is_refused():
    with pytest.raises(CryptoError, match="version 99"):
        TrustStore.from_json('{"version": 99, "entries": []}')
