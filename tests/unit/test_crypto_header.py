"""The 12 byte header, its whitening, and the counter search that undoes it.

The counter search is the part worth the most attention. It exists because the keystream
depends on the counter and the counter is inside the header, and it is bounded because
without a bound a file containing nothing costs sixteen million HKDF calls to reject.
"""

import pytest

from sieng.common.errors import CryptoError, DecryptError
from sieng.crypto import header as hdr
from sieng.crypto.envelope import (
    AUTH_IMPLICIT,
    AUTH_PQ_EXPLICIT,
    EXTERNAL_BYTES,
    INLINE_BYTES,
    SIGNATURE_BYTES,
    SessionEnvelope,
    choose_mode,
    envelope_size,
)
from sieng.crypto.kem.hybrid import SEALED_BYTES

SID = b"\x01\x02\x03\x04"
SESSION_KEY = bytes(range(32))


def a_header(**kwargs):
    fields = {"session_id": SID, "counter": 7, "length": 1000}
    return hdr.Header(**{**fields, **kwargs})


# ---- the bit layout --------------------------------------------------------


def test_a_header_is_twelve_bytes():
    """Ninety-six coefficients. On a 512x512 cover at 0.05 bpnzAC that is about seven
    percent of everything available, which is why the size was argued over."""
    assert len(a_header().pack()) == hdr.HEADER_BYTES == 12
    assert hdr.HEADER_BITS == 96


def test_the_fields_land_in_the_documented_bytes():
    """Pinned against FORMAT_SPEC.md 3.2. A field one byte out still round trips through
    our own code and is unreadable by anyone else's."""
    packed = a_header(counter=0x0A0B0C, length=0x111213, flags=0b0010_0001).pack()

    assert packed[0] == (1 << 4) | 1
    assert packed[1:5] == SID
    assert packed[5:8] == b"\x0a\x0b\x0c"
    assert packed[8:11] == b"\x11\x12\x13"
    assert packed[11] == 0b0010_0001


def test_a_header_survives_the_round_trip():
    original = a_header(counter=1234, length=5678, flags=0b0011_0101)

    assert hdr.Header.unpack(original.pack()) == original


@pytest.mark.parametrize("counter", [0, 1, hdr.MAX_COUNTER])
def test_every_counter_in_range_round_trips(counter):
    assert hdr.Header.unpack(a_header(counter=counter).pack()).counter == counter


def test_a_counter_past_twenty_four_bits_is_refused():
    with pytest.raises(CryptoError, match="does not fit in 24 bits"):
        a_header(counter=hdr.MAX_COUNTER + 1)


def test_a_payload_too_long_to_describe_is_refused():
    """The length field is 24 bits, so a message over 16 MB cannot be described by a
    header at all. Better to say so than to truncate silently."""
    with pytest.raises(CryptoError, match="16777215 bytes per message"):
        a_header(length=hdr.MAX_LENGTH + 1)


def test_a_wrong_sized_session_id_is_refused():
    with pytest.raises(CryptoError, match="Session id"):
        a_header(session_id=b"abc")


def test_unpacking_the_wrong_number_of_bytes_is_refused():
    with pytest.raises(CryptoError, match="A header is 12 bytes"):
        hdr.Header.unpack(bytes(11))


# ---- flags -----------------------------------------------------------------


def test_the_reserved_bits_must_be_zero():
    """Unchecked spare bits are a channel an attacker can send data through, and a future
    version could not tell an old file from a tampered one."""
    with pytest.raises(CryptoError, match="reserved"):
        a_header(flags=0b1000_0000)
    with pytest.raises(CryptoError, match="reserved"):
        a_header(flags=0b0100_0000)


def test_the_flag_helper_sets_the_documented_bits():
    flags = hdr.build_flags(
        has_precover=True,
        multipart=True,
        envelope_mode=hdr.ENVELOPE_INLINE,
        pq_auth=True,
        bootstrap=True,
    )

    assert flags == 0b0011_0111


def test_the_envelope_mode_reads_back():
    for mode in (hdr.ENVELOPE_EXTERNAL, hdr.ENVELOPE_INLINE, hdr.ENVELOPE_MULTIPART):
        header = a_header(flags=hdr.build_flags(envelope_mode=mode))
        assert header.envelope_mode == mode


def test_the_reserved_envelope_mode_cannot_be_written():
    with pytest.raises(CryptoError, match="reserved and must never be written"):
        hdr.build_flags(envelope_mode=hdr.ENVELOPE_RESERVED)


def test_the_flag_properties_agree_with_the_bits():
    header = a_header(flags=hdr.build_flags(has_precover=True, pq_auth=True, bootstrap=True))

    assert header.has_precover is True
    assert header.is_pq_authenticated is True
    assert header.carries_envelope is True
    assert a_header(flags=0).has_precover is False


# ---- whitening -------------------------------------------------------------


def test_whitening_hides_the_constant_bytes():
    """Without it, version and suite are fixed and the reserved bits are zero, so the
    first byte of every file this program produces looks the same."""
    header = a_header()

    masked = hdr.whiten(header.pack(), SESSION_KEY, header.counter)

    assert masked != header.pack()
    assert masked[0] != header.pack()[0]


def test_whitening_is_its_own_inverse():
    header = a_header()

    masked = hdr.whiten(header.pack(), SESSION_KEY, header.counter)

    assert hdr.unwhiten(masked, SESSION_KEY, header.counter) == header.pack()


def test_every_counter_gets_a_different_keystream():
    """If the counter were left out of the info string, every header in a session would
    be masked identically, and XORing two of them would show where they differ."""
    streams = [hdr.keystream(SESSION_KEY, counter) for counter in range(50)]

    assert len(set(streams)) == 50


def test_two_headers_do_not_share_a_mask():
    first = hdr.whiten(a_header(counter=1).pack(), SESSION_KEY, 1)
    second = hdr.whiten(a_header(counter=2).pack(), SESSION_KEY, 2)

    assert first != second


def test_a_different_session_key_gives_a_different_mask():
    header = a_header()

    assert hdr.whiten(header.pack(), SESSION_KEY, 7) != hdr.whiten(header.pack(), bytes(32), 7)


# ---- the counter search ----------------------------------------------------


def test_the_receiver_finds_the_counter_it_was_not_told():
    """The chicken and egg problem: the keystream depends on the counter, and the counter
    is inside the header."""
    header = a_header(counter=5)
    masked = hdr.whiten(header.pack(), SESSION_KEY, 5)

    assert hdr.unwhiten_search(masked, SESSION_KEY, last_counter=0, max_skip=10) == header


def test_the_search_finds_the_counter_it_starts_on():
    header = a_header(counter=3)
    masked = hdr.whiten(header.pack(), SESSION_KEY, 3)

    assert hdr.unwhiten_search(masked, SESSION_KEY, last_counter=3, max_skip=1) == header


def test_a_counter_beyond_the_window_is_not_found():
    header = a_header(counter=50)
    masked = hdr.whiten(header.pack(), SESSION_KEY, 50)

    with pytest.raises(DecryptError):
        hdr.unwhiten_search(masked, SESSION_KEY, last_counter=0, max_skip=10)


def test_the_search_stops_at_the_limit_rather_than_running_to_the_end():
    """The whole reason for the bound. A file with nothing hidden in it never matches, and
    without a limit the receiver would work through sixteen million counters to say so.

    Measured by counting derivations rather than by timing, which would be flaky.
    """
    calls = []
    original = hdr.keystream

    def counting(session_key, counter, length=hdr.HEADER_BYTES):
        calls.append(counter)
        return original(session_key, counter, length)

    hdr.keystream = counting
    try:
        with pytest.raises(DecryptError):
            hdr.unwhiten_search(bytes(12), SESSION_KEY, last_counter=0, max_skip=25)
    finally:
        hdr.keystream = original

    assert len(calls) == 25


def test_random_bytes_are_rejected():
    """A cover with nothing in it must not produce a header by accident. Four independent
    conditions have to hold, so the chance is around one in four billion per candidate."""
    with pytest.raises(DecryptError):
        hdr.unwhiten_search(bytes(range(12)), SESSION_KEY, last_counter=0, max_skip=200)


def test_a_length_larger_than_the_carrier_is_rejected():
    """Part of what makes a false match unlikely, and it stops a corrupt header from
    asking the extractor for more bits than exist."""
    header = a_header(counter=2, length=900_000)
    masked = hdr.whiten(header.pack(), SESSION_KEY, 2)

    with pytest.raises(DecryptError):
        hdr.unwhiten_search(masked, SESSION_KEY, 0, max_skip=10, max_length=1000)
    assert hdr.unwhiten_search(masked, SESSION_KEY, 0, max_skip=10, max_length=1_000_000)


def test_the_wrong_session_key_finds_nothing():
    header = a_header(counter=2)
    masked = hdr.whiten(header.pack(), SESSION_KEY, 2)

    with pytest.raises(DecryptError):
        hdr.unwhiten_search(masked, bytes(32), last_counter=0, max_skip=50)


def test_a_search_window_below_one_is_refused():
    with pytest.raises(CryptoError, match="max_skip"):
        hdr.unwhiten_search(bytes(12), SESSION_KEY, 0, max_skip=0)


def test_a_failed_search_is_the_same_error_as_a_failed_decryption():
    """A caller that could tell "no counter matched" from "the payload did not decrypt"
    would learn whether a file holds anything at all."""
    with pytest.raises(DecryptError):
        hdr.unwhiten_search(bytes(12), SESSION_KEY, 0, max_skip=5)
    with pytest.raises(DecryptError):
        hdr.unwhiten_search(bytes(11), SESSION_KEY, 0, max_skip=5)


# ---- the envelope ----------------------------------------------------------


def an_envelope(**kwargs):
    fields = {
        "session_id": SID,
        "sender_fingerprint": bytes(32),
        "recipient_fingerprint": bytes(range(32)),
        "sealed_secret": bytes(SEALED_BYTES),
    }
    return SessionEnvelope(**{**fields, **kwargs})


def test_the_envelope_is_the_size_the_capacity_check_assumes():
    """These numbers changed with D14: one 1,168 byte HPKE blob instead of a 32 byte
    ephemeral plus a 1,088 byte ML-KEM ciphertext."""
    assert INLINE_BYTES == 1240
    assert EXTERNAL_BYTES == 1244
    assert len(an_envelope().pack_inline()) == 1240
    assert len(an_envelope().pack_external()) == 1244


def test_the_external_form_is_recognisable_and_the_inline_form_is_not():
    """A .sess file may announce itself; anything embedded in an image may not. Every bit
    that goes into a cover has to be indistinguishable from noise."""
    envelope = an_envelope()

    assert envelope.pack_external().startswith(b"SI3S")
    assert not envelope.pack_inline().startswith(b"SI3S")
    assert envelope.pack_external()[4:] == envelope.pack_inline()


def test_an_envelope_survives_both_round_trips():
    envelope = an_envelope()

    assert SessionEnvelope.unpack_external(envelope.pack_external()) == envelope
    assert SessionEnvelope.unpack_inline(envelope.pack_inline()) == envelope


def test_a_signed_envelope_round_trips_too():
    envelope = an_envelope(auth_mode=AUTH_PQ_EXPLICIT, signature=bytes(SIGNATURE_BYTES))

    assert SessionEnvelope.unpack_inline(envelope.pack_inline()) == envelope
    assert envelope.size() == INLINE_BYTES + SIGNATURE_BYTES


def test_a_signature_of_the_wrong_size_is_refused():
    """Ed25519 and ML-DSA together. One of the two verifying is not enough, so one of the
    two being present is not either."""
    with pytest.raises(CryptoError, match="Both Ed25519 and ML-DSA are required"):
        an_envelope(auth_mode=AUTH_PQ_EXPLICIT, signature=bytes(64))


def test_an_implicit_envelope_carries_no_signature():
    with pytest.raises(CryptoError, match="needs a 0 byte signature"):
        an_envelope(signature=bytes(SIGNATURE_BYTES))


def test_a_file_that_is_not_a_session_file_is_refused():
    with pytest.raises(CryptoError, match="not a SIENG3 session file"):
        SessionEnvelope.unpack_external(b"NOPE" + bytes(INLINE_BYTES))


def test_an_envelope_of_the_wrong_length_is_refused():
    with pytest.raises(CryptoError, match="A session envelope is"):
        SessionEnvelope.unpack_inline(bytes(INLINE_BYTES - 1))


def test_an_unknown_version_is_refused():
    blob = bytearray(an_envelope().pack_inline())
    blob[0] = 99

    with pytest.raises(CryptoError, match="version 99"):
        SessionEnvelope.unpack_inline(bytes(blob))


# ---- choosing the mode -----------------------------------------------------


def test_the_research_image_gets_an_external_envelope():
    """512x512 at 0.1 bpnzAC is 2,600 bits against an envelope of 9,920. Inline would mean
    the envelope is four times the size of everything available."""
    assert choose_mode(26_000, 0.1) == hdr.ENVELOPE_EXTERNAL


@pytest.mark.parametrize(
    ("nnz_ac", "expected"),
    [
        (26_000, hdr.ENVELOPE_EXTERNAL),
        (130_000, hdr.ENVELOPE_EXTERNAL),
        (500_000, hdr.ENVELOPE_EXTERNAL),
        (1_500_000, hdr.ENVELOPE_INLINE),
    ],
)
def test_the_documented_table_is_what_the_code_produces(nnz_ac, expected):
    """Pinned against FORMAT_SPEC.md 4.3. The table there was corrected to match this
    formula: the 2048x1536 row used to claim INLINE at 50,000 bits, which is well under
    the eight times headroom the formula requires."""
    assert choose_mode(nnz_ac, 0.1) == expected


def test_the_cutoff_is_where_the_arithmetic_says():
    """9,920 bits of envelope times eight is 79,360, so at 0.1 bpnzAC the switch happens
    at 793,600 non-zero AC coefficients."""
    assert choose_mode(793_600, 0.1) == hdr.ENVELOPE_INLINE
    assert choose_mode(793_500, 0.1) == hdr.ENVELOPE_EXTERNAL


def test_a_higher_rate_makes_inline_reachable_sooner():
    assert choose_mode(200_000, 0.1) == hdr.ENVELOPE_EXTERNAL
    assert choose_mode(200_000, 0.4) == hdr.ENVELOPE_INLINE


def test_signing_pushes_the_envelope_out_of_the_image():
    """A signed envelope is 4,613 bytes. A cover that could hold an unsigned one inline
    cannot necessarily hold this."""
    assert choose_mode(1_500_000, 0.1) == hdr.ENVELOPE_INLINE
    assert choose_mode(1_500_000, 0.1, AUTH_PQ_EXPLICIT) == hdr.ENVELOPE_EXTERNAL


def test_splitting_across_files_makes_multipart_reachable():
    """One file cannot hold it, but ten between them can."""
    assert choose_mode(100_000, 0.1, AUTH_IMPLICIT, expected_file_count=1) == (
        hdr.ENVELOPE_EXTERNAL
    )
    assert choose_mode(100_000, 0.1, AUTH_IMPLICIT, expected_file_count=10) == (
        hdr.ENVELOPE_MULTIPART
    )


def test_the_envelope_size_helper_matches_what_is_produced():
    assert envelope_size(AUTH_IMPLICIT) == len(an_envelope().pack_inline())
    assert envelope_size(AUTH_IMPLICIT, inline=False) == len(an_envelope().pack_external())


@pytest.mark.parametrize("rate", [0, -0.1])
def test_a_rate_that_is_not_positive_is_refused(rate):
    with pytest.raises(CryptoError, match="Payload rate"):
        choose_mode(26_000, rate)
