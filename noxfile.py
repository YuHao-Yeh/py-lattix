import nox

nox.options.default_venv_backend = "uv"
nox.options.error_on_missing_interpreters = False


# ======================================================
# Current Hatch Env
# ======================================================


@nox.session(name="fmt", venv_backend="none")
def fmt(session: nox.Session):
    """Auto-format code using current Hatch env."""
    session.run("black", ".")
    session.run("ruff", "check", "--fix", ".")


@nox.session(name="style", venv_backend="none")
def style(session: nox.Session):
    """Style-only checks (no mutation) using current Hatch env."""
    session.run("black", "--check", ".")
    session.run("ruff", "check", ".")


@nox.session(name="lint", venv_backend="none")
def lint(session: nox.Session) -> None:
    """Full static checks (style + type) using current Hatch env."""
    session.run("black", "--check", ".")
    session.run("ruff", "check", ".")
    session.run("mypy", "src/lattix")


@nox.session(name="tests", venv_backend="none")
def tests(session: nox.Session):
    """Full test using current Hatch env."""
    session.run("pytest", "-q")


# ======================================================
# Hatch
# ======================================================

PY_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]


@nox.session(name="typecheck", python=PY_VERSIONS)
def typecheck(session: nox.Session):
    """Verify type hints with Mypy."""
    session.install(".[test]", "mypy", "types-PyYAML")
    session.run("mypy", "src/lattix")


@nox.session(name="hatch_tests")
def hatch_tests(session: nox.Session):
    """Verify tests with pytest."""
    session.install(".[test]")
    session.run("pytest", *session.posargs)
