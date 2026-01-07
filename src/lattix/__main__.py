import sys
import argparse
from . import __version__
from .utils import compat
from .structures import mapping

def print_diagnostics():
    """Print package info and detected dependencies."""
    print(f"Lattix v{__version__}")
    print("-" * 30)
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Path separator: {mapping.Lattix().sep}")
    print("\nDetected Adapters (Optional Dependencies):")
    
    deps = {
        "NumPy": compat.HAS_NUMPY,
        "Pandas": compat.HAS_PANDAS,
        "PyTorch": compat.HAS_TORCH,
        "PyYAML": compat.HAS_YAML,
        "Msgpack": compat.HAS_MSGPACK,
        "Orjson": compat.HAS_ORJSON,
    }
    
    for name, found in deps.items():
        status = "Found" if found else "Not Found"
        print(f"  {name:<10}: {status}")

def run_tests():
    """Run internal doctests."""
    import doctest
    print(f"Running doctests for Lattix v{__version__}...")
    results = doctest.testmod(mapping, verbose=False)
    if results.failed == 0:
        print("All doctests passed!")
    else:
        print(f"{results.failed} tests failed.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(prog="lattix", description="Lattix: Hierarchical Mapping Library")
    parser.add_argument("--version", action="version", version=f"lattix {__version__}")
    parser.add_argument("--test", action="store_true", help="Run package doctests")
    
    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print_diagnostics()
        print("\nUsage: python -m lattix --test (to run doctests)")

if __name__ == "__main__":
    main()