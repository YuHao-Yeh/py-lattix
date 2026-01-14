"""Dynamic dependency management and compatibility shims.

This module provides a robust system for handling optional third-party
dependencies. It enables Lattix to support specialized types from libraries
like NumPy, Pandas, and PyTorch while maintaining a "zero hard dependency"
policy.

Key Features:
    * **Lazy Loading**: Modules are only imported when specifically accessed
      via this module (e.g., ``compat.numpy``).
    * **Availability Checking**: Dynamic ``HAS_*`` flags allow the library
      to safely branch logic based on the user's environment.
    * **Safe Importing**: Utilities to check for module existence without
      the performance overhead of a full import.

Example:
    >>> from lattix.utils import compat
    >>> if compat.HAS_NUMPY:
    ...     # This only executes if numpy is installed
    ...     arr = compat.numpy.array([1, 2, 3])
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import json as json

    import msgpack as msgpack
    import numpy as numpy
    import orjson as orjson
    import pandas as pandas
    import torch as torch
    import xarray as xarray
    import yaml as yaml

    HAS_JSON: bool
    HAS_MSGPACK: bool
    HAS_NUMPY: bool
    HAS_ORJSON: bool
    HAS_PANDAS: bool
    HAS_TORCH: bool
    HAS_XARRAY: bool
    HAS_YAML: bool

__all__ = ["get_module", "has_module"]

_OPTIONAL_MODS = {
    "json",
    "msgpack",
    "numpy",
    "orjson",
    "pandas",
    "torch",
    "xarray",
    "yaml",
}


# ======================================================
# Core Lazy Loader
# ======================================================
def get_module(name: str) -> ModuleType | None:
    """Attempt to import a module and returns it.

    This function checks ``sys.modules`` first to return an already loaded
    module immediately. If not loaded, it attempts a standard import.

    Args:
        name: The fully-qualified name of the module to import.

    Returns:
        Optional[ModuleType]: The module object if successful, or None if
            the module cannot be found or fails to import.
    """
    if name in sys.modules:
        # Returns None if it was previously failed and set to None
        return sys.modules[name]

    try:
        return importlib.import_module(name)
    except ImportError:
        return None
    except Exception:
        # Catch generic errors during import (e.g. syntax errors in the lib)
        return None


def has_module(name: str) -> bool:
    """Check if a module exists in the environment without importing it.

    Use ``importlib.util.find_spec`` to probe the system for the module's
    existence. This is significantly faster and safer than a full import.

    Args:
        name: The name of the module to check.

    Returns:
        bool: True if the module is found, False otherwise.
    """
    if name in sys.modules:
        return sys.modules[name] is not None
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, TypeError):
        return False


# ======================================================
# Lazy Attributes for Common Libs
# ======================================================
def __getattr__(name: str) -> Any:
    """Provide dynamic access to optional modules and availability flags.

    This function implements PEP 562. It intercepts access to attributes
    defined in ``_OPTIONAL_MODS`` and names starting with ``HAS_``.

    Behavior:
        1. If access matches ``HAS_<MOD_NAME>``, it returns a boolean
           indicating if the module is installed.
        2. If access matches a name in ``_OPTIONAL_MODS``, it attempts to
           lazily import and return that module.

    Args:
        name: The name of the attribute being accessed.

    Returns:
        Any: A module object, a boolean flag, or raises AttributeError.

    Raises:
        AttributeError: If the requested name is not a tracked optional
            module or a valid availability flag.
    """
    if name.startswith("HAS_"):
        mod_name = name[4:].lower()
        return has_module(mod_name)

    # Handle lazy module loading
    if name in _OPTIONAL_MODS:
        try:
            return importlib.import_module(name)
        except ImportError:
            return None

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
