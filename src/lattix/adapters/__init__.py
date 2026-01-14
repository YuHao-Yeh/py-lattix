"""Object adaptation and serialization entry point.

This module acts as the primary interface for Lattix's adaptation system. It
combines core registry logic with an on-demand "lazy loading" mechanism for
third-party libraries like NumPy, Pandas, PyTorch, and Xarray.

By using lazy loading, Lattix ensures that external library-specific code is
only imported and executed if an object from that library is actually
encountered in a mapping.

Key functions:
    get_adapter: The primary public lookup for finding an object's adapter.
    register_adapter: Manual registration of custom conversion handlers.
    construct_from_*: Utilities for rebuilding objects from primitive data.
"""

from __future__ import annotations

from collections import ChainMap, defaultdict
from typing import Any, TypeVar

from ..utils.types import RecurseFunc
from . import registry
from .registry import (
    construct_from_iterable,
    construct_from_mapping,
    fqname_for_cls,
    get_adapter,
    get_adapter_registry,
    get_defaults_registry,
    register_adapter,
    register_constructor_defaults,
    unregister_adapter,
    unregister_constructor_defaults,
)

__all__ = [
    "registry",
    "fqname_for_cls",
    "register_adapter",
    "unregister_adapter",
    "get_adapter_registry",
    "get_adapter",
    "register_constructor_defaults",
    "unregister_constructor_defaults",
    "get_defaults_registry",
    "construct_from_iterable",
    "construct_from_mapping",
]


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


# ======================================================
# Builtin and common adapters (LAZY register)
# ======================================================
def handle_defaultdict(
    value: defaultdict[_KT, _VT], recurse: RecurseFunc
) -> defaultdict[_KT, _VT]:
    """Adapter handler for collections.defaultdict.

    Args:
        value: The defaultdict instance.
        recurse: A function to recursively adapt child elements.

    Returns:
        defaultdict: A new defaultdict with adapted items.
    """
    return defaultdict(
        value.default_factory,
        {k: recurse(v) for k, v in value.items()},
    )


def handle_chainmap(value: ChainMap[_KT, _VT], recurse: RecurseFunc) -> dict[_KT, Any]:
    """Adapter handler for collections.ChainMap.

    Args:
        value: The ChainMap instance.
        recurse: A function to recursively adapt child elements.

    Returns:
        dict: A flattened and adapted dictionary representing the merged maps.
    """
    merged: dict[_KT, _VT] = {}
    for m in value.maps:
        merged.update({k: recurse(v) for k, v in m.items()})
    return merged


# Standard Library registrations performed at import time
register_adapter(defaultdict, handle_defaultdict)
register_adapter(ChainMap, handle_chainmap)
