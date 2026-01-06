__all__ = ["get_module", "has_module"]

import importlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:   # pragma: no cover
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
    

_OPTIONAL_MODS = {
    "json", "msgpack", "numpy", "orjson", "pandas", "torch", "xarray", "yaml",
}

# --- Core Lazy Loader ---

def get_module(name: str) -> ModuleType | None:
    """
    Try to import a module. Returns the module if successful, else None.
    Uses sys.modules to return immediately if already loaded.
    """
    if name in sys.modules:
        return sys.modules[name]  # Returns None if it was previously failed and set to None
    
    try:
        return importlib.import_module(name)
    except ImportError:
        return None
    except Exception:
        # Catch generic errors during import (e.g. syntax errors in the lib)
        return None

def has_module(name: str | ModuleType | type) -> bool:
    """Check if a module exists without importing it."""
    if name in sys.modules:
        return sys.modules[name] is not None
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, TypeError):
        return False


# --- Lazy Attributes for Common Libs ---

def __getattr__(name: str) -> Any:
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