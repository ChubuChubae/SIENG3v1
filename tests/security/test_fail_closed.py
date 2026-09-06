"""Fail closed: when something is wrong, stop instead of quietly carrying on.

This file covers the layers outside crypto: bad configuration, an unreadable carrier, a
payload that does not fit. The crypto attacks have their own files now that Phase 7 is
finished, and they are listed below so nobody adds a second copy here.

Tests added later:
  Phase 3.2  test_unsupported_carrier_is_refused
  (Phase 7 is complete: see test_auth_attacks.py, test_ratchet_state_attacks.py,
   test_header_randomness.py)
"""

import importlib
import logging
from pathlib import Path

import pytest

from sieng.app.settings import Settings, SettingsError, load_settings
from sieng.common.errors import CapacityError, DecryptError
from sieng.common.logging import get_logger
from sieng.domain.capacity import check_capacity
from sieng.ui.cli.__main__ import COMMANDS, main

pytestmark = pytest.mark.usefixtures("clean_env")


# ---- bad config must stop the program, not be silently clamped -------------


def test_out_of_range_value_is_not_clamped():
    with pytest.raises(SettingsError):
        Settings(
            workspace_dir=Path("/fake/ws"),
            temp_dir=Path("/fake/ws/tmp"),
            default_stc_height=99,
        )


def test_misspelled_key_is_not_ignored():
    """An ignored typo makes the user believe a setting applied when it did not."""
    with pytest.raises(SettingsError):
        load_settings(max_ratchet_skips=10)


def test_missing_config_file_does_not_fall_back_to_defaults(tmp_path):
    with pytest.raises(SettingsError):
        load_settings(tmp_path / "absent.toml")


# ---- commands that cannot work must not exit 0 -----------------------------


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_unimplemented_command_signals_failure(command):
    assert main([command]) != 0


# ---- a missing dependency must explain itself, not raise a bare ImportError -


def test_missing_pyqt_raises_an_actionable_error():
    from sieng.ui.gui.bootstrap import GuiUnavailableError, run

    try:
        importlib.import_module("PyQt6.QtWidgets")
    except ImportError:
        pass
    else:
        pytest.skip("PyQt6 is installed here, this case only applies when it is missing")

    with pytest.raises(GuiUnavailableError) as error:
        run(None)

    assert "pip install" in str(error.value)


# ---- sensitive values must not show up in repr or logs ---------------------


def test_settings_repr_has_no_credential_looking_fields():
    text = repr(load_settings()).lower()

    assert "password" not in text
    assert "secret" not in text


def test_no_secret_appears_in_logs(caplog):
    """Every layer logs through get_logger, so a key can never reach a log file."""
    logger = get_logger("sieng.security.leak")
    aead_key = "a3" * 32
    nonce = "b4" * 12

    with caplog.at_level(logging.DEBUG):
        logger.debug("sealing with aead_key=%s nonce=%s", aead_key, nonce)
        logger.info("chain_key rotated to %s", "c5" * 32)
        logger.warning("raw digest %s", "d6" * 32)

    assert aead_key not in caplog.text
    assert nonce not in caplog.text
    assert "c5c5c5c5" not in caplog.text
    assert "d6d6d6d6" not in caplog.text


# ---- errors must not become an oracle --------------------------------------


def test_decrypt_error_cannot_carry_a_reason():
    """Wrong key, tampered data and wrong carrier must be indistinguishable to the caller."""
    with pytest.raises(TypeError):
        DecryptError("wrong key")

    assert str(DecryptError()) == DecryptError.MESSAGE


def test_capacity_check_refuses_before_any_work_happens():
    """Fail closed: refuse an oversized payload instead of embedding a truncated one."""
    with pytest.raises(CapacityError):
        check_capacity(payload_bits=10**9, n_changeable=26000)
