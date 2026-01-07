"""
Lattix

A high-performance, hierarchical, and thread-safe mapping library for Python.

Lattix allows you to manage complex, nested data structures using dot-notation, 
compound path keys (e.g., 'a/b/c'), and set-like logical operators, 
while providing seamless integration with NumPy, Pandas, and PyTorch.

:copyright: (c) 2026 YuHao-Yeh.
:license: MIT, see LICENSE for more details.
"""

from ._core.base import LattixNode
from .adapters import (
    get_adapter,
    register_adapter,
    unregister_adapter,
)
from .serialization import (
    register_yaml_type,
    yaml_safe_dump,
    yaml_safe_load,
)
from .structures.mapping import Lattix
from .utils import exceptions

# --- Version Metadata ---
__version__ = "0.1.1"
__author__ = "YuHao-Yeh"


__all__ = [
    "__version__",
    
    # Core Class
    "Lattix",
    "LattixNode",
    
    # Serialization API
    # These are the "Enhanced" versions of YAML load/dump
    "yaml_safe_load",
    "yaml_safe_dump",
    "register_yaml_type",
    
    # Adapter API
    # Used for extending Lattix to support other 3rd-party types
    "register_adapter",
    "unregister_adapter",
    "get_adapter",
    
    # Namespaces
    "exceptions",
    "adapters",
    "serialization",
]

# Optional: Log the availability of optional dependencies on debug level
import logging
logging.getLogger(__name__).debug("Lattix v%s initialized", __version__)