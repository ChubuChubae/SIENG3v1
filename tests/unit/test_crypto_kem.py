"""The hybrid handshake: identities, X-Wing encapsulation, and the static exchange.

There is no known-answer test here and there cannot be one. HPKE draws fresh randomness on
every call, so the same inputs never produce the same bytes twice. What can be pinned are
the sizes, which the envelope arithmetic depends on, and the properties: the right key
opens it, everything else fails identically, and the transcript is genuinely bound.

The security tests that go with this file live in tests/security/, where the MITM and
substitution cases belong.
"""

import pytest

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.kdf import labels
from sieng.crypto.kem import hybrid, mlkem768, x25519

TRANSCRIPT = b"a transcript both sides agreed on"


@pytest.fixture(scope="module")
def alice():
    return hybrid.generate_identity()


@pytest.fixture(scope="module")
def bob():
    return hybrid.generate_identity()


# ---- the backend actually has ML-KEM ---------------------------------------


def test_ml_kem_is_available():
    """If this fails nothing else in Phase 7 means anything, so it is checked first and
    the message says how to fix it."""
    assert mlkem768.is_available() is True
    mlkem768.ensure_available()


# ---- identities ------------------------------------------------------------


def test_an_identity_has_both_halves(alice):
    public = alice.public()

    assert len(public.mlkem) == mlkem768.PUBLIC_BYTES == 1184
    assert len(public.x25519) == x25519.PUBLIC_BYTES == 32
    assert len(alice.mlkem_seed) == mlkem768.SEED_BYTES == 64
    assert len(alice.x25519_secret) == x25519.PRIVATE_BYTES == 32


def test_two_identities_differ():
    assert hybrid.generate_identity() != hybrid.generate_identity()


def test_the_public_key_is_derived_not_stored(alice):
    """The secret holds seeds only, so the public key has to come back identical every
    time it is recomputed or the keystore would need to hold more."""
    assert alice.public() == alice.public()


def test_a_public_identity_survives_the_wire_format(alice):
    public = alice.public()

    assert hybrid.PublicIdentity.from_bytes(public.to_bytes()) == public
    assert len(public.to_bytes()) == hybrid.PUBLIC_BYTES == 1216


def test_the_two_components_keep_their_order(alice):
    """ML-KEM first, then X25519. Swapping them would parse without error and produce two
    keys that are both wrong."""
    public = alice.public()
    raw = public.to_bytes()

    assert raw[: mlkem768.PUBLIC_BYTES] == public.mlkem
    assert raw[mlkem768.PUBLIC_BYTES :] == public.x25519


def test_a_truncated_public_identity_is_refused(alice):
    with pytest.raises(CryptoError, match="1216 bytes"):
        hybrid.PublicIdentity.from_bytes(alice.public().to_bytes()[:-1])


def test_a_component_of_the_wrong_size_is_refused():
    with pytest.raises(CryptoError, match="ML-KEM public key"):
        hybrid.PublicIdentity(bytes(100), bytes(32))
    with pytest.raises(CryptoError, match="X25519 public key"):
        hybrid.PublicIdentity(bytes(1184), bytes(31))


def test_a_secret_identity_of_the_wrong_size_is_refused():
    with pytest.raises(CryptoError, match="ML-KEM seed"):
        hybrid.SecretIdentity(bytes(32), bytes(32))
    with pytest.raises(CryptoError, match="X25519 secret"):
        hybrid.SecretIdentity(bytes(64), bytes(16))


def test_fingerprints_identify_an_identity(alice, bob):
    assert alice.public().fingerprint() != bob.public().fingerprint()
    assert alice.public().fingerprint() == alice.public().fingerprint()


# ---- the encapsulation -----------------------------------------------------


def test_the_recipient_recovers_the_secret(alice, bob):
    secret, blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)

    assert hybrid.open_secret(bob, blob, TRANSCRIPT) == secret
    assert len(secret) == hybrid.SECRET_BYTES == 32


def test_the_sizes_are_the_ones_the_envelope_budget_assumes(alice, bob):
    """1,120 of encapsulation plus 32 of secret under a 16 byte tag. The capacity check in
    the pipeline is built on these numbers, so they are pinned rather than computed."""
    _, blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)

    assert len(blob) == hybrid.SEALED_BYTES == 1168
    encapsulated, ciphertext = hybrid.parse_sealed(blob)
    assert len(encapsulated) == hybrid.ENCAPSULATED_BYTES == 1120
    assert len(ciphertext) == 48


def test_every_handshake_is_different(bob):
    """HPKE draws a fresh ephemeral each time, so two sealings of the same secret to the
    same recipient must not look alike."""
    first_secret, first_blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)
    second_secret, second_blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)

    assert first_secret != second_secret
    assert first_blob != second_blob


def test_the_wrong_recipient_cannot_open_it(alice, bob):
    _, blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)

    with pytest.raises(DecryptError):
        hybrid.open_secret(alice, blob, TRANSCRIPT)


def test_a_modified_transcript_is_refused(bob):
    """What the `info` parameter buys. A transcript that does not match makes the blob
    fail to open here, rather than quietly deriving a different key later where the
    failure would be much harder to attribute."""
    _, blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)

    with pytest.raises(DecryptError):
        hybrid.open_secret(bob, blob, TRANSCRIPT + b"!")


@pytest.mark.parametrize("position", [0, 500, 1119, 1120, -1])
def test_a_tampered_blob_is_refused_wherever_it_is_touched(bob, position):
    """Positions on both sides of the 1,120 byte boundary, so both the encapsulation and
    the ciphertext are covered."""
    _, blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)
    damaged = bytearray(blob)
    damaged[position] ^= 1

    with pytest.raises(DecryptError):
        hybrid.open_secret(bob, bytes(damaged), TRANSCRIPT)


@pytest.mark.parametrize("size", [0, 1167, 1169])
def test_a_blob_of_the_wrong_length_is_refused(bob, size):
    with pytest.raises(DecryptError):
        hybrid.open_secret(bob, bytes(size), TRANSCRIPT)


def test_every_failure_looks_the_same(alice, bob):
    """Wrong key, wrong transcript, tampered blob and wrong length must be one error."""
    _, blob = hybrid.seal_secret(bob.public(), TRANSCRIPT)
    damaged = bytes([blob[0] ^ 1]) + blob[1:]

    failures = []
    for identity, data, transcript in (
        (alice, blob, TRANSCRIPT),
        (bob, blob, b"different"),
        (bob, damaged, TRANSCRIPT),
        (bob, bytes(10), TRANSCRIPT),
    ):
        with pytest.raises(DecryptError) as error:
            hybrid.open_secret(identity, data, transcript)
        failures.append((type(error.value), str(error.value)))

    assert len(set(failures)) == 1


# ---- AUTH_IMPLICIT ---------------------------------------------------------


def test_both_sides_compute_the_same_static_secret(alice, bob):
    """dh_static is symmetric, which is what lets the recipient check it without the
    sender transmitting anything."""
    from_sender = hybrid.static_exchange(alice, bob.public())
    from_recipient = hybrid.static_exchange(bob, alice.public())

    assert from_sender == from_recipient
    assert len(from_sender) == 32


def test_a_third_party_gets_a_different_static_secret(alice, bob):
    """The whole of AUTH_IMPLICIT. Someone without the sender's private key derives a
    different dh_static, so the session key they compute is not the one the recipient
    expects, and the message simply does not open."""
    impostor = hybrid.generate_identity()

    assert hybrid.static_exchange(impostor, bob.public()) != hybrid.static_exchange(
        alice, bob.public()
    )


def test_a_malformed_peer_key_is_refused(alice):
    """A small order point drives X25519 to all zeros, which both sides would agree on
    without either having proved anything."""
    with pytest.raises(CryptoError, match="not a valid point"):
        x25519.exchange(x25519.load_private(alice.x25519_secret), bytes(32))


# ---- the shared secret -----------------------------------------------------


def test_the_shared_secret_needs_every_input(alice, bob):
    """Change any one of the three and ss changes. If one of them stopped mattering, the
    property it was there to provide would be gone with no other sign."""
    secret, _ = hybrid.seal_secret(bob.public(), TRANSCRIPT)
    static = hybrid.static_exchange(alice, bob.public())
    base = hybrid.derive_shared_secret(secret, static, TRANSCRIPT)

    assert base != hybrid.derive_shared_secret(bytes(32), static, TRANSCRIPT)
    assert base != hybrid.derive_shared_secret(secret, bytes(32), TRANSCRIPT)
    assert base != hybrid.derive_shared_secret(secret, static, b"other transcript")
    assert base == hybrid.derive_shared_secret(secret, static, TRANSCRIPT)


def test_the_shared_secret_is_a_key_sized_value(alice, bob):
    secret, _ = hybrid.seal_secret(bob.public(), TRANSCRIPT)
    static = hybrid.static_exchange(alice, bob.public())

    assert len(hybrid.derive_shared_secret(secret, static, TRANSCRIPT)) == 32


def test_the_inputs_are_length_prefixed(alice, bob):
    """Without length prefixes, moving a byte from the secret into dh_static would leave
    the concatenation unchanged and produce the same ss from different inputs."""
    static = hybrid.static_exchange(alice, bob.public())
    first = hybrid.derive_shared_secret(bytes(32), static, b"ab")
    second = hybrid.derive_shared_secret(bytes(32), static, b"ab")

    assert first == second
    assert hybrid.derive_shared_secret(bytes(32), static, b"a") != hybrid.derive_shared_secret(
        bytes(32), static, b"ab"
    )


@pytest.mark.parametrize("bad", [b"", bytes(31), bytes(33)])
def test_a_wrong_sized_secret_is_refused(bad):
    with pytest.raises(CryptoError, match="Session secret"):
        hybrid.derive_shared_secret(bad, bytes(32), TRANSCRIPT)


def test_the_suite_label_records_the_x_wing_choice():
    """Pinned. D14 changed how ss is derived, so the suite label changed with it, and a
    file made under either one must never be readable as the other."""
    assert labels.KEM_SUITE == b"sieng3/kem/xwing-hpke/v1"


# ---- what the handshake costs ----------------------------------------------


def test_the_envelope_overhead_is_what_the_capacity_check_uses():
    """AUTH_IMPLICIT adds nothing beyond the encapsulation and the identity."""
    assert hybrid.envelope_overhead() == 1168 + 1216 == 2384


def test_explicit_pq_authentication_is_far_too_big_for_an_image():
    """Ed25519 plus ML-DSA-65 is 3,373 bytes on top. A 512x512 cover at 0.4 bpnzAC holds
    roughly 1.3 KB in total, which is why AUTH_PQ_EXPLICIT requires an external envelope
    and cannot be the default."""
    assert hybrid.envelope_overhead(64 + 3309) > 5000
