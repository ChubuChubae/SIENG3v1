"""Settings: defaults, validation, and where values come from."""

import dataclasses
from pathlib import Path

import pytest

from sieng.app.settings import (
    DEFAULT_MAX_RATCHET_SKIP,
    DEFAULT_PAYLOAD_RATE,
    DEFAULT_STC_HEIGHT,
    Settings,
    SettingsError,
    load_settings,
)

pytestmark = pytest.mark.usefixtures("clean_env")

# Any path works, these tests never touch the disk
WORKSPACE = {"workspace_dir": Path("/tmp/ws"), "temp_dir": Path("/tmp/ws/tmp")}


def make_settings(**changes):
    """Settings with defaults, overriding only what is passed in."""
    return Settings(**WORKSPACE, **changes)


# ---- defaults and immutability ---------------------------------------------


def test_defaults_match_declared_constants():
    settings = load_settings()

    assert settings.default_stc_height == DEFAULT_STC_HEIGHT
    assert settings.default_payload_rate == DEFAULT_PAYLOAD_RATE
    assert settings.max_ratchet_skip == DEFAULT_MAX_RATCHET_SKIP
    assert settings.docker_enabled is True


def test_cannot_be_modified_after_creation():
    """Security-relevant values must not change mid-run."""
    settings = load_settings()

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.default_stc_height = 12


def test_with_overrides_leaves_the_original_alone():
    settings = load_settings()

    changed = settings.with_overrides(log_level="DEBUG")

    assert changed.log_level == "DEBUG"
    assert settings.log_level == "INFO"


# ---- validation ------------------------------------------------------------


@pytest.mark.parametrize("height", [5, 15, 0, -1])
def test_stc_height_outside_range_is_rejected(height):
    with pytest.raises(SettingsError, match="default_stc_height"):
        make_settings(default_stc_height=height)


@pytest.mark.parametrize("height", [6, 10, 14])
def test_stc_height_at_the_boundary_is_accepted(height):
    assert make_settings(default_stc_height=height).default_stc_height == height


@pytest.mark.parametrize("rate", [0.0, 1.5, -0.1])
def test_payload_rate_outside_range_is_rejected(rate):
    with pytest.raises(SettingsError, match="default_payload_rate"):
        make_settings(default_payload_rate=rate)


def test_max_ratchet_skip_must_be_positive():
    """This cap blocks a forged counter. At 0 the receiver can never decrypt anything."""
    with pytest.raises(SettingsError, match="max_ratchet_skip"):
        make_settings(max_ratchet_skip=0)


def test_unknown_log_level_is_rejected():
    with pytest.raises(SettingsError, match="log_level"):
        make_settings(log_level="VERBOSE")


def test_error_message_says_what_range_is_valid():
    """An error that says something is wrong without saying what is right forces guessing."""
    with pytest.raises(SettingsError) as error:
        make_settings(default_stc_height=99)

    assert "6" in str(error.value)
    assert "14" in str(error.value)


# ---- where values come from ------------------------------------------------


def test_reads_values_from_env(monkeypatch):
    monkeypatch.setenv("SIENG_DEFAULT_PAYLOAD_RATE", "0.4")
    monkeypatch.setenv("SIENG_LOG_LEVEL", "debug")
    monkeypatch.setenv("SIENG_DOCKER_ENABLED", "no")

    settings = load_settings()

    assert settings.default_payload_rate == 0.4
    assert settings.log_level == "DEBUG"
    assert settings.docker_enabled is False


def test_unparsable_env_value_is_rejected(monkeypatch):
    monkeypatch.setenv("SIENG_DEFAULT_STC_HEIGHT", "not a number")

    with pytest.raises(SettingsError, match="SIENG_DEFAULT_STC_HEIGHT"):
        load_settings()


def test_argument_beats_env(monkeypatch):
    monkeypatch.setenv("SIENG_LOG_LEVEL", "ERROR")

    assert load_settings(log_level="WARNING").log_level == "WARNING"


def test_reads_values_from_toml_file(tmp_path):
    config = tmp_path / "sieng.toml"
    config.write_text('[sieng]\nlog_level = "WARNING"\nmax_ratchet_skip = 50\n', encoding="utf-8")

    settings = load_settings(config)

    assert settings.log_level == "WARNING"
    assert settings.max_ratchet_skip == 50


def test_missing_config_file_is_an_error(tmp_path):
    """Silence here means running on defaults while believing the config was applied."""
    with pytest.raises(SettingsError, match="Config file not found"):
        load_settings(tmp_path / "absent.toml")


def test_misspelled_config_key_is_an_error():
    with pytest.raises(SettingsError, match="Unknown config key"):
        load_settings(max_ratchet_skips=10)


def test_home_shortcut_in_paths_is_expanded():
    settings = load_settings(workspace_dir="~/sieng-test", temp_dir="~/sieng-test/tmp")

    assert "~" not in str(settings.workspace_dir)
    assert settings.workspace_dir.is_absolute()
