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


def test_every_cost_model_is_registered():
    """The ui and the research runner build their lists from this, so a model that is not
    here does not exist as far as the rest of the program is concerned."""
    container = build_container()

    assert container.costs.names() == [
        "hill",
        "juniward",
        "legacy_texture",
        "si_uniward",
        "uerd",
    ]


def test_each_carrier_domain_has_a_cost_model():
    """A carrier with nothing to score it by would fail only once a user picked it."""
    container = build_container()

    assert container.costs.for_domain("dct")
    assert container.costs.for_domain("spatial")


def test_the_main_engine_is_registered():
    """hill_stc joins this once D13 settles how the coder handles spatial planes."""
    assert build_container().engines.ids() == ["juniward_stc"]


def test_the_engine_is_offered_for_the_domain_it_can_handle():
    """The ui builds its dropdown from this, so an engine listed under the wrong domain
    would be offered for files it cannot open."""
    container = build_container()

    assert [e.engine_id for e in container.engines.for_domain("dct")] == ["juniward_stc"]
    assert container.engines.for_domain("spatial") == []


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
