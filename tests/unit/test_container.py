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
    settings = Settings(workspace_dir=Path("/tmp/ws"), temp_dir=Path("/tmp/ws/tmp"))

    assert build_container(settings).settings is settings


def test_registries_are_still_empty():
    """Phase 0 has none yet, so a red result means something half-finished got registered."""
    container = build_container()

    assert container.carriers == {}
    assert container.costs == {}
    assert container.engines == {}


def test_summary_mentions_the_workspace():
    settings = load_settings(workspace_dir="/tmp/ws-summary", temp_dir="/tmp/ws-summary/tmp")

    assert "ws-summary" in build_container(settings).summary()


def test_each_call_returns_a_separate_container():
    """Shared registries would leak registrations from one test into the next."""
    first = build_container()
    second = build_container()

    assert first is not second
    assert first.carriers is not second.carriers
