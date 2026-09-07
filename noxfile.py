"""Check runner for SIENG3. Everything runs locally, nothing depends on a hosted service.

    nox              run the standard set
    nox -s lint      run one session
    nox -l           list them all

Which session to run when: docs/PROJECT_CONTEXT.md 2.6
Every session uses venv_backend="none" because it runs in an environment that already has
pip install -e ".[dev]".
"""

import shutil

import nox

nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = False
# integration is in this list on purpose. It was left out once and the whole folder went
# unrun for two phases, which is exactly the mistake it exists to catch. It uses the 64x64
# fixture for most cases so it stays quick enough to belong here.
#
# `slow` is not in the list, and that is a compromise with a known cost. It holds the only
# test that uses a full size photograph, which is the size that found the trellis memory
# bug, and it takes about a minute. Run `nox -s slow` before anything that claims the
# engine works, and always before a release.
nox.options.sessions = [
    "lint",
    "types",
    "imports",
    "unit",
    "property",
    "integration",
    "vectors",
    "security",
]

PYTHON = "3.11"
SRC = "src/sieng"
TARGETS = [SRC, "tests", "noxfile.py", "main.py"]
STRICT_LAYERS = [
    "src/sieng/crypto",
    "src/sieng/coder",
    "src/sieng/carrier",
    "src/sieng/domain",
    # The contract only. The models themselves are numpy arithmetic end to end, where
    # strict typing costs more noise than it catches.
    "src/sieng/cost/base.py",
]

# pytest exits 5 when it collects nothing, which is normal while the project is being built.
# Only the folders listed here may be empty, and each one still prints a warning.
# tests/unit and tests/security are deliberately absent: they gate closing a module,
# so letting them pass while empty would be lying to ourselves.
NO_TESTS_COLLECTED = 5
EMPTY_UNTIL_PHASE = {
    "tests/vectors": "7.1 (KAT for HKDF / ML-KEM / GCM-SIV)",
    "tests/integration": "8.3 (full pipeline)",
    "tests/fuzz": "11.2 (fuzzing harness)",
}


def run_pytest(session, path, *extra):
    """Run pytest on one folder, allowing "no tests" only for folders in EMPTY_UNTIL_PHASE."""
    phase = EMPTY_UNTIL_PHASE.get(path)
    codes = [0, NO_TESTS_COLLECTED] if phase else [0]
    session.run("pytest", path, "-q", *extra, external=True, success_codes=codes)
    if phase:
        session.warn(f"{path} gets real tests in Phase {phase}, it may have checked nothing")


# ---- code quality ----------------------------------------------------------
@nox.session(python=PYTHON, venv_backend="none")
def lint(session):
    """ruff: style and bug patterns."""
    session.run("ruff", "check", *TARGETS, external=True)
    session.run("ruff", "format", "--check", *TARGETS, external=True)


@nox.session(python=PYTHON, venv_backend="none")
def fmt(session):
    """ruff format: rewrites files instead of checking them."""
    session.run("ruff", "format", *TARGETS, external=True)
    session.run("ruff", "check", "--fix", *TARGETS, external=True)


@nox.session(python=PYTHON, venv_backend="none")
def types(session):
    """mypy --strict on the layers where a silent mistake is expensive."""
    session.run("mypy", *STRICT_LAYERS, external=True)


@nox.session(python=PYTHON, venv_backend="none")
def imports(session):
    """import-linter: enforces the import matrix in PROJECT_CONTEXT.md 2.1.

    Contracts live in [tool.importlinter] in pyproject.toml. A red run means code landed
    in the wrong layer. Fix the code, not the contract.

    PYTHONPATH is set so this works whether or not the package is installed, the same
    way tests/conftest.py does it.
    """
    session.run("lint-imports", external=True, env={"PYTHONPATH": "src"})


# ---- tests -----------------------------------------------------------------
@nox.session(python=PYTHON, venv_backend="none")
def unit(session):
    """Unit tests."""
    run_pytest(session, "tests/unit", *session.posargs)


@nox.session(python=PYTHON, venv_backend="none")
def vectors(session):
    """Known answer tests. Never skip: one wrong bit means the crypto is unusable."""
    run_pytest(session, "tests/vectors")


@nox.session(python=PYTHON, venv_backend="none")
def security(session):
    """Negative security tests. Never skip: every case must fail closed."""
    run_pytest(session, "tests/security")


@nox.session(python=PYTHON, venv_backend="none", name="property")
def property_tests(session):
    """Properties that must hold for every input, not just the ones we thought of."""
    run_pytest(session, "tests/property")


@nox.session(python=PYTHON, venv_backend="none")
def integration(session):
    """Full pipeline, including the yaml templates."""
    run_pytest(session, "tests/integration", "-m", "not slow")


@nox.session(python=PYTHON, venv_backend="none")
def slow(session):
    """The tests that use a full size photograph. Minutes, not seconds."""
    session.run("pytest", "tests", "-q", "-m", "slow", external=True)


@nox.session(python=PYTHON, venv_backend="none")
def cov(session):
    """Coverage. Target is 80% in layers 1-5."""
    session.run("pytest", "tests", "--cov=sieng", "--cov-report=term-missing", "-q", external=True)


# ---- security tooling ------------------------------------------------------
@nox.session(python=PYTHON, venv_backend="none")
def sast(session):
    """bandit and semgrep: find flaws in the source without running it."""
    session.run("bandit", "-q", "-r", SRC, external=True)
    if shutil.which("semgrep"):
        session.run("semgrep", "--config", "auto", "--error", SRC, external=True)
    else:
        session.warn("skipping semgrep, not installed (it does not install on Windows)")


@nox.session(python=PYTHON, venv_backend="none")
def secrets(session):
    """detect-secrets: keeps real keys from being committed alongside the source."""
    session.run("detect-secrets", "scan", "--all-files", external=True)


@nox.session(python=PYTHON, venv_backend="none")
def deps(session):
    """pip-audit: check dependencies against the CVE database."""
    session.run("pip-audit", "--strict", "--desc", external=True)


@nox.session(python=PYTHON, venv_backend="none")
def sbom(session):
    """Generate the SBOM that ships with a release."""
    session.run("cyclonedx-py", "environment", "-o", "dist/sbom.cyclonedx.json", external=True)


@nox.session(python=PYTHON, venv_backend="none")
def image_scan(session):
    """trivy: scan the analyzer container. Needs Docker."""
    if not shutil.which("trivy"):
        session.skip("trivy is not installed")
    session.run("trivy", "image", "sieng-analyzer:latest", external=True)


# ---- fuzzing ---------------------------------------------------------------
@nox.session(python=PYTHON, venv_backend="none")
def fuzz_smoke(session):
    """Short fuzz run per target, before closing a phase.

    Only reaches the Python layer. Memory bugs in libjpeg need libFuzzer at the C level,
    which is a recorded Phase 1 gap.
    """
    run_pytest(session, "tests/fuzz")


@nox.session(python=PYTHON, venv_backend="none")
def all_checks(session):
    """Everything except what needs Docker or takes a long time."""
    for name in ("lint", "types", "imports", "unit", "vectors", "security", "sast", "deps"):
        session.notify(name)
