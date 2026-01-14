"""JSON serialization utilities for Lattix.

This module provides functions to convert Lattix objects and other complex
Python structures into JSON format. it supports both the standard library
``json`` module and the high-performance ``orjson`` library.

Both functions rely on Lattix's internal serialization framework to ensure
that specialized types (like NumPy arrays, Pandas DataFrames, or Lattix nodes)
are properly transformed into JSON-compatible primitives.
"""

from typing import Any

from ..utils import compat, transform
from ..utils.exceptions import OptionalImportError

__all__ = ["to_json", "to_orjson"]


def to_json(obj: Any, **kwargs: Any) -> str:
    """Serialize an object to a JSON-formatted string.

    Uses the standard library ``json.dumps``. The object is first passed
    through Lattix's generic serializer to handle non-primitive types.

    Args:
        obj: The object to serialize.
        **kwargs: Additional keyword arguments passed to ``json.dumps``
            (e.g., indent, sort_keys).

    Returns:
        str: A JSON-formatted string.
    """
    import json

    return json.dumps(transform.serialize(obj), **kwargs)


def to_orjson(obj: Any, **kwargs: Any) -> bytes:
    """Serialize an object to JSON bytes using the orjson library.

    orjson is significantly faster than the standard library and has
    native support for types like dataclasses and datetimes. This function
    configures orjson to support NumPy arrays and non-string keys
    automatically.

    Args:
        obj: The object to serialize.
        **kwargs: Additional keyword arguments passed to ``orjson.dumps``.

    Returns:
        bytes: A JSON-formatted byte string.

    Raises:
        OptionalImportError: If the ``orjson`` library is not installed.
    """
    if not compat.HAS_ORJSON:
        raise OptionalImportError("orjson", "JSON serialization", "orjson")

    return compat.orjson.dumps(
        obj,
        default=lambda x: transform.serialize(x),
        option=compat.orjson.OPT_SERIALIZE_NUMPY | compat.orjson.OPT_NON_STR_KEYS,
        **kwargs,
    )
