"""The command line, end to end.

Two properties matter more than the plumbing.

**The password never appears in an argument.** There is no option for it, and this file
asserts that there is none, because the day someone adds `--password` for convenience is
the day passwords start appearing in shell histories and in `ps` output.

**Extraction says the same thing whatever went wrong.** The exit code and the message are
identical for a file that holds nothing, a file for another session, and a file that was
altered. Anything else makes `sieng extract` a tool for testing whether a file is a stego
file.
"""

import argparse

import pytest

import sieng.app.container as container_module
import sieng.ui.cli.__main__ as cli
from sieng.crypto.ratchet import session
from tests.fake_carrier import FakeDctCarrier, write_cover

SS = bytes(range(32))
SID = b"sess"
PASSWORD = "hunter2"  # noqa: S105  a test fixture value, not a real credential
FAST = {"time_cost": 1, "memory_cost_kib": 8, "lanes": 1}


@pytest.fixture
def wired(monkeypatch):
    """A container that knows the fake carrier, and a password that comes from nowhere.

    getpass is replaced rather than bypassed, so the code under test still goes through
    the same call it would in front of a real terminal.
    """
    real_build = container_module.build_container

    def with_fake(settings=None):
        container = real_build(settings)
        container.carriers.register(FakeDctCarrier)
        return container

    monkeypatch.setattr(container_module, "build_container", with_fake)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": PASSWORD)


@pytest.fixture
def a_session(tmp_path):
    path = tmp_path / "s.state"
    session.create(path, SID, SS, PASSWORD.encode(), **FAST)
    return path


def a_cover(tmp_path, name="cover.fakedct"):
    return write_cover(tmp_path / name, 256)


# ---- the password ----------------------------------------------------------


def test_there_is_no_password_option():
    """An argument lands in the shell history and in the process list, where any other
    user on the machine can read it. A tool that offers the option gets used in scripts,
    and then the password is in a file too."""
    parser = cli.build_parser()

    for command in ("embed", "extract", "session"):
        actions = _subparser(parser, command)._actions
        options = {option for action in actions for option in action.option_strings}
        assert not {"--password", "--pass", "-p"} & options, command


def test_the_password_comes_from_getpass(monkeypatch):
    asked = []
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": asked.append(prompt) or "pw")

    assert cli.read_password() == b"pw"
    assert asked


def test_an_empty_password_is_refused(monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "")

    with pytest.raises(ValueError, match="protects nothing"):
        cli.read_password()


def test_creating_a_session_asks_twice(monkeypatch):
    answers = iter(["first", "second"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))

    with pytest.raises(ValueError, match="do not match"):
        cli.read_password(confirm=True)


# ---- the commands ----------------------------------------------------------


def test_status_reports_what_is_wired(capsys):
    assert cli.main(["--status"]) == cli.EXIT_OK

    printed = capsys.readouterr().out
    assert "juniward_stc" in printed
    assert "crypto suite" in printed


def test_a_session_can_be_created(tmp_path, wired, capsys):
    path = tmp_path / "new.state"

    assert cli.main(["session", str(path)]) == cli.EXIT_OK

    assert path.is_file()
    printed = capsys.readouterr().out
    assert "shared secret" in printed
    assert "Carry it over a channel you trust" in printed


def test_embed_then_extract(tmp_path, wired, a_session, capsys):
    cover = a_cover(tmp_path)
    payload = tmp_path / "secret.txt"
    payload.write_bytes(b"the real message")
    recovered = tmp_path / "recovered.txt"
    other_side = tmp_path / "recv.state"
    session.create(other_side, SID, SS, PASSWORD.encode(), **FAST)

    embed_code = cli.main(
        [
            "embed",
            str(cover),
            str(tmp_path / "out.fakedct"),
            "--payload",
            str(payload),
            "--session",
            str(a_session),
        ]
    )
    extract_code = cli.main(
        [
            "extract",
            str(tmp_path / "out.fakedct"),
            str(recovered),
            "--session",
            str(other_side),
        ]
    )

    assert embed_code == cli.EXIT_OK
    assert extract_code == cli.EXIT_OK
    assert recovered.read_bytes() == b"the real message"


def test_an_unimplemented_command_never_exits_zero(capsys):
    """A caller trusts the exit code, and a 0 would say the work was done."""
    for command in cli.PENDING:
        assert cli.main([command]) == cli.EXIT_NOT_IMPLEMENTED


def test_a_missing_cover_is_a_usage_error(tmp_path, wired, a_session, capsys):
    payload = tmp_path / "secret.txt"
    payload.write_bytes(b"x")

    code = cli.main(
        [
            "embed",
            str(tmp_path / "nope.fakedct"),
            str(tmp_path / "out.fakedct"),
            "--payload",
            str(payload),
            "--session",
            str(a_session),
        ]
    )

    assert code == cli.EXIT_USAGE
    assert "not found" in capsys.readouterr().err


# ---- what extract is allowed to print --------------------------------------


def extract_failure(tmp_path, stego, state, capsys):
    code = cli.main(["extract", str(stego), str(tmp_path / "out.bin"), "--session", str(state)])
    return code, capsys.readouterr().err


def test_a_file_with_nothing_in_it_fails_quietly(tmp_path, wired, a_session, capsys):
    cover = a_cover(tmp_path)

    code, message = extract_failure(tmp_path, cover, a_session, capsys)

    assert code == cli.EXIT_FAILED
    assert "cannot tell you which" in message


def test_every_extraction_failure_looks_the_same(tmp_path, wired, a_session, capsys):
    """Three different reasons, one exit code and one message. This is the property that
    stops the command being a detector."""
    cover = a_cover(tmp_path)
    payload = tmp_path / "secret.txt"
    payload.write_bytes(b"hidden")
    stego = tmp_path / "out.fakedct"
    cli.main(
        [
            "embed",
            str(cover),
            str(stego),
            "--payload",
            str(payload),
            "--session",
            str(a_session),
        ]
    )
    capsys.readouterr()

    other = tmp_path / "other.state"
    session.create(other, SID, bytes(32), PASSWORD.encode(), **FAST)
    damaged = tmp_path / "damaged.fakedct"
    blob = bytearray(stego.read_bytes())
    blob[6000] ^= 0xFF
    damaged.write_bytes(bytes(blob))

    outcomes = {
        extract_failure(tmp_path, cover, a_session, capsys),
        extract_failure(tmp_path, stego, other, capsys),
        extract_failure(tmp_path, damaged, a_session, capsys),
    }

    assert len(outcomes) == 1


def test_the_failure_message_names_the_possibilities_without_choosing(
    tmp_path, wired, a_session, capsys
):
    """Listing what might be wrong helps the user. Saying which one it was helps an
    examiner, so the message does the first and not the second."""
    cover = a_cover(tmp_path)

    _, message = extract_failure(tmp_path, cover, a_session, capsys)

    for possibility in ("hold nothing", "different session", "password", "altered"):
        assert possibility in message


def _subparser(parser, name):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"no subcommand {name}")
