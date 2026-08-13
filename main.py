"""GUI entry point. Deliberately holds no logic.

Use `python main.py` while developing, or the `sieng` command after pip install -e .
"""

import sys
from pathlib import Path

# Lets `import sieng` work before pip install -e .
SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main():
    from sieng.app.container import build_container
    from sieng.ui.gui.bootstrap import GuiUnavailableError, run

    try:
        return run(build_container())
    except GuiUnavailableError as error:
        # No traceback here, the message already tells the user what to do
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
