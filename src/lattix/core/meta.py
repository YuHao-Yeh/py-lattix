"""Metaclass implementation for Lattix attribute management.

This module provides :class:`LattixMeta`, a specialized metaclass used to
coordinate class-level attribute discovery and caching.

Because Lattix uses dynamic attribute access (``__getattr__``) to retrieve
nested mapping keys, it must maintain a clear distinction between actual
Python class attributes (methods, properties, class variables) and data keys.
This metaclass ensures that any mutation to the class structure (adding or
deleting methods) automatically invalidates the internal caches, maintaining
the integrity of the attribute resolution logic.
"""

from abc import ABCMeta
from typing import Any

from ..utils.inspection import scan_class_attrs

__all__ = ["LattixMeta"]


class LattixMeta(ABCMeta):
    """Metaclass that handles Lattix class-level attribute caching.

    This metaclass extends :class:`abc.ABCMeta` to intercept attribute
    assignment and deletion on Lattix classes. It triggers cache
    invalidation for the attribute scanner, ensuring that instances
    of Lattix always have an up-to-date view of their class-level
    members.
    """

    def __delattr__(cls, name: str) -> None:
        """Intercepts attribute deletion to invalidate caches.

        Clears the ``__CLASS_ATTRS__`` sentinel on the class and
        purges the global :func:`scan_class_attrs` cache.

        Args:
            name: The name of the attribute being deleted.
        """
        super().__delattr__(name)
        type.__setattr__(cls, "__CLASS_ATTRS__", None)
        scan_class_attrs.cache_clear()

    def __setattr__(cls, name: str, value: Any) -> None:
        """Intercepts attribute assignment to invalidate caches.

        If the attribute being set is not a private/internal dunder name,
        it clears the ``__CLASS_ATTRS__`` sentinel on the class and
        purges the global :func:`scan_class_attrs` cache.

        Args:
            name: The name of the attribute being set.
            value: The value being assigned to the attribute.
        """
        super().__setattr__(name, value)
        if not name.startswith("__"):
            type.__setattr__(cls, "__CLASS_ATTRS__", None)
            scan_class_attrs.cache_clear()
