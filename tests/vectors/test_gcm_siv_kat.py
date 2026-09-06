"""AES-256-GCM-SIV against the published vectors of RFC 8452 appendix C.2.

Every payload this project produces goes through this function, so "it round trips" is not
evidence of anything: a wrong implementation round trips perfectly with itself. What makes
the output correct is that it equals the bytes in the standard.

The cases below cover the boundaries that matter. Empty plaintext, because an empty
message must still produce a tag. Lengths of 8, 12 and 16, because GCM-SIV works in 16
byte blocks and the partial ones are where padding mistakes live. And a case with AAD,
because this project always passes AAD and a vector with an empty one would not exercise
it at all.
"""

import pytest

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto.aead import gcm_siv

KEY = bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000000")
NONCE = bytes.fromhex("030000000000000000000000")


def unhex(text):
    return bytes.fromhex(text)


# ---- RFC 8452 appendix C.2 -------------------------------------------------

VECTORS = [
    ("empty", b"", b"", "07f5f4169bbf55a8400cd47ea6fd400f"),
    (
        "8-bytes",
        unhex("0100000000000000"),
        b"",
        "c2ef328e5c71c83b843122130f7364b761e0b97427e3df28",
    ),
    (
        "12-bytes",
        unhex("010000000000000000000000"),
        b"",
        "9aab2aeb3faa0a34aea8e2b18ca50da9ae6559e48fd10f6e5c9ca17e",
    ),
    (
        "16-bytes-one-whole-block",
        unhex("01000000000000000000000000000000"),
        b"",
        "85a01b63025ba19b7fd3ddfc033b3e76c9eac6fa700942702e90862383c6c366",
    ),
    (
        "32-bytes-two-blocks",
        unhex("0100000000000000000000000000000002000000000000000000000000000000"),
        b"",
        "4a6a9db4c8c6549201b9edb53006cba821ec9cf850948a7c86c68ac7539d027f"
        "e819e63abcd020b006a976397632eb5d",
    ),
    (
        "8-bytes-with-aad",
        unhex("0200000000000000"),
        unhex("01"),
        "1de22967237a813291213f267e3b452f02d01ae33e4ec854",
    ),
]

IDS = [name for name, _, _, _ in VECTORS]


@pytest.mark.parametrize(("name", "plaintext", "aad", "expected"), VECTORS, ids=IDS)
def test_seal_matches_the_rfc(name, plaintext, aad, expected):
    """The bytes on the wire, against the bytes in the standard."""
    assert gcm_siv.seal(KEY, NONCE, plaintext, aad).hex() == expected


@pytest.mark.parametrize(("name", "plaintext", "aad", "expected"), VECTORS, ids=IDS)
def test_open_recovers_the_rfc_plaintext(name, plaintext, aad, expected):
    """Decrypting the standard's own ciphertext, not one this code just produced."""
    assert gcm_siv.open_(KEY, NONCE, unhex(expected), aad) == plaintext


# ---- the property SIV was chosen for ---------------------------------------


def test_a_repeated_nonce_leaks_only_that_two_messages_were_equal():
    """The whole reason for SIV over plain GCM.

    A ratchet counter can go backwards when a user restores a backup or copies a folder,
    which reuses a nonce. Under GCM that would leak the XOR of the plaintexts and the
    authentication key itself. Under SIV, two different plaintexts still give unrelated
    ciphertexts, and the only thing an observer learns is when two are identical.
    """
    first = gcm_siv.seal(KEY, NONCE, b"attack at dawn", b"")
    second = gcm_siv.seal(KEY, NONCE, b"attack at dusk", b"")
    same_again = gcm_siv.seal(KEY, NONCE, b"attack at dawn", b"")

    assert first != second
    assert first == same_again


def test_the_ciphertext_is_the_plaintext_length_plus_a_tag():
    """Capacity has to be checked before encrypting, so this length must be predictable."""
    for size in (0, 1, 15, 16, 17, 1000):
        assert len(gcm_siv.seal(KEY, NONCE, bytes(size), b"")) == gcm_siv.sealed_length(size)
        assert gcm_siv.sealed_length(size) == size + 16


# ---- every failure looks the same ------------------------------------------


def test_a_tampered_ciphertext_is_refused():
    sealed = bytearray(gcm_siv.seal(KEY, NONCE, b"payload", b"aad"))
    sealed[0] ^= 1

    with pytest.raises(DecryptError):
        gcm_siv.open_(KEY, NONCE, bytes(sealed), b"aad")


def test_a_tampered_tag_is_refused():
    sealed = bytearray(gcm_siv.seal(KEY, NONCE, b"payload", b"aad"))
    sealed[-1] ^= 1

    with pytest.raises(DecryptError):
        gcm_siv.open_(KEY, NONCE, bytes(sealed), b"aad")


def test_the_wrong_aad_is_refused():
    """This is what stops a ciphertext being lifted out of one image and dropped into
    another: the aad carries the carrier fingerprint (THREAT_MODEL.md S10)."""
    sealed = gcm_siv.seal(KEY, NONCE, b"payload", b"image-one")

    with pytest.raises(DecryptError):
        gcm_siv.open_(KEY, NONCE, sealed, b"image-two")


def test_the_wrong_key_is_refused():
    sealed = gcm_siv.seal(KEY, NONCE, b"payload", b"")

    with pytest.raises(DecryptError):
        gcm_siv.open_(bytes(32), NONCE, sealed, b"")


def test_the_wrong_nonce_is_refused():
    sealed = gcm_siv.seal(KEY, NONCE, b"payload", b"")

    with pytest.raises(DecryptError):
        gcm_siv.open_(KEY, bytes(12), sealed, b"")


def test_a_ciphertext_too_short_to_hold_a_tag_is_refused():
    with pytest.raises(DecryptError):
        gcm_siv.open_(KEY, NONCE, bytes(15), b"")


def test_every_failure_raises_the_same_bare_error():
    """The error must not say why. A caller that can tell a wrong key from a wrong aad can
    be used as an oracle, so DecryptError carries no message and no attributes."""
    sealed = gcm_siv.seal(KEY, NONCE, b"payload", b"aad")
    tampered = bytes([sealed[0] ^ 1]) + sealed[1:]

    failures = []
    for key, nonce, ciphertext, aad in (
        (bytes(32), NONCE, sealed, b"aad"),
        (KEY, bytes(12), sealed, b"aad"),
        (KEY, NONCE, tampered, b"aad"),
        (KEY, NONCE, sealed, b"different"),
        (KEY, NONCE, bytes(15), b"aad"),
    ):
        with pytest.raises(DecryptError) as error:
            gcm_siv.open_(key, nonce, ciphertext, aad)
        failures.append((type(error.value), str(error.value), error.value.args))

    assert len(set(failures)) == 1
    assert failures[0] == (DecryptError, DecryptError.MESSAGE, (DecryptError.MESSAGE,))


# ---- inputs that are a programming error, not an attack --------------------


@pytest.mark.parametrize("size", [16, 24, 31, 33])
def test_a_key_that_is_not_thirty_two_bytes_is_refused(size):
    """A 16 byte key would quietly select AES-128 in some libraries. Here it is refused,
    and as CryptoError rather than DecryptError, because it is a bug in our code."""
    with pytest.raises(CryptoError, match="32 byte key"):
        gcm_siv.seal(bytes(size), NONCE, b"payload", b"")


@pytest.mark.parametrize("size", [0, 11, 13, 16])
def test_a_nonce_that_is_not_twelve_bytes_is_refused(size):
    with pytest.raises(CryptoError, match="12 byte nonce"):
        gcm_siv.seal(KEY, bytes(size), b"payload", b"")


def test_a_bad_key_size_is_refused_on_the_way_out_too():
    """The check has to be on open_ as well, or a wrong sized key becomes a DecryptError
    and a real bug gets mistaken for a wrong password."""
    with pytest.raises(CryptoError, match="32 byte key"):
        gcm_siv.open_(bytes(16), NONCE, bytes(32), b"")


def test_a_negative_length_is_refused():
    with pytest.raises(CryptoError, match="cannot be negative"):
        gcm_siv.sealed_length(-1)
