"""Lattix: A high-performance, hierarchical, and thread-safe mapping library.

Lattix combines the flexibility of a Python dictionary with the power of
tree-like structures. It provides dot-notation access, compound path keys,
and set-like logical operators, while offering seamless integration with
the modern Python data stack (NumPy, Pandas, PyTorch).
"""

from __future__ import annotations

import logging as _logging

from .adapters import (
    get_adapter,
    register_adapter,
    unregister_adapter,
)
from .core.base import LattixNode
from .serialization import (
    register_yaml_type,
    to_json,
    to_msgpack,
    to_orjson,
    yaml_safe_dump,
    yaml_safe_load,
)
from .structures.mapping import Lattix
from .utils import exceptions

# ========== Version Metadata ==========
__version__ = "0.2.0"
__author__ = "YuHao-Yeh"

__all__ = [
    # Metadata
    "__version__",
    "__author__",
    # Core Class
    "Lattix",
    "LattixNode",
    # Serialization API
    "yaml_safe_load",
    "yaml_safe_dump",
    "register_yaml_type",
    "to_json",
    "to_orjson",
    "to_msgpack",
    # Adapter API
    "register_adapter",
    "unregister_adapter",
    "get_adapter",
    # Namespaces
    "exceptions",
]


_log = _logging.getLogger(__name__)
_log.debug("Lattix v%s initialized", __version__)
