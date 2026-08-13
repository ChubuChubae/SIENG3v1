"""Shared test setup."""

import os
import sys
from pathlib import Path

import pytest

# Lets pytest run before pip install -e . After installing, this line does nothing.
SRC = Path(__file__).resolve().parents[1] / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def clean_env(monkeypatch):
    """Remove SIENG_* vars.

    Without this, a machine that exports SIENG_LOG_LEVEL makes tests pass or fail for
    reasons nobody can see.
    """
    for key in [k for k in os.environ if k.startswith("SIENG_")]:
        monkeypatch.delenv(key, raising=False)
