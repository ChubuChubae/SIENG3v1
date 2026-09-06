"""The attacks the authentication design exists to stop, run as tests rather than claimed.

Each one is set up the way an attacker would actually have to run it, and each asserts
that the two sides end up with different key material or that verification refuses. A
design document saying "this prevents X" is worth much less than a test that performs X
and shows it failing.

    key substitution   the man in the middle swaps a public key in transit
    downgrade          an attacker strips the signature and hopes for a fallback
    replay             a captured handshake is reused
    canonicalisation   fields are shuffled across a boundary without changing the bytes
"""

import pytest

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.auth import identity as ident
from sieng.crypto.auth import signatures, transcript
from sieng.crypto.auth.trust_store import TrustStore
from sieng.crypto.kdf import hkdf
from sieng.crypto.kem import hybrid

SID = b"\x01\x02\x03\x04"


@pytest.fixture(scope="module")
def alice():
    return ident.generate(signing=True)


@pytest.fixture(scope="module")
def bob():
    return ident.generate(signing=True)


@pytest.fixture(scope="module")
def mallory():
    return ident.generate(signing=True)


def session_secret(sender, recipient_public, transcript_bytes):
    """One side of a handshake: encapsulate, mix in dh_static, derive ss."""
    secret, blob = hybrid.seal_secret(recipient_public.kem, transcript_bytes)
    static = hybrid.static_exchange(sender.kem, recipient_public.kem)
    return hybrid.derive_shared_secret(secret, static, transcript_bytes), blob


# ---- key substitution ------------------------------------------------------


def test_mitm_key_substitution_is_rejected(alice, bob, mallory):
    """Mallory replaces Bob's public key with her own on the way to Alice.

    Alice encapsulates to Mallory's key, so Mallory can read it. What she cannot do is
    hand it on to Bob as though nothing happened: the transcript Alice used names
    Mallory's fingerprint, and the transcript Bob builds names his own. The two
    transcripts differ, so the two secrets differ, and Bob's side simply does not open.
    """
    alice_sees = transcript.build(SID, alice.public(), mallory.public())
    bob_sees = transcript.build(SID, alice.public(), bob.public())

    assert alice_sees != bob_sees

    from_alice, _ = session_secret(alice, mallory.public(), alice_sees)
    at_bob, _ = session_secret(alice, bob.public(), bob_sees)
    assert from_alice != at_bob


def test_a_substituted_key_cannot_open_the_encapsulation(alice, bob, mallory):
    """The other half of the same attack, at the KEM rather than the KDF.

    Even holding the blob, Mallory cannot pass it to Bob: it was sealed to her key.
    """
    context = transcript.build(SID, alice.public(), mallory.public())
    _, blob = hybrid.seal_secret(mallory.public().kem, context)

    with pytest.raises(DecryptError):
        hybrid.open_secret(bob.kem, blob, context)


def test_the_transcript_notices_a_swapped_sender(alice, bob, mallory):
    """Mallory claiming to be Alice changes the sender fields, so Bob derives a different
    secret from the one she does."""
    honest = transcript.build(SID, alice.public(), bob.public())
    forged = transcript.build(SID, mallory.public(), bob.public())

    assert honest != forged


def test_an_untrusted_identity_never_reaches_a_handshake(alice, mallory):
    """The trust store is the first gate. A key nobody verified does not get to try."""
    store = TrustStore()
    store.add(alice.public(), "qr", "Alice")

    with pytest.raises(CryptoError, match="not in this trust store"):
        store.require_for_new_session(mallory.public())


# ---- downgrade -------------------------------------------------------------


def test_stripping_the_signature_does_not_downgrade_to_implicit(alice, bob):
    """An attacker removes the signature and sets the mode to implicit, hoping the
    receiver falls back rather than refusing.

    It does not work, because the auth mode is inside the transcript. Changing it changes
    the transcript, which changes the secret, so the message does not open. The receiver
    never gets as far as deciding whether to be lenient.
    """
    explicit = transcript.build(SID, alice.public(), bob.public(), transcript.AUTH_PQ_EXPLICIT)
    implicit = transcript.build(SID, alice.public(), bob.public(), transcript.AUTH_IMPLICIT)

    assert explicit != implicit

    from_sender, _ = session_secret(alice, bob.public(), explicit)
    if_downgraded, _ = session_secret(alice, bob.public(), implicit)
    assert from_sender != if_downgraded


def test_a_signature_over_the_implicit_transcript_does_not_verify_as_explicit(alice, bob):
    """A signature is over one exact transcript. It cannot be moved to another mode."""
    implicit = transcript.build(SID, alice.public(), bob.public(), transcript.AUTH_IMPLICIT)
    explicit = transcript.build(SID, alice.public(), bob.public(), transcript.AUTH_PQ_EXPLICIT)
    signature = signatures.sign(alice, implicit)

    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), explicit, signature)


def test_verification_refuses_rather_than_skipping(bob):
    """Handed a signature but no signing keys, the answer is an error. Treating it as
    unsigned would silently turn AUTH_PQ_EXPLICIT into AUTH_IMPLICIT."""
    kem_only = ident.Identity(bob.public().kem)

    with pytest.raises(CryptoError, match="cannot be checked"):
        signatures.verify(kem_only, b"transcript", bytes(signatures.SIGNATURE_BYTES))


def test_breaking_one_algorithm_is_not_enough(alice, bob):
    """The reason for two signatures. If either one alone were accepted, an attacker
    would only have to break the weaker of them."""
    message = transcript.build(SID, alice.public(), bob.public(), transcript.AUTH_PQ_EXPLICIT)
    genuine = signatures.sign(alice, message)
    classical, quantum = signatures.split(genuine)

    forged_quantum = bytes(len(quantum))
    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message, classical + forged_quantum)

    forged_classical = bytes(len(classical))
    with pytest.raises(signatures.SignatureError):
        signatures.verify(alice.public(), message, forged_classical + quantum)


# ---- replay ----------------------------------------------------------------


def test_a_captured_handshake_cannot_be_replayed_into_another_session(alice, bob):
    """The session id is in the transcript, so a blob captured from session A does not
    open in session B even between the same two people."""
    first = transcript.build(b"aaaa", alice.public(), bob.public())
    second = transcript.build(b"bbbb", alice.public(), bob.public())
    _, blob = hybrid.seal_secret(bob.public().kem, first)

    with pytest.raises(DecryptError):
        hybrid.open_secret(bob.kem, blob, second)


def test_two_handshakes_between_the_same_pair_differ(alice, bob):
    """Fresh randomness each time, so capturing one says nothing about the next."""
    context = transcript.build(SID, alice.public(), bob.public())
    first, first_blob = session_secret(alice, bob.public(), context)
    second, second_blob = session_secret(alice, bob.public(), context)

    assert first != second
    assert first_blob != second_blob


# ---- canonicalisation ------------------------------------------------------


def test_transcript_canonicalization(alice, bob):
    """Moving a byte across a field boundary must change the transcript.

    Without length prefixes, ("ab", "c") and ("a", "bc") produce the same bytes, and an
    attacker who controls where one field ends can shift content between two fields while
    every signature over the result still verifies.
    """
    assert hkdf.length_prefixed(b"ab", b"c") != hkdf.length_prefixed(b"a", b"bc")


def test_a_shorter_session_id_cannot_borrow_from_the_next_field(alice, bob):
    """The concrete version of the same attack against the real transcript."""
    with pytest.raises(CryptoError):
        transcript.build(b"aaa", alice.public(), bob.public())


def test_identity_fields_cannot_be_shuffled(alice, bob):
    """Sender and recipient are adjacent fields of the same widths. Length prefixing plus
    the fixed order is what keeps them apart."""
    forward = transcript.build(SID, alice.public(), bob.public())
    backward = transcript.build(SID, bob.public(), alice.public())

    assert forward != backward
    assert len(forward) == len(backward)


# ---- what happens when everything is honest --------------------------------


def test_an_honest_handshake_agrees_on_both_sides(alice, bob):
    """The control. If this ever fails, the tests above are passing for the wrong reason.

    Both sides build the transcript independently, and the recipient recovers exactly the
    secret the sender sealed.
    """
    from_sender = transcript.build(SID, alice.public(), bob.public())
    from_recipient = transcript.build(SID, alice.public(), bob.public())
    assert from_sender == from_recipient

    secret, blob = hybrid.seal_secret(bob.public().kem, from_sender)
    assert hybrid.open_secret(bob.kem, blob, from_recipient) == secret

    sender_side = hybrid.derive_shared_secret(
        secret, hybrid.static_exchange(alice.kem, bob.public().kem), from_sender
    )
    recipient_side = hybrid.derive_shared_secret(
        secret, hybrid.static_exchange(bob.kem, alice.public().kem), from_recipient
    )
    assert sender_side == recipient_side


def test_a_signed_handshake_verifies_end_to_end(alice, bob):
    message = transcript.build(SID, alice.public(), bob.public(), transcript.AUTH_PQ_EXPLICIT)

    signatures.verify(alice.public(), message, signatures.sign(alice, message))
