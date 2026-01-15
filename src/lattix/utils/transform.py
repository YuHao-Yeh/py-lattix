"""Recursive data transformation and serialization logic.

This module contains the "heavy lifters" of the Lattix utility suite. It
manages the recursive conversion of hierarchies between different mapping
types and prepares data for external serialization (JSON, YAML, etc.).
"""

from __future__ import annotations

import sys
from typing import Any, TypeVar, cast

from ..adapters.registry import (
    construct_from_iterable,
    construct_from_mapping,
    get_adapter,
)
from .inspection import is_primitive

if sys.version_info >= (3, 9):
    from collections.abc import Iterable, Mapping
else:
    from typing import Iterable, Mapping

__all__ = ["deep_convert", "serialize", "flatten", "unflatten"]

_VT = TypeVar("_VT")


# ======================================================
# deep_convert
# ======================================================
def deep_convert(value: Any, ftype: type = dict, **kwargs: Any) -> Any:
    """Recursively convert nested structures into a target collection type.

    This function traverses the input hierarchy and transforms all nested
    mappings and iterables into the type specified by `ftype`. It is
    primarily used to convert Lattix objects back into plain dictionaries
    or lists.

    The conversion follows this priority:
        1. Custom Adapters: If a type adapter is registered, it handles the value.
        2. Primitives: Atomic types are returned as-is.
        3. Mappings: Nested mappings are converted recursively.
        4. Iterables: Sequences are converted recursively.

    Args:
        value: The object/hierarchy to convert.
        ftype: The target type for collections (e.g., dict, UserDict, list).
            Defaults to dict.
        **kwargs: Additional arguments passed to specialized constructors.

    Returns:
        Any: The converted structure where all nodes are of type `ftype`.
    """
    # 0. Check adapters first
    if adapter := get_adapter(value):
        return adapter(value, lambda v: deep_convert(v, ftype, **kwargs))

    # 1. Primitives pass through
    if is_primitive(value):
        return value

    # 2. Handle Mappings
    if isinstance(value, Mapping):
        if ftype is str:
            return str(value)
        items_gen: Iterable[Any]

        # dict / OrderedDict / UserDict / ...
        if issubclass(ftype, Mapping):
            items_gen = (
                (str(key), deep_convert(val, ftype, **kwargs))
                for key, val in value.items()
            )
            return construct_from_mapping(ftype, cast(Mapping[Any, Any], items_gen))

        if issubclass(ftype, list):
            items_gen = (
                [str(key), deep_convert(val, ftype, **kwargs)]
                for key, val in value.items()
            )
        else:
            items_gen = (
                (str(key), deep_convert(val, ftype, **kwargs))
                for key, val in value.items()
            )

        # built = construct_from_iterable(ftype, cast(Iterable[Any], items_gen))
        built = construct_from_iterable(ftype, items_gen)

        if len(built) == 1:
            first = built[0]
            if isinstance(first, (list, tuple)) and len(first) == 2:
                return cast(Any, ftype)(first)
        return built

    # 3. Handle Iterabls
    if isinstance(value, Iterable):
        return construct_from_iterable(
            ftype, (deep_convert(v, ftype, **kwargs) for v in value)
        )

    # 4. Fallback
    return value


# ======================================================
# serialize
# ======================================================
def serialize(obj: Any, _seen: set[int] | None = None) -> Any:
    """Recursively transform an object into Python-serializable primitives.

    This function prepares complex hierarchies for export. It ensures that
    non-standard keys are stringified, circular references are detected,
    and third-party objects (Tensors, DataFrames) are converted into
    standard Python collections.

    Rules:
        - Primitives: Returned as-is.
        - Circular Refs: Returns a string marker indicating the circularity.
        - Adapters: Delegates to registered handlers if available.
        - Mappings: Recursively serializes keys (to str) and values.
        - Sets: Recurseively serializes values into sets.
        - Tuples: Recusively serialized values into tuples.
        - Iterables: Serialized into lists.
        - Objects: Serialized based on ``__dict__`` or ``__slots__``.

    Args:
        obj: The object to serialize.
        _seen: Internal set used for cycle detection.

    Returns:
        Any: A structure composed entirely of serializable Python primitives.
    """
    if _seen is None:
        _seen = set()

    # 1. Primitives
    if is_primitive(obj):
        return obj

    # 2. Cycle Detection
    oid = id(obj)
    if oid in _seen:
        return f"<Circular {type(obj).__name__} at {hex(oid)}>"
    _seen.add(oid)

    try:
        # 3. Adapter check
        if adapter := get_adapter(obj):
            return adapter(obj, lambda x: serialize(x, _seen))

        # 4. Mapping
        if isinstance(obj, Mapping):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                sk = k if isinstance(k, str) else str(k)
                out[sk] = serialize(v, _seen)
            return out

        # 5. Set
        if isinstance(obj, (set, frozenset)):
            return {serialize(x, _seen) for x in obj}

        # 6. Tuple
        if isinstance(obj, tuple):
            return tuple(serialize(x, _seen) for x in obj)

        # 7. Iterable (exclude str/bytes)
        if isinstance(obj, Iterable):
            return [serialize(x, _seen) for x in obj]

        # 8. Object with __dict__
        if hasattr(obj, "__dict__") and vars(obj):
            return {
                k: serialize(v, _seen)
                for k, v in vars(obj).items()
                if not k.startswith("_")
            }

        # 9. Object with __slots__
        if hasattr(obj, "__slots__"):
            return {
                k: serialize(getattr(obj, k), _seen)
                for k in obj.__slots__
                if not k.startswith("_") and hasattr(obj, k)
            }

        # 10. Fallback
        try:
            return str(obj)
        except Exception:
            return repr(obj)

    finally:
        _seen.remove(oid)


# ======================================================
# flatten / unflatten
# ======================================================
def flatten(value: Mapping[str, _VT], sep: str = ".") -> dict[str, Any]:
    """Collapses a nested mapping into a single level with compound keys.

    Example:
        >>> data = {"a": {"b": 1}}
        >>> flatten(data, sep="/")
        {'a/b': 1}

    Args:
        value: The nested mapping to flatten.
        sep: The string used to join path segments. Defaults to ".".

    Returns:
        dict[str, Any]: A flat dictionary where keys represent hierarchical paths.
    """
    res: dict[str, Any] = {}
    # Stack stores (path_tuple, current_value)
    stack: list[tuple[tuple[str, ...], Any]] = [((), value)]

    while stack:
        path, cur = stack.pop()

        if not isinstance(cur, Mapping):
            res[sep.join(path)] = cur
            continue

        for key, val in cur.items():
            new_path = (*path, key)
            if isinstance(val, Mapping) and val:
                stack.append((new_path, val))  # pyright: ignore
            else:
                res[sep.join(new_path)] = val
    return res


def unflatten(value: Mapping[str, _VT], sep: str = ".") -> dict[str, Any]:
    """Expand a flat mapping with compound keys into a nested structure.

    This is the inverse of :func:`flatten`.

    Args:
        value: The flat mapping to expand.
        sep: The string used to split path segments. Defaults to ".".

    Returns:
        dict[str, Any]: A nested dictionary hierarchy.

    Raises:
        ValueError: If a path segment conflicts with an existing scalar value
            (e.g., trying to nest a key inside an integer).
    """
    res: dict[str, Any] = {}
    for key, val in value.items():
        parts = key.split(sep)
        target = res

        # for i in len(parts) - 1:
        for part in parts[:-1]:
            child = target.get(part)
            # Create dict if missing or overwrite if scalar collision occurs
            if child is None:
                child = target[part] = {}
            elif not isinstance(child, dict):
                # Option A: Overwrite
                # child = target[part] = {}
                # Option B: Raise error
                raise ValueError(
                    f"Key conflict: '{part}' is scalar, cannot become dict"
                )
            target = child

        target[parts[-1]] = val
    return res
