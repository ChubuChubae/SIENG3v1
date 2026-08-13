"""CLI: exit codes and messages.

Exit codes matter more than they look. Scripts that call sieng trust them, so a
command that cannot work yet must never report success.
"""

import pytest

from sieng.ui.cli.__main__ import COMMANDS, EXIT_NOT_IMPLEMENTED, main

pytestmark = pytest.mark.usefixtures("clean_env")


def test_no_arguments_prints_help(capsys):
    exit_code = main([])

    assert exit_code == 0
    assert "sieng" in capsys.readouterr().out


def test_version_flag_exits_cleanly():
    with pytest.raises(SystemExit) as error:
        main(["--version"])

    assert error.value.code == 0


def test_status_reports_the_crypto_suite(capsys):
    exit_code = main(["--status"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "crypto suite" in output
    assert "carriers=" in output


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_unimplemented_command_does_not_report_success(command, capsys):
    exit_code = main([command])

    assert exit_code == EXIT_NOT_IMPLEMENTED
    assert "not implemented yet" in capsys.readouterr().err


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_every_command_says_which_phase_it_lands_in(command):
    """Without a phase, users cannot tell whether to wait or find another way."""
    description, phase = COMMANDS[command]

    assert description
    assert phase[0].isdigit()
