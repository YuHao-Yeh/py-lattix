"""Hierarchical path parsing and optimization.

This module provides high-performance utilities for processing string-based
hierarchical paths. It uses caching to minimize the overhead of repeated
string splitting during deep tree traversals.
"""

from functools import lru_cache

from .types import Tuple

__all__ = ["split_path"]


@lru_cache(maxsize=2048)
def split_path(path: str, sep: str) -> Tuple[str, ...]:
    """Parse a path string into a tuple of keys.

    This internal helper is cached to optimize repeated access to the same
    hierarchical paths.

    Args:
        path: The full path string (e.g., "users/admin/id").
        sep: The separator character.

    Returns:
        tuple[str, ...]: The individual path segments.
    """
    return tuple(path.split(sep))
