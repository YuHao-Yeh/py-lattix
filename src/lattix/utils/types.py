"""Unified type hinting interface for Lattix.

This module provides a consistent set of type aliases and runtime components
used for type hinting and instance validation throughout the library. It
consolidates internal aliases from :module:`_typing` and adds components
required for runtime introspection.

Key Components:
    * **Collection Aliases**: Version-agnostic aliases for ``Dict``, ``List``,
      etc. (supporting PEP 585 style where possible).
    * **GenericAlias**: Support for subscriptable generic types (e.g.,
      ``Lattix[str, int]``) across all supported Python versions.
    * **Atomic Base Types**: A comprehensive tuple of types used for
      ``isinstance`` checks to identify non-container values.
    * **Domain Aliases**: Specific types for Lattix operations like
      ``JOIN_METHOD`` and ``AdapterRegistry``.

Example:
    >>> from lattix.utils.types import AtomicTypes, Adapter
    >>> def my_func(val: AtomicTypes, handler: Adapter): ...
"""

from __future__ import annotations

import datetime
import decimal
import fractions
import pathlib
import sys
import uuid
from typing import TYPE_CHECKING, Any

from ._typing import (
    JOIN_METHOD,
    MERGE_METHOD,
    TRAV_ORDER,
    Adapter,
    AdapterRegistry,
    ArgsRegistry,
    AtomicTypes,
    BuiltinAtoms,
    ClassAttrSet,
    Dict,
    List,
    ModuleRegistry,
    RecurseFunc,
    ScalarTypes,
    Set,
    StdLibAtoms,
    StyleHandler,
    StyleRegistry,
    Tuple,
    Type,
    TypeGuard,
)

# ======================================================
# Runtime compatibility helpers (Python 3.9+)
# ======================================================
if TYPE_CHECKING:
    GenericAlias: Any
else:
    try:
        from types import GenericAlias as GenericAlias
    except (ImportError, AttributeError):
        from typing import List as TList

        GenericAlias = type(TList[int])


# ======================================================
# Atomic scalar types (Python 3.10+)
# ======================================================
"""tuple: A consolidated tuple of types considered 'atomic' scalars.

This tuple is used primarily by :func:`lattix.utils.common.is_primitive` to
efficiently determine if an object should be treated as a leaf node rather
than a container that requires recursion.
"""

_ATOMIC_BASE_TYPES = (
    str,
    bytes,
    bytearray,
    int,
    float,
    complex,
    bool,
    type(None),
    decimal.Decimal,
    fractions.Fraction,
    pathlib.Path,
    uuid.UUID,
    datetime.date,
    datetime.time,
)

__all__ = [
    "Dict",
    "List",
    "Set",
    "Tuple",
    "Type",
    "GenericAlias",
    "TypeGuard",
    "AtomicTypes",
    "ScalarTypes",
    "BuiltinAtoms",
    "StdLibAtoms",
    "_ATOMIC_BASE_TYPES",
    "ClassAttrSet",
    "StyleHandler",
    "StyleRegistry",
    "ModuleRegistry",
    "RecurseFunc",
    "Adapter",
    "AdapterRegistry",
    "ArgsRegistry",
    "JOIN_METHOD",
    "MERGE_METHOD",
    "TRAV_ORDER",
]

del sys, datetime, decimal, fractions, pathlib, uuid
