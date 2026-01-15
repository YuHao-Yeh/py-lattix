"""Data type introspection and class attribute discovery.

This module provides utilities for inspecting Python objects at runtime to
determine their structural roles within Lattix (e.g., whether they are
atomic scalars or containers requiring recursion). It also includes
optimized class-scanning logic to support dynamic attribute access.
"""

from __future__ import annotations

import sys
from typing import Any

from . import compat
from .types import _ATOMIC_BASE_TYPES, AtomicTypes, ScalarTypes, TypeGuard

if sys.version_info >= (3, 9):
    from functools import cache
else:
    from functools import lru_cache as cache

__all__ = ["is_primitive", "is_scalar", "scan_class_attrs"]

_HAS_PANDAS = compat.HAS_PANDAS
_HAS_NUMPY = compat.HAS_NUMPY
_HAS_TORCH = compat.HAS_TORCH
_HAS_XARRAY = compat.HAS_XARRAY
pandas = pd = compat.pandas
xarray = xr = compat.xarray

_NDARRAY = compat.numpy.ndarray if _HAS_NUMPY else type(None)
_TENSOR = compat.torch.Tensor if _HAS_TORCH else type(None)


# ======================================================
# Data Type helper
# ======================================================
def is_primitive(obj: Any) -> TypeGuard[AtomicTypes]:
    """Check if an object is a fundamental atomic type.

    Atomic types include basic built-ins (str, int, float, bool, None, bytes)
    and common standard library scalars (Decimal, Path, datetime, etc.).

    Args:
        obj: The object to inspect.

    Returns:
        bool: True if the object is considered a primitive atomic value.
    """
    return isinstance(obj, _ATOMIC_BASE_TYPES)


def is_scalar(obj: Any) -> TypeGuard[ScalarTypes]:
    """Check if an object is a scalar value, including Data Science types.

    In addition to basic primitives, this function recognizes NumPy ndarrays,
    Pandas DataFrames/Series, Torch Tensors, and Xarray DataArray/Dataset as
    scalar "leaf" units in the context of traversal logic.

    Args:
        obj: The object to inspect.

    Returns:
        bool: True if the object is a primitive or a supported third-party scalar.
    """
    # 1. Check primitives first (Fastest path)
    if isinstance(obj, _ATOMIC_BASE_TYPES):
        return True

    # 2. Check Pandas
    if _HAS_PANDAS and isinstance(obj, (pd.DataFrame, pd.Series)):
        return True

    # 3. Check Numpy
    if _HAS_NUMPY and isinstance(obj, _NDARRAY):
        return True

    if _HAS_TORCH and isinstance(obj, _TENSOR):
        return True

    # 5. NEW: Check Xarray
    if _HAS_XARRAY and isinstance(obj, (xr.DataArray, xr.Dataset)):
        return True

    return False


# ======================================================
# class attribute scanner
# ======================================================
@cache
def scan_class_attrs(cls: type[Any]) -> set[str]:
    """Scan a class and its entire MRO for defined attribute names.

    This is used by Lattix to distinguish between class-level members
    (methods, properties) and dynamic mapping keys. The results are
    cached for performance.

    Args:
        cls: The class to inspect.

    Returns:
        set[str]: A set of all attribute names found in the inheritance tree.
    """
    attrs: set[str] = set()
    for base in cls.__mro__:
        # attrs |= base.__dict__.keys()
        if base is object:
            continue
        attrs.update(base.__dict__.keys())
    return attrs
