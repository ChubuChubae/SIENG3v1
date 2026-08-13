"""Fail closed: when something is wrong, stop instead of quietly carrying on.

Phase 0 has no crypto, so MITM and rollback cannot be tested yet. What can be tested is
how the existing layers behave when they meet something unexpected, which is the same
habit the crypto layer will need.

Tests added later:
  Phase 3.2  test_unsupported_carrier_is_refused
  Phase 7.3  test_mitm_key_substitution_is_rejected
  Phase 7.5  test_header_bits_are_indistinguishable_from_random
  Phase 7.6  test_state_rollback_is_detected
             test_two_processes_cannot_use_same_counter
"""

import importlib
from pathlib import Path

import pytest

from sieng.app.settings import Settings, SettingsError, load_settings
from sieng.ui.cli.__main__ import COMMANDS, main

pytestmark = pytest.mark.usefixtures("clean_env")


# ---- bad config must stop the program, not be silently clamped -------------


def test_out_of_range_value_is_not_clamped():
    with pytest.raises(SettingsError):
        Settings(
            workspace_dir=Path("/tmp/ws"),
            temp_dir=Path("/tmp/ws/tmp"),
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
    """Phase 0 holds no keys yet. This is the placeholder for RedactingFilter in Phase 2.1."""
    text = repr(load_settings()).lower()

    assert "password" not in text
    assert "secret" not in text
