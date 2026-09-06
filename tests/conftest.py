"""Shared test setup."""

import os
import sys
from pathlib import Path

import pytest

# Lets pytest run before pip install -e . After installing, this line does nothing.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# So `from tests.fake_carrier import ...` works regardless of how pytest was invoked.
# pytest usually adds the root itself, but only for some import modes, and a shared helper
# that imports differently depending on the command line is a trap worth closing.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def clean_env(monkeypatch):
    """Remove SIENG_* vars.

    Without this, a machine that exports SIENG_LOG_LEVEL makes tests pass or fail for
    reasons nobody can see.
    """
    for key in [k for k in os.environ if k.startswith("SIENG_")]:
        monkeypatch.delenv(key, raising=False)
