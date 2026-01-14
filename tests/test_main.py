import subprocess
import sys
from unittest.mock import patch

import pytest

from lattix import __main__ as cli
from lattix import __version__

# ---------- Tests 1: Diagnostics ----------


def test_print_diagnostics(capsys):
    """Verify diagnostics print the version and dependency section."""
    cli.print_diagnostics()
    captured = capsys.readouterr().out

    assert f"Lattix v{__version__}" in captured
    assert "Python version" in captured
    assert "Detected Adapters" in captured
    # Check if logic for Found/Not Found exists in output
    assert ("Found" in captured) or ("Not Found" in captured)


def test_print_diagnostics_lattix_failure(capsys):
    """Test print_diagnostics when Lattix instantiation fails."""
    with patch(
        "lattix.structures.mapping.Lattix", side_effect=Exception("Simulated Failure")
    ):
        cli.print_diagnostics()

    captured = capsys.readouterr().out
    assert "Default separator   : 'unknown'" in captured


# ---------- Tests 2: Doctest ----------


def test_run_tests_success(capsys):
    """Test run_tests when doctest reports 0 failures."""
    with patch("doctest.testmod") as mock_doctest:
        # Mocking return value of testmod: (failed, attempted)
        mock_doctest.return_value = (0, 20)

        cli.run_tests()

        captured = capsys.readouterr().out
        assert "doctests passed!" in captured


def test_run_tests_failure(capsys):
    """Test run_tests when doctest reports failures (should exit 1)."""
    with patch("doctest.testmod") as mock_doctest:
        mock_doctest.return_value = (5, 15)

        with pytest.raises(SystemExit) as excinfo:
            cli.run_tests()

        assert excinfo.value.code == 1
        captured = capsys.readouterr().out
        assert "tests failed out of" in captured


def test_run_tests_import_error_branch(capsys):
    """Test run_tests when one of the modules cannot be imported."""
    with patch("importlib.import_module", side_effect=ImportError("Module not found")):
        cli.run_tests()

    captured = capsys.readouterr().out
    # Check if the skip message appears in the output
    assert "SKIP (Module not found)" in captured
    # Since total_failed is 0 (it didn't run any tests to fail), it should still pass
    assert "All 0 doctests passed!" in captured


# ---------- Tests 3: main() entry point ----------


def test_main_default_behavior(capsys):
    """Test running main without arguments (prints diagnostics)."""
    with patch("sys.argv", ["lattix"]):
        cli.main()
        captured = capsys.readouterr().out
        assert f"Lattix v{__version__}" in captured
        assert "Usage: python -m lattix --test" in captured


def test_main_test_flag():
    """Test that --test flag triggers run_tests."""
    with patch("sys.argv", ["lattix", "--test"]):
        with patch.object(cli, "run_tests") as mock_run:
            cli.main()
            mock_run.assert_called_once()


# --- Integration Test (Subprocess) ---


def test_cli_execution():
    """
    Ensure 'python -m lattix' actually executes as a subprocess.
    This confirms the entry point is wired correctly.
    """
    import os

    # Ensure src is in PYTHONPATH so the subprocess can find 'lattix'
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("src") + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, "-m", "lattix", "--version"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert (
        f"lattix {__version__}" in result.stdout
        or f"lattix {__version__}" in result.stderr
    )


def test_cli_diagnostics_subprocess():
    """Test the full output of python -m lattix."""
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("src") + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, "-m", "lattix"], capture_output=True, text=True, env=env
    )

    assert result.returncode == 0
    assert "Detected Adapters" in result.stdout
