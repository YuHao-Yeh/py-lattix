"""Concrete mapping implementations for Lattix.

This package houses the specialized data structures that form the core
functional API of Lattix. These classes implement the hierarchical mapping
protocols defined in :module:`lattix.core`, adding concrete logic for
path-based traversal, attribute access, and specialized data integration.

The primary class provided is :class:`Lattix`, which serves as the central
structure for managing complex, nested data with thread-safe lock
inheritance and set-like logic.
"""

from . import mapping
from .mapping import Lattix

__all__ = ["mapping", "Lattix"]
