"""CLI, the target of the `sieng` console script declared in pyproject.toml.

Three commands work: `session new`, `embed` and `extract`. The rest still report that they
are not implemented and exit non-zero, because a caller trusts the exit code and a 0 would
say the data was hidden when nothing happened.

Two rules shape this file more than anything else.

**The password is only ever read with getpass.** There is no `--password` option and there
will not be one. An argument appears in the shell history and in the process list, where
any other user on the machine can read it, and a tool that offers the option gets used in
scripts where the password ends up in a file. Reading it from the terminal is mildly
inconvenient once and safe every time.

**Extraction reports the same failure for everything about the file.** The exit code and
the message are identical whether the file holds nothing, holds something for a different
session, or was tampered with. Anything else turns `sieng extract` into a tool for testing
whether a file is a stego file, which is exactly what the project exists to prevent.
"""

import argparse
import getpass
import sys
from pathlib import Path

from sieng import CRYPTO_SUITE, __version__
from sieng.common.errors import (
    CapacityError,
    CarrierError,
    PipelineError,
    RatchetLimitError,
    ReplayError,
    RollbackDetected,
)

# Errors that describe the caller's situation rather than a file's contents, and so may be
# printed as they are. DecryptError is deliberately absent: see main().
USER_FIXABLE: tuple[type[Exception], ...] = (
    CapacityError,
    CarrierError,
    PipelineError,
    RatchetLimitError,
    ReplayError,
    RollbackDetected,
    ValueError,
    OSError,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_IMPLEMENTED = 3
EXIT_FAILED = 4

DEFAULT_ENGINE = "juniward_stc"

# Commands that still have no implementation, with the phase that brings each one.
PENDING = {
    "analyze": ("inspect a suspicious file", "4.5"),
    "compare": ("diff a cover against its stego", "4.5"),
    "pipeline": ("run a pipeline from a yaml file", "8.7"),
}


def build_parser():
    """Build the parser. One subcommand per capability, not one per phase."""
    parser = argparse.ArgumentParser(
        prog="sieng",
        description="SIENG3 - adaptive JPEG/PNG steganography with post-quantum crypto",
    )
    parser.add_argument("--version", action="version", version=f"sieng {__version__}")
    parser.add_argument("--status", action="store_true", help="print system status and exit")
    subcommands = parser.add_subparsers(dest="command", metavar="command")

    new_session = subcommands.add_parser("session", help="create a session")
    new_session.add_argument("state", type=Path, help="where to write the session state")
    new_session.add_argument("--window", type=int, default=1000, help="max messages skipped")

    embed = subcommands.add_parser("embed", help="hide data in a carrier")
    embed.add_argument("cover", type=Path)
    embed.add_argument("output", type=Path)
    embed.add_argument("--payload", type=Path, required=True, help="file to hide")
    embed.add_argument("--session", type=Path, required=True, help="session state file")
    embed.add_argument("--rate", type=float, default=0.1, help="payload rate in bpnzAC")
    embed.add_argument("--engine", default=DEFAULT_ENGINE)
    embed.add_argument("--height", type=int, default=None, help="STC constraint height")

    extract = subcommands.add_parser("extract", help="recover hidden data")
    extract.add_argument("stego", type=Path)
    extract.add_argument("output", type=Path, help="where to write the recovered payload")
    extract.add_argument("--session", type=Path, required=True, help="session state file")
    extract.add_argument("--engine", default=DEFAULT_ENGINE)
    extract.add_argument("--height", type=int, default=None, help="STC constraint height")

    for name, (description, phase) in PENDING.items():
        subcommands.add_parser(name, help=f"{description} (Phase {phase})", add_help=False)
    return parser


def read_password(confirm=False):
    """Ask for the password on the terminal.

    Never an argument, never an environment variable. Both are readable by other processes
    and both end up saved somewhere the user did not intend.
    """
    password = getpass.getpass("Session password: ")
    if confirm and password != getpass.getpass("Confirm: "):
        raise ValueError("The two passwords do not match")
    if not password:
        raise ValueError("An empty password protects nothing")
    return password.encode()


def run_session(args, out=None):
    """Create a new session. Both sides need the same shared secret, so this prints it.

    Phase 7 has the full handshake that establishes a secret without anyone printing it.
    Until the ui for that exists, this is the honest placeholder: it says plainly that the
    secret has to be carried to the other side by some means this program does not provide.
    """
    from sieng.pipeline.session import create_session

    out = out or sys.stdout
    session_id, shared_secret = create_session(args.state, read_password(confirm=True), args.window)

    print(f"Session created at {args.state}", file=out)
    print(f"  session id     {session_id.hex()}", file=out)
    print(f"  shared secret  {shared_secret.hex()}", file=out)
    print(
        "\nThe other side needs this secret and cannot get it from the file. Carry it "
        "over a channel you trust, and delete it from anywhere it was written down.",
        file=out,
    )
    return EXIT_OK


def run_embed_command(args, out=None):
    from sieng.app.container import build_container
    from sieng.pipeline.embed import run_embed
    from sieng.pipeline.engines.base import EmbedRequest

    out = out or sys.stdout
    container = build_container()
    request = EmbedRequest(
        cover=args.cover,
        destination=args.output,
        payload=Path(args.payload).read_bytes(),
        state_path=args.session,
        password=read_password(),
        payload_rate=args.rate,
        constraint_height=args.height,
    )
    result = run_embed(request, args.engine, container.carriers, container.engines)
    print(result.summary(), file=out)
    return EXIT_OK


def run_extract_command(args, out=None):
    """Recover a payload, saying nothing about why if it fails.

    The single message below covers every reason: nothing hidden, wrong session, wrong
    password, tampered file. Listing the possibilities is fine; saying which one it was
    is not.
    """
    from sieng.app.container import build_container
    from sieng.common.errors import DecryptError
    from sieng.pipeline.engines.base import ExtractRequest
    from sieng.pipeline.extract import run_extract

    out = out or sys.stdout
    container = build_container()
    request = ExtractRequest(
        stego=args.stego,
        state_path=args.session,
        password=read_password(),
        constraint_height=args.height,
    )
    try:
        result = run_extract(request, args.engine, container.carriers, container.engines)
    except DecryptError:
        print(
            "Nothing could be recovered from this file. It may hold nothing, it may "
            "belong to a different session, the password may be wrong, or it may have "
            "been altered. This program cannot tell you which.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    Path(args.output).write_bytes(result.payload)
    print(f"{len(result.payload)} bytes recovered to {args.output}", file=out)
    return EXIT_OK


def print_status(out=None):
    """Version, crypto suite and what the container wired up. Useful to check an install."""
    from sieng.app.container import build_container

    out = out or sys.stdout
    container = build_container()
    print(f"sieng {__version__}", file=out)
    print(f"crypto suite: {CRYPTO_SUITE}", file=out)
    print(container.summary(), file=out)
    print(f"engines: {', '.join(container.engines.ids())}", file=out)
    print(f"cost models: {', '.join(container.costs.names())}", file=out)
    if PENDING:
        print("\nNot implemented yet:", file=out)
        for name, (description, phase) in PENDING.items():
            print(f"  {name:<10} {description:<32} -> Phase {phase}", file=out)


HANDLERS = {
    "session": run_session,
    "embed": run_embed_command,
    "extract": run_extract_command,
}


def main(argv=None):
    """CLI entry point. Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.status:
        print_status()
        return EXIT_OK
    if args.command is None:
        parser.print_help()
        return EXIT_OK

    handler = HANDLERS.get(args.command)
    if handler is None:
        description, phase = PENDING[args.command]
        print(
            f"Command '{args.command}' ({description}) is not implemented yet, it lands "
            f"in Phase {phase}. See docs/PROJECT_CONTEXT.md for the roadmap.",
            file=sys.stderr,
        )
        return EXIT_NOT_IMPLEMENTED

    try:
        return handler(args)
    except USER_FIXABLE as error:
        # Mistakes the user can fix: a missing file, an empty password, a payload that
        # does not fit, an engine that cannot open this carrier. All of them are already
        # worded for a reader by the layer that raised them.
        #
        # DecryptError is deliberately not in this list. It is handled inside the extract
        # command, where the message is written to reveal nothing, and if it ever reached
        # here it would be printed with whatever detail it carried.
        print(f"{error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
