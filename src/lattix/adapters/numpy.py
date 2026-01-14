"""NumPy type adapter for Lattix.

This module provides conversion logic for NumPy data structures, allowing
``numpy.ndarray`` objects to be treated as standard Python lists during
serialization or deep conversion.
"""

from typing import Any

from ..utils import compat
from ..utils.types import RecurseFunc
from .registry import register_adapter

__all__ = ["_register_numpy_adapters"]


def _register_numpy_adapters() -> None:
    """Registers the adapter for NumPy ndarrays.

    If NumPy is installed, this function associates ``numpy.ndarray``
    with a handler that converts arrays to nested lists using the
    native ``tolist()`` method.
    """
    if not compat.HAS_NUMPY:
        return

    def handle_numpy_array(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.tolist()
        except Exception:
            return list(value)

    register_adapter(compat.numpy.ndarray, handle_numpy_array)
