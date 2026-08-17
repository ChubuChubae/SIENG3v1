"""common: error hierarchy, log redaction, progress scoping."""

import logging

import pytest

from sieng.common.errors import (
    CapacityError,
    ConfigError,
    CryptoError,
    DecryptError,
    SiengError,
    UnsupportedCarrierError,
)
from sieng.common.logging import RedactingFilter, get_logger, redact
from sieng.common.progress import ProgressReporter

# ---- error hierarchy -------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [UnsupportedCarrierError, ConfigError, DecryptError, CapacityError],
)
def test_everything_descends_from_sieng_error(error):
    """Catching SiengError must catch everything we throw and nothing we do not."""
    assert issubclass(error, SiengError)


def test_decrypt_error_takes_no_arguments():
    """A message that varies by cause turns the error itself into an oracle."""
    with pytest.raises(TypeError):
        DecryptError("wrong key")


def test_decrypt_error_message_is_always_the_same():
    assert str(DecryptError()) == str(DecryptError()) == DecryptError.MESSAGE


def test_decrypt_error_is_a_crypto_error():
    assert issubclass(DecryptError, CryptoError)


def test_capacity_error_carries_the_real_ceiling():
    """Callers need the ceiling to tell the user what would fit."""
    error = CapacityError(requested_bits=5000, max_bits=2504, max_bpnzac=0.0963)

    assert error.max_bits == 2504
    assert "2504" in str(error)
    assert "0.0963" in str(error)


# ---- log redaction ---------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "key=9f2a4c8e1b7d3056",
        "nonce: 0011223344556677",
        "session_key = abcdef",
        "chain_key=deadbeef",
        "password: hunter2",
        "seed_sel=00ff00ff",
    ],
)
def test_named_secrets_are_redacted(text):
    assert "<redacted>" in redact(text)


def test_long_hex_runs_are_redacted():
    digest = "9f" * 20
    assert digest not in redact(f"digest {digest} done")


def test_fingerprints_are_not_treated_as_secrets():
    """Fingerprints exist to be shown to users, hiding them defeats their purpose."""
    assert "fingerprint" in redact("fingerprint = 3F2A 8B01 C4D9 77E2")


def test_short_values_survive():
    """Redacting everything would make logs useless."""
    assert redact("counter=7 width=512") == "counter=7 width=512"


def test_filter_redacts_the_message(caplog):
    logger = get_logger("sieng.test.msg")
    with caplog.at_level(logging.DEBUG):
        logger.debug("aead_key=%s", "0123456789abcdef0123456789abcdef")

    assert "0123456789abcdef" not in caplog.text


def test_filter_redacts_the_arguments(caplog):
    """logger.debug("%s", key) keeps the secret in args, not in msg."""
    logger = get_logger("sieng.test.args")
    with caplog.at_level(logging.DEBUG):
        logger.debug("chain_key=%s", "ff" * 16)

    assert "ffffffff" not in caplog.text


def test_get_logger_does_not_stack_filters():
    logger = get_logger("sieng.test.once")
    get_logger("sieng.test.once")

    assert sum(isinstance(f, RedactingFilter) for f in logger.filters) == 1


# ---- progress --------------------------------------------------------------


def collect():
    """Return a callback and the list it appends to."""
    seen = []
    return (lambda percent, message: seen.append((percent, message))), seen


def test_reports_straight_through_without_scoping():
    callback, seen = collect()

    ProgressReporter(callback).step(40, "working")

    assert seen == [(40, "working")]


def test_scoped_maps_into_its_slice():
    callback, seen = collect()

    ProgressReporter(callback).scoped(0, 40).step(50, "half of the first stage")

    assert seen == [(20, "half of the first stage")]


def test_nested_scopes_stay_inside_the_outer_range():
    callback, seen = collect()

    outer = ProgressReporter(callback).scoped(40, 80)
    outer.scoped(0, 50).step(100, "deep")

    assert seen == [(60, "deep")]


@pytest.mark.parametrize("percent", [-10, 0, 50, 100, 250])
def test_never_reports_outside_zero_to_hundred(percent):
    callback, seen = collect()

    ProgressReporter(callback).scoped(10, 90).step(percent, "x")

    assert 0 <= seen[0][0] <= 100


def test_rejects_a_backwards_range():
    with pytest.raises(ValueError, match="Invalid progress range"):
        ProgressReporter(None, low=80, high=20)


def test_works_without_a_callback():
    """Progress is optional. Code should not have to check before reporting."""
    ProgressReporter().scoped(0, 50).step(10, "silent")
