"""Pandas type adapter for Lattix.

This module provides conversion logic for Pandas DataFrames and Series,
ensuring they are transformed into JSON-serializable formats (lists and
dictionaries) during Lattix operations.
"""

from typing import Any

from ..utils import compat
from ..utils.types import RecurseFunc
from .registry import register_adapter

__all__ = ["_register_pandas_adapters"]


def _register_pandas_adapters() -> None:
    """Registers adapters for Pandas Series and DataFrames.

    The conversion strategy is:
        - Series: Converted to a standard Python list.
        - DataFrame: Converted to a dictionary of lists (orient='list').
    """
    if not compat.HAS_PANDAS:
        return

    def handle_series(value: Any, recurse: RecurseFunc) -> Any:
        return value.tolist()

    def handle_dataframe(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.to_dict(orient="list")
        except Exception:
            return value.to_dict()

    register_adapter(compat.pandas.Series, handle_series)
    register_adapter(compat.pandas.DataFrame, handle_dataframe)
