"""Xarray type adapter for Lattix.

This module provides conversion logic for Xarray DataArrays and Datasets,
extracting the underlying coordinate and variable data into standard
Python collections.
"""

from typing import Any

from ..utils import compat
from ..utils.types import RecurseFunc
from .registry import register_adapter

__all__ = ["_register_xarray_adapters"]


def _register_xarray_adapters() -> None:
    """Registers adapters for Xarray DataArray and Dataset objects.

    The conversion strategy is:
        - DataArray: Underlying values are converted to a list.
        - Dataset: Converted to a dictionary mapping variable names to lists.
    """
    if not compat.HAS_XARRAY:
        return
    xm = compat.xarray

    def handle_dataarray(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.values.tolist()
        except Exception:
            return list(value.values)

    def handle_dataset(value: Any, recurse: RecurseFunc) -> Any:
        return {k: v.values.tolist() for k, v in value.data_vars.items()}

    register_adapter(xm.DataArray, handle_dataarray)
    register_adapter(xm.Dataset, handle_dataset)
