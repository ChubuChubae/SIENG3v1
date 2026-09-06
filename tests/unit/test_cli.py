"""CLI: exit codes and the shape of the parser.

Exit codes matter more than they look. Scripts that call sieng trust them, so a command
that cannot work yet must never report success.

The commands that do work are covered end to end in tests/integration/test_cli.py, where
there is a real cover and a real session to run them against.
"""

import pytest

from sieng.ui.cli.__main__ import EXIT_NOT_IMPLEMENTED, EXIT_OK, PENDING, build_parser, main

pytestmark = pytest.mark.usefixtures("clean_env")


def test_no_arguments_prints_help(capsys):
    exit_code = main([])

    assert exit_code == EXIT_OK
    assert "sieng" in capsys.readouterr().out


def test_version_flag_exits_cleanly():
    with pytest.raises(SystemExit) as error:
        main(["--version"])

    assert error.value.code == 0


def test_status_reports_the_crypto_suite(capsys):
    exit_code = main(["--status"])
    output = capsys.readouterr().out

    assert exit_code == EXIT_OK
    assert "crypto suite" in output
    assert "carriers=" in output


def test_status_lists_the_engines_that_are_wired(capsys):
    """The ui builds its choices from the registries, so status shows what is really in
    them rather than a hardcoded list that can drift."""
    main(["--status"])

    assert "juniward_stc" in capsys.readouterr().out


@pytest.mark.parametrize("command", sorted(PENDING))
def test_unimplemented_command_does_not_report_success(command, capsys):
    exit_code = main([command])

    assert exit_code == EXIT_NOT_IMPLEMENTED
    assert "not implemented yet" in capsys.readouterr().err


@pytest.mark.parametrize("command", sorted(PENDING))
def test_every_pending_command_says_which_phase_it_lands_in(command):
    """Without a phase, users cannot tell whether to wait or find another way."""
    description, phase = PENDING[command]

    assert description
    assert phase[0].isdigit()


@pytest.mark.parametrize("command", ["embed", "extract", "session"])
def test_the_working_commands_are_not_listed_as_pending(command):
    """A command that works and still says "not implemented" would send users away."""
    assert command not in PENDING


def test_the_working_commands_have_a_subparser(command=None):
    """They take arguments, so unlike the pending ones they cannot share a stub parser."""
    parser = build_parser()
    text = parser.format_help()

    for name in ("embed", "extract", "session"):
        assert name in text
