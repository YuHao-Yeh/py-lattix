__all__ = [
    # constants
    "HAS_NUMPY", "HAS_PANDAS", "HAS_YAML", 
    # lazy accessors
    "numpy", "pandas", "yaml",
    # generic helpers
    "get_module", "has_module"
]

import importlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:   # pragma: no cover
    import numpy as numpy
    import pandas as pandas
    import yaml as yaml
    
    HAS_NUMPY: bool
    HAS_PANDAS: bool
    HAS_YAML: bool

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
    """
    Check if a module is available without triggering a hard import if possible.
    Supports passing a string name, a module object, or a class/type.
    """
    target_name: str
    
    if isinstance(name, ModuleType):
        target_name = name.__name__
    elif isinstance(name, str):
        target_name = name
    else:
        # It's a class or type
        target_name = name.__module__.split(".")[0]

    # Check sys.modules first (fastest)
    if target_name in sys.modules:
        return sys.modules[target_name] is not None
    
    # Try safe import
    return get_module(target_name) is not None


# --- Lazy Attributes for Common Libs ---

def __getattr__(name: str) -> Any:
    # 1. Library Access
    if name in {"numpy", "pandas", "yaml"}:
        return get_module(name)

    # 2. Flag Access
    if name == "HAS_NUMPY":
        return has_module("numpy")
    if name == "HAS_PANDAS":
        return has_module("pandas")
    if name == "HAS_YAML":
        return has_module("yaml")

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")