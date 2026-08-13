"""CLI, the target of the `sieng` console script declared in pyproject.toml.

Phase 0 accepts commands and reports status but cannot do real work yet.
Unimplemented commands exit with code 3, never 0: callers trust the exit code, and a 0
would tell them the data was embedded when nothing happened.
"""

import argparse
import sys

from sieng import CRYPTO_SUITE, __version__

EXIT_NOT_IMPLEMENTED = 3

# command -> (description, phase that makes it work), see docs/PROJECT_CONTEXT.md
COMMANDS = {
    "embed": ("hide data in a carrier", "8.5"),
    "extract": ("recover hidden data", "8.5"),
    "analyze": ("inspect a suspicious file", "4.5"),
    "compare": ("diff a cover against its stego", "4.5"),
    "pipeline": ("run a pipeline from a yaml file", "8.7"),
}


def build_parser():
    """Build the parser, with one subcommand per entry in COMMANDS."""
    parser = argparse.ArgumentParser(
        prog="sieng",
        description="SIENG3 - adaptive JPEG/PNG steganography (work in progress)",
    )
    parser.add_argument("--version", action="version", version=f"sieng {__version__}")
    parser.add_argument("--status", action="store_true", help="print system status and exit")

    subcommands = parser.add_subparsers(dest="command", metavar="command")
    for name, (description, phase) in COMMANDS.items():
        subcommands.add_parser(name, help=f"{description} (Phase {phase})", add_help=False)
    return parser


def print_status():
    """Print version, crypto suite and what the container wired up. Useful to check the install."""
    from sieng.app.container import build_container

    print(f"sieng {__version__}")
    print(f"crypto suite: {CRYPTO_SUITE}")
    print(build_container().summary())
    print("\nNot implemented yet:")
    for name, (description, phase) in COMMANDS.items():
        print(f"  {name:<10} {description:<32} -> Phase {phase}")


def main(argv=None):
    """CLI entry point. Returns an exit code."""
    parser = build_parser()
    args, _unknown = parser.parse_known_args(argv)

    if args.status:
        print_status()
        return 0

    if args.command is None:
        parser.print_help()
        return 0

    description, phase = COMMANDS[args.command]
    print(
        f"Command '{args.command}' ({description}) is not implemented yet, "
        f"it lands in Phase {phase}. "
        f"See docs/PROJECT_CONTEXT.md for the current roadmap.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
