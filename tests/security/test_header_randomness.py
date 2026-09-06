"""Whitened headers must be indistinguishable from random bits.

This is the test the whitening exists to pass. An unwhitened header is mostly constant:
the version and suite nibbles never change, the reserved flag bits are always zero, and
the top bits of a modest length field are too. A steganalyst does not have to break
anything to use that, they have to notice it once, and then every file this program has
ever produced is identifiable.

Two standard tests from NIST SP 800-22, both on the bits as they would be embedded:

    monobit   are there as many ones as zeros? Catches a mask that leaves a constant
              field showing through.
    runs      do the bits alternate at the rate randomness would? Catches structure that
              monobit cannot see, such as whole bytes that never change while the overall
              balance stays right.

The thresholds are the conventional p >= 0.01. These tests are deterministic: the headers
are built from a fixed key and consecutive counters, so a failure is a real regression
rather than an unlucky run.

A pass here is not proof of security. It is proof that the obvious giveaway is gone.
"""

import math
from itertools import pairwise

import pytest

from sieng.crypto import header as hdr

SESSION_KEY = bytes(range(32))
SAMPLE = 10_000
ALPHA = 0.01


def whitened_bits(count=SAMPLE):
    """The bit string that `count` consecutive headers would put into a cover.

    Deliberately the worst case for the whitening: the same session, consecutive counters,
    and a payload length that barely moves. Everything that varies between these headers
    is the counter, so any structure left over is the whitening's fault.
    """
    bits: list[int] = []
    for counter in range(count):
        header = hdr.Header(session_id=b"\x11\x22\x33\x44", counter=counter, length=1024)
        masked = hdr.whiten(header.pack(), SESSION_KEY, counter)
        bits.extend((byte >> shift) & 1 for byte in masked for shift in range(7, -1, -1))
    return bits


@pytest.fixture(scope="module")
def bits():
    return whitened_bits()


def monobit_p_value(bits):
    """NIST SP 800-22 2.1. Are there as many ones as zeros?"""
    total = sum(1 if bit else -1 for bit in bits)
    return math.erfc(abs(total) / math.sqrt(2 * len(bits)))


def runs_p_value(bits):
    """NIST SP 800-22 2.3. Do the bits alternate at the rate randomness would?

    Only meaningful when the proportion of ones is already close to a half, which monobit
    establishes, so that precondition is asserted rather than assumed.
    """
    n = len(bits)
    proportion = sum(bits) / n
    assert abs(proportion - 0.5) < 2 / math.sqrt(n), "monobit must pass before runs means anything"

    runs = 1 + sum(1 for a, b in pairwise(bits) if a != b)
    expected = 2 * n * proportion * (1 - proportion)
    spread = 2 * math.sqrt(2 * n) * proportion * (1 - proportion)
    return math.erfc(abs(runs - expected) / spread)


# ---- the whitened bits -----------------------------------------------------


def test_the_sample_is_the_size_the_dod_asks_for():
    assert len(whitened_bits(SAMPLE)) == SAMPLE * hdr.HEADER_BITS == 960_000


def test_whitened_headers_pass_the_monobit_test(bits):
    assert monobit_p_value(bits) >= ALPHA


def test_whitened_headers_pass_the_runs_test(bits):
    assert runs_p_value(bits) >= ALPHA


def test_no_bit_position_is_stuck(bits):
    """Per position across all headers, not across the whole stream. A constant field
    would show up here even when the overall balance is fine, and this is exactly the
    failure mode whitening exists to remove."""
    for position in range(hdr.HEADER_BITS):
        column = bits[position :: hdr.HEADER_BITS]
        ones = sum(column)
        assert 0.4 < ones / len(column) < 0.6, f"bit {position} is biased"


def test_no_byte_value_dominates(bits):
    """The first byte of an unwhitened header is always 0x11. If any byte value takes
    much more than its share, something is showing through."""
    first_bytes = []
    for counter in range(SAMPLE):
        header = hdr.Header(session_id=b"\x11\x22\x33\x44", counter=counter, length=1024)
        first_bytes.append(hdr.whiten(header.pack(), SESSION_KEY, counter)[0])

    most_common = max(first_bytes.count(value) for value in set(first_bytes))
    assert most_common < SAMPLE / 20


# ---- and the same tests fail without whitening -----------------------------


def test_the_tests_would_catch_an_unwhitened_header():
    """A test that never fails proves nothing. Plain headers must fail these, or the
    thresholds are too loose to have detected a broken mask either.
    """
    plain: list[int] = []
    for counter in range(SAMPLE):
        header = hdr.Header(session_id=b"\x11\x22\x33\x44", counter=counter, length=1024)
        plain.extend((byte >> shift) & 1 for byte in header.pack() for shift in range(7, -1, -1))

    assert monobit_p_value(plain) < ALPHA


def test_an_unwhitened_header_has_stuck_bits():
    """The concrete giveaway: byte 0 is the same in every file."""
    first_bytes = {
        hdr.Header(session_id=b"\x11\x22\x33\x44", counter=counter, length=1024).pack()[0]
        for counter in range(100)
    }

    assert first_bytes == {0x11}
