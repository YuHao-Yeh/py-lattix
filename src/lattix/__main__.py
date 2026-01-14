"""Command-line interface for Lattix diagnostics and testing.

This module provides a CLI entry point for verifying the Lattix installation,
checking optional dependencies, and running internal package tests.
"""

import argparse
import doctest
import importlib
import sys

from . import __version__
from .utils import compat


def print_diagnostics() -> None:
    """Print package information and detected third-party dependencies."""
    print(f"\033[1mLattix v{__version__}\033[0m")
    print("-" * 40)
    print(f"{'Python version':<20}: {sys.version.split()[0]}")

    try:
        from .structures.mapping import Lattix

        print(f"{'Default separator':<20}: '{Lattix().sep}'")
    except Exception:
        print(f"{'Default separator':<20}: 'unknown'")

    print("\n\033[1mDetected Adapters (Optional Dependencies):\033[0m")

    deps = {
        "NumPy": "HAS_NUMPY",
        "Pandas": "HAS_PANDAS",
        "PyTorch": "HAS_TORCH",
        "PyYAML": "HAS_YAML",
        "Msgpack": "HAS_MSGPACK",
        "Orjson": "HAS_ORJSON",
        "Xarray": "HAS_XARRAY",
    }

    for label, attr in deps.items():
        found = getattr(compat, attr, False)
        status = "\033[92mFound\033[0m" if found else "\033[90mNot Found\033[0m"
        print(f"  {label:<18}: {status}")


def run_tests() -> None:
    """Execute internal module doctests  across the package."""
    modules_to_test = [
        "lattix.structures.mapping",
        "lattix.adapters.registry",
        "lattix.core.base",
        "lattix.core.mixins",
        "lattix.serialization.yaml",
        "lattix.utils.compat",
        "lattix.utils.transform",
        "lattix.utils.types",
    ]
    total_failed = 0
    total_attempted = 0

    print(f"Running doctests for Lattix v{__version__}...")

    for mod_name in modules_to_test:
        try:
            mod = importlib.import_module(mod_name)
            failed, attempted = doctest.testmod(mod, verbose=False)
            total_failed += failed
            total_attempted += attempted
            status = "PASSED" if failed == 0 else "FAILED"
            print(f"  {mod_name:<30}: {status} ({attempted} tests)")
        except ImportError:
            print(f"  {mod_name:<30}: SKIP (Module not found)")

    print("-" * 40)
    if total_failed == 0:
        print(f"\033[92mAll {total_attempted} doctests passed!\033[0m")
    else:
        print(f"\033[91m{total_failed} tests failed out of {total_attempted}.\033[0m")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="lattix", description="Lattix Diagnostics & Testing Utility"
    )
    parser.add_argument("--version", action="version", version=f"lattix {__version__}")
    parser.add_argument("--test", action="store_true", help="Run package doctests")

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print_diagnostics()
        print("\n\033[3mUsage: python -m lattix --test (to run doctests)\033[0m")


if __name__ == "__main__":
    main()
