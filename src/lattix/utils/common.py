from __future__ import annotations

__all__ = [
    "deep_convert",
    "serialize",
    "flatten",
    "unflatten",
    "scan_class_attrs",
    "strip_ansi",
    "is_primitive",
    "is_scalar",
]

import re
import sys
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Any, TypeVar, cast

from ..adapters.generic import (
    construct_from_iterable, construct_from_mapping, get_adapter
)
from . import compat
from .types import (
    _ATOMIC_BASE_TYPES, AtomicTypes, ScalarTypes, TypeGuard, DictType, ListType
)

if TYPE_CHECKING:   # pragma: no cover
    import sys
    from .types import DictType, ListType, SetType, TupleType, TypeType

    MappingT = TypeVar("MappingT", bound=Mapping[Any, Any])
    IterableT = TypeVar("IterableT", bound=Iterable[Any])
    
    if sys.version_info >= (3, 10):
        ContainerT = TypeType[MappingT] | TypeType[IterableT]
    else:
        from typing import Union
        ContainerT = Union[TypeType[MappingT], TypeType[IterableT]]
    
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")

HAS_NUMPY = compat.HAS_NUMPY
HAS_PANDAS = compat.HAS_PANDAS
numpy = np = compat.numpy
pandas = pd = compat.pandas


# ======================================================
# Data Type helper
# ======================================================

def is_primitive(obj: Any) -> TypeGuard[AtomicTypes]:
    return isinstance(obj, _ATOMIC_BASE_TYPES)

def is_scalar(obj: Any) -> TypeGuard[ScalarTypes]:
    # 1. Check primitives first (Fastest path)
    if isinstance(obj, _ATOMIC_BASE_TYPES):
        return True

    # 2. Check Pandas
    if HAS_PANDAS and isinstance(obj, (pd.DataFrame, pd.Series)):
        return True
    
    # 3. Check Numpy
    if HAS_NUMPY and isinstance(obj, np.ndarray):
        return True
    
    return False


# ======================================================
# ANSI helper
# ======================================================

_ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str):
    """Helper to remove ANSI color codes."""
    # return re.sub(r'\x1b\[[0-9;]*m', '', text)
    return _ANSI_ESCAPE_RE.sub('', text)


# ======================================================
# deep_convert
# ======================================================

def deep_convert(
    value: Any,
    ftype: TypeType[Any] = dict,
    **kwargs: Any
) -> Any:
    """Recursively convert nested structures to given type."""

    # 0. Check adapters first
    if (adapter := get_adapter(value)):
        return adapter(
            value,
            lambda v: deep_convert(v, ftype, **kwargs)
        )
    
    # 1. Primitives pass through
    if is_primitive(value):
        return value

    # 2. Handle Mappings
    if isinstance(value, Mapping):
        map_obj = cast(Mapping[Any, Any], value)

        if ftype is str:
            return str(value)

        # dict / OrderedDict / UserDict / ...
        if issubclass(ftype, Mapping):
            items_gen = (
                (str(key), deep_convert(val, ftype, **kwargs)) 
                for key, val in map_obj.items()
            )
            return construct_from_mapping(ftype, items_gen)
        
        if issubclass(ftype, list):
            items_gen = (
                [str(key), deep_convert(val, ftype, **kwargs)]
                for key, val in map_obj.items()
            )
        else:
            items_gen = (
                (str(key), deep_convert(val, ftype, **kwargs))
                for key, val in map_obj.items()
            )
                
        built = construct_from_iterable(ftype, items_gen)

        if len(built) == 1:
            first = built[0]
            if isinstance(first, (list, tuple)) and len(first) == 2:
                return ftype(first)
        return built
    
    # 3. Handle Iterabls
    if isinstance(value, Iterable):
        iter_obj = cast(Iterable[Any], value)
        return construct_from_iterable(
            ftype,
            (deep_convert(v, ftype, **kwargs) for v in iter_obj)
        )
    
    # 4. Fallback
    return value


# ======================================================
# serialize
# ======================================================

def serialize(
    obj: Any,
    _seen: SetType[int] | None = None
) -> Any:
    """Recursively adapt `obj` into plain Python serializable structures.
    
    Rules:
        - primitives: return as-is
        - dict-like: recursively serialize keys (if not hashable, convert to str)
        - iterable: serialize each item
        - objects with adapters: call adapter(value, recurse)
        - objects with __dict__: serialize its attrs

    This function is intentionally conservative to avoid surprising expansion.
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
        if (adapter := get_adapter(obj)):
            return adapter(obj, lambda x: serialize(x, _seen))

        # 4. Mapping
        if isinstance(obj, Mapping):
            map_obj = cast(Mapping[_KT, _VT], obj)
            out : DictType[str, Any] = {}
            for k, v in map_obj.items():
                sk = k if isinstance(k, str) else str(k)
                out[sk] = serialize(v, _seen)
            return out

        # 5. Iterable (exclude str/bytes)
        if isinstance(obj, Iterable):
            return [serialize(x, _seen) for x in obj]

        # 6. Object with __dict__
        if hasattr(obj, "__dict__") and vars(obj):
            return {
                k: serialize(v, _seen) 
                for k, v in vars(obj).items() 
                if not k.startswith("_")
            }
        
        # 7. Object with __slots__
        if hasattr(obj, "__slots__"):
            return {
                k: serialize(getattr(obj, k), _seen) 
                for k in obj.__slots__
                if not k.startswith("_") and hasattr(obj, k)
            }

        # 8. Fallback
        try:
            return str(obj)
        except Exception:
            return repr(obj)

    finally:
       _seen.remove(oid)


# ======================================================
# flatten / unflatten
# ======================================================

def flatten(value: Mapping[str, Any], sep: str = ".") -> DictType[str, Any]:
    """Flatten nested mapping into a single level with compound keys."""
    res: DictType[str, Any] = {}
    # Stack stores (path_tuple, current_value)
    stack : ListType[TupleType[TupleType[str, ...], Any]] = [((), value)]

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


def unflatten(value: Mapping[str, _VT], sep: str = ".") -> DictType[str, _VT]:
    """Unflatten mapping back to nested form."""
    res: DictType[str, Any] = {}
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
                raise ValueError(f"Key conflict: '{part}' is scalar, cannot become dict")
            target = child

        target[parts[-1]] = val
    return res


# ======================================================
# class attribute scanner
# ======================================================

@lru_cache(maxsize=None)
def scan_class_attrs(cls: TypeType[Any]) -> SetType[str]:
    attrs: SetType[str] = set()
    for base in cls.__mro__:
        # attrs |= base.__dict__.keys()
        if base is object:
            continue
        attrs.update(base.__dict__.keys())
    return attrs



if __name__ == "__main__":
    # test serialize
    import math
    from pathlib import Path
    from pprint import pprint

    class Slotted:
        __slots__ = ['x', 'y']
        def __init__(self):
            self.x = 10
            self.y = 20

    obj_data: DictType[str, Any] = {
        "a": 1,
        "b": [1, 2, 3],
        "m1": {"a": 1},
        "m2": {"a.b": 2},
        "m3": {"a": 1, "a.b": 2},
        "pi": math.pi,
        "p": Path("/tmp") if 'Path' in globals() else None,
        "s": Slotted(),
    }
    print("--- Serialize ---")
    pprint(serialize(obj_data))
    # Expect:
    # {'a': 1,
    #  'b': [1, 2, 3],
    #  'm1': {'a': 1},
    #  'm2': {'a.b': 2},
    #  'm3': {'a': 1, 'a.b': 2},
    #  'p': WindowsPath('/tmp'),
    #  'pi': 3.141592653589793,
    #  's': {'x': 10, 'y': 20}}

    print("\n--- Flatten ---")
    flat = flatten(obj_data, sep="/")
    pprint(flat)
    # Expect:
    # {'a': 1,
    #  'b': [1, 2, 3],
    #  'm1/a': 1,
    #  'm2/a.b': 2,
    #  'm3/a': 1,
    #  'm3/a.b': 2,
    #  'p': WindowsPath('/tmp'),
    #  'pi': 3.141592653589793,
    #  's': <__main__.Slotted object at ...>}

    print("\n--- Unflatten ---")
    pprint(unflatten(flat, sep="/"))
    # Expect:
    # {'a': 1,
    #  'b': [1, 2, 3],
    #  'm1': {'a': 1},
    #  'm2': {'a.b': 2},
    #  'm3': {'a': 1, 'a.b': 2},
    #  'p': WindowsPath('/tmp'),
    #  'pi': 3.141592653589793,
    #  's': <__main__.Slotted object at ...>}