from __future__ import annotations
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from .._core.base import LattixNode

if TYPE_CHECKING:
    from typing import TypeVar

    _KT = TypeVar("_KT")
    _VT = TypeVar("_VT")
    MappingT = Mapping[_KT, _VT]


def recursive_merge(target: Any, source: Mapping[_KT, _VT], overwrite: bool = True):
    """Deep merge source into target."""
    for k, v in source.items():
        if k in target and isinstance(target[k], Mapping) and isinstance(v, Mapping):
            recursive_merge(target[k], v, overwrite)
        elif overwrite or k not in target:
            if hasattr(target, "_construct_child") and isinstance(v, Mapping):
                # Convert dicts to Lattix nodes on the fly
                child = target._construct_child(k)
                recursive_merge(child, v, overwrite)
                target[k] = child
            else:
                target[k] = v
    return target


def set_operation(left: Mapping[_KT, _VT], right: Mapping[_KT, _VT], op: str, inplace: bool = False) -> Any:
    """Generic handler for &, |, -, ^"""
    res = left if inplace else left.clone(deep=True)
    
    left_keys = set(left.keys())
    right_keys = set(right.keys())

    if op in ("&", "-"):
        keys_to_iter = list(left_keys)
    else:   # "|", "^"
        keys_to_iter = list(left_keys) + [k for k in right_keys if k not in left_keys]
    
    keep_left_only  = op in ("|", "-", "^")
    keep_right_only = op in ("|", "^")

    is_pruning_op = op in ("-", "^")

    delete_keys = []

    for key in keys_to_iter:
        v1, v2 = left.get(key)

    if op == "and": # Intersection
        # Remove keys not in right
        for k in left_keys - right_keys:
            del res[k]
        # Recurse on common
        for k in left_keys & right_keys:
            if isinstance(res[k], Mapping) and isinstance(right[k], Mapping):
                set_operation(res[k], right[k], "and", inplace=True)

    elif op == "or": # Union
        for k, v in right.items():
            if k not in res:
                res[k] = v # Should clone if deep
            elif isinstance(res[k], Mapping) and isinstance(v, Mapping):
                set_operation(res[k], v, "or", inplace=True)

    # ... Implement sub/xor similarly ...
    
    return res