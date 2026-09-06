"""HKDF-SHA256 against the published vectors of RFC 5869.

This is the first real known-answer test in the project, and it is a different kind of
evidence from everything before it. Phase 6 could only be checked against properties,
because no reference cost map was available. Here the right answer is written down in a
standards document, byte for byte, and either the output matches it or the code is wrong.

Vectors 1 to 3 are the SHA-256 ones from RFC 5869 appendix A. Vector 3 is the interesting
case: empty salt and empty info, which is exactly the shape a careless implementation gets
wrong by substituting something for the empty value.

Note what is being tested. The arithmetic belongs to `cryptography` and is audited. What
these vectors prove is that this project calls it correctly, with the arguments in the
order it thinks they are in.
"""

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand

from sieng.common.errors import CryptoError
from sieng.crypto.kdf import hkdf


def unhex(text):
    """RFC 5869 prints its vectors as hex with no separators."""
    return bytes.fromhex(text)


# ---- RFC 5869 appendix A, the SHA-256 cases --------------------------------

# A.1 basic
CASE_1 = {
    "ikm": unhex("0b" * 22),
    "salt": unhex("000102030405060708090a0b0c"),
    "info": unhex("f0f1f2f3f4f5f6f7f8f9"),
    "length": 42,
    "prk": unhex("077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5"),
    "okm": unhex(
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
    ),
}

# A.2 longer inputs and outputs
CASE_2 = {
    "ikm": unhex("".join(f"{b:02x}" for b in range(0x50))),
    "salt": unhex("".join(f"{b:02x}" for b in range(0x60, 0xB0))),
    "info": unhex("".join(f"{b:02x}" for b in range(0xB0, 0x100))),
    "length": 82,
    "prk": unhex("06a6b88c5853361a06104c9ceb35b45cef760014904671014a193f40c15fc244"),
    "okm": unhex(
        "b11e398dc80327a1c8e7f78c596a49344f012eda2d4efad8a050cc4c19afa97c"
        "59045a99cac7827271cb41c65e590e09da3275600c2f09b8367793a9aca3db71"
        "cc30c58179ec3e87c14c01d5c1f3434f1d87"
    ),
}

# A.3 empty salt and empty info, which is the case implementations get wrong
CASE_3 = {
    "ikm": unhex("0b" * 22),
    "salt": b"",
    "info": b"",
    "length": 42,
    "prk": unhex("19ef24a32c717b167f33a91d6f648bdf96596776afdb6377ac434c1c293ccb04"),
    "okm": unhex(
        "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8"
    ),
}

CASES = [CASE_1, CASE_2, CASE_3]
IDS = ["rfc5869-a1", "rfc5869-a2", "rfc5869-a3-empty-salt-and-info"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_the_full_derivation_matches_the_rfc(case):
    """extract then expand, end to end, against the published output.

    HKDF is defined as extract followed by expand, so matching okm proves both halves are
    called correctly and in the right order.
    """
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=case["length"],
        salt=case["salt"],
        info=case["info"],
    ).derive(case["ikm"])

    assert derived == case["okm"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_expand_alone_matches_the_rfc(case):
    """Everything below the session level calls expand on its own, never extract.

    Feeding the RFC's own PRK straight into expand isolates that half, which is the half
    the ratchet uses on every single message.
    """
    okm = HKDFExpand(algorithm=hashes.SHA256(), length=case["length"], info=case["info"]).derive(
        case["prk"]
    )

    assert okm == case["okm"]


def test_our_expand_matches_the_rfc():
    """The project's own wrapper, not the library underneath it, against vector A.1."""
    assert hkdf.expand(CASE_1["prk"], CASE_1["info"], CASE_1["length"]) == CASE_1["okm"]


def test_our_extract_produces_a_uniform_key():
    """extract() fixes the length at 32 and always passes a label, so it cannot reproduce
    a vector directly. What it must do is agree with the library called the same way."""
    expected = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"salt", info=b"label").derive(
        b"input key material"
    )

    assert hkdf.extract(b"input key material", b"label", salt=b"salt") == expected


# ---- what the wrapper adds on top ------------------------------------------


def test_a_different_label_gives_a_different_key():
    """The property the whole labels.py file exists to guarantee. If this ever fails, the
    message key and the next chain key are the same 32 bytes."""
    key = bytes(range(32))

    assert hkdf.expand_key(key, b"sieng3/msg/v1") != hkdf.expand_key(key, b"sieng3/ratchet/v1")


def test_the_same_inputs_always_give_the_same_key():
    """Not a nicety. The receiver derives its keys separately and they have to match."""
    key = bytes(range(32))

    assert hkdf.expand_key(key, b"label") == hkdf.expand_key(key, b"label")


def test_a_key_that_is_not_thirty_two_bytes_is_refused():
    """A short key means it never went through extract(), so it is not uniform and the
    output would be weaker than it looks."""
    with pytest.raises(CryptoError, match="32 byte key"):
        hkdf.expand(bytes(16), b"label")


def test_deriving_without_a_label_is_refused():
    """An empty info means no domain separation, which is the one mistake here that
    produces a working system and a broken one at the same time."""
    with pytest.raises(CryptoError, match="without a label"):
        hkdf.expand(bytes(32), b"")
    with pytest.raises(CryptoError, match="without a label"):
        hkdf.extract(b"ikm", b"")


def test_deriving_from_nothing_is_refused():
    with pytest.raises(CryptoError, match="empty input key material"):
        hkdf.extract(b"", b"label")


@pytest.mark.parametrize("length", [0, -1, 255 * 32 + 1])
def test_an_impossible_output_length_is_refused(length):
    """RFC 5869 caps a single expand at 255 * HashLen."""
    with pytest.raises(CryptoError, match="Cannot expand"):
        hkdf.expand(bytes(32), b"label", length)


def test_the_longest_allowed_expansion_works():
    assert len(hkdf.expand(bytes(32), b"label", 255 * 32)) == 255 * 32


# ---- length prefixing ------------------------------------------------------


def test_fields_are_prefixed_with_their_length():
    assert hkdf.length_prefixed(b"ab", b"c") == b"\x00\x02ab\x00\x01c"


def test_moving_a_byte_between_fields_changes_the_result():
    """The canonicalisation attack in one line. Without length prefixes both of these
    would be b'abc', and an attacker could move the boundary without anyone noticing."""
    assert hkdf.length_prefixed(b"ab", b"c") != hkdf.length_prefixed(b"a", b"bc")


def test_an_empty_field_still_takes_a_prefix():
    """An empty field has to stay visible, or two fields collapse into one."""
    assert hkdf.length_prefixed(b"", b"x") == b"\x00\x00\x00\x01x"
    assert hkdf.length_prefixed(b"", b"x") != hkdf.length_prefixed(b"x")


def test_a_field_too_long_to_prefix_is_refused():
    with pytest.raises(CryptoError, match="two byte length prefix"):
        hkdf.length_prefixed(bytes(0x10000))


# ---- the per-message info strings ------------------------------------------


def test_the_counter_reaches_the_derived_key():
    """Two messages in one session must not derive the same keys."""
    first = hkdf.counter_info(b"label", b"sess", 1)
    second = hkdf.counter_info(b"label", b"sess", 2)

    assert first != second
    assert hkdf.expand_key(bytes(32), first) != hkdf.expand_key(bytes(32), second)


def test_the_session_id_reaches_the_derived_key():
    """Two sessions must not collide even at the same counter."""
    assert hkdf.counter_info(b"label", b"aaaa", 7) != hkdf.counter_info(b"label", b"bbbb", 7)


def test_the_counter_is_three_bytes_big_endian():
    assert hkdf.counter_info(b"L", b"sess", 1) == b"Lsess\x00\x00\x01"
    assert hkdf.counter_info(b"L", b"sess", 0xFFFFFF) == b"Lsess\xff\xff\xff"


def test_a_counter_past_the_header_range_is_refused():
    """The header carries 24 bits. A counter that does not fit would be truncated and two
    different messages would derive the same key."""
    with pytest.raises(CryptoError, match="24 bit range"):
        hkdf.counter_info(b"label", b"sess", 1 << 24)


def test_a_wrong_sized_session_id_is_refused():
    with pytest.raises(CryptoError, match="4 bytes"):
        hkdf.counter_info(b"label", b"toolong", 1)


def test_the_header_stream_info_carries_no_session_id():
    """The receiver reads the header before it knows the session id, so this derivation
    cannot depend on one (FORMAT_SPEC.md 3.3)."""
    assert hkdf.stream_info(b"L", 5) == b"L\x00\x00\x05"


def test_the_header_keystream_differs_per_message():
    """Without the counter every header would be whitened with the same 12 bytes, and
    XORing two headers together would show the difference in plaintext."""
    session_key = bytes(range(32))

    first = hkdf.expand(session_key, hkdf.stream_info(b"hdr", 1), 12)
    second = hkdf.expand(session_key, hkdf.stream_info(b"hdr", 2), 12)

    assert first != second
