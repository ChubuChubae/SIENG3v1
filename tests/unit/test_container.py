"""Container: the composition root."""

from pathlib import Path

import pytest

from sieng.app.container import Container, build_container
from sieng.app.settings import Settings, load_settings

pytestmark = pytest.mark.usefixtures("clean_env")


def test_builds_with_default_settings():
    container = build_container()

    assert isinstance(container, Container)
    assert container.settings.default_stc_height > 0


def test_uses_the_settings_it_is_given():
    settings = Settings(workspace_dir=Path("/fake/ws"), temp_dir=Path("/fake/ws/tmp"))

    assert build_container(settings).settings is settings


def test_phase_one_carriers_are_registered():
    """jpg and png only. Anything else must be refused, never quietly handled."""
    container = build_container()

    assert container.carriers.suffixes() == [".jpe", ".jpeg", ".jpg", ".png"]


def test_cost_and_engine_registries_are_still_empty():
    """A red result here means something half-finished got registered."""
    container = build_container()

    assert container.costs == {}
    assert container.engines == {}


def test_summary_mentions_the_workspace():
    settings = load_settings(workspace_dir="/fake/ws-summary", temp_dir="/fake/ws-summary/tmp")

    assert "ws-summary" in build_container(settings).summary()


def test_each_call_returns_a_separate_container():
    """Shared registries would leak registrations from one test into the next."""
    first = build_container()
    second = build_container()

    assert first is not second
    assert first.carriers is not second.carriers
    assert first.costs is not second.costs
