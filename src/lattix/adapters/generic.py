from __future__ import annotations

__all__ = [
    # adapters
    "fqname_for_cls", "register_adapter", "unregister_adapter", 
    "get_adapter_registry", "get_adapter",
    # constructor defaults 
    "register_constructor_defaults", "unregister_constructor_defaults", 
    "get_defaults_registry", "construct_from_iterable", 
    "construct_from_mapping",
    # helpers
    "discover_and_register_plugins",
]

from array import array
from collections import ChainMap, defaultdict, deque
from functools import lru_cache
from importlib import import_module
import inspect
import logging
from pathlib import Path
import pkgutil
from typing import TYPE_CHECKING, Any, TypeVar

from ..utils.compat import get_module

if TYPE_CHECKING:   # pragma: no cover
    from collections.abc import Callable, Iterable, Mapping
    from ..utils.types import (
        Adapter, RecurseFunc,
        DictType, ListType, TupleType, TypeType,
        AdapterRegistry, ArgsRegistry
    )
    dict_items = type({}.items())

logger = logging.getLogger(__name__)
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")

# ======================================================
# Registry keyed by fully-qualified class name
# ======================================================
# Use mapping: fqname -> adapter callable
_ADAPTERS: AdapterRegistry = {}

def fqname_for_cls(cls: TypeType[Any]) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"

def register_adapter(cls: TypeType[Any], func: Adapter) -> None:
    """Register a custom adapter for `cls`
    
    Args:
        - cls : The class type to associate with the adapter.
        - func : A callable that handles conversion for objects of this type.
    
    Usage:
        register_adapter(SomeType, handler_function)
    """
    key = fqname_for_cls(cls)
    _ADAPTERS[key] = func
    _get_adapter_for_type.cache_clear()  # clear cache for get_adapter
   
def unregister_adapter(cls: TypeType[Any]) -> None:
    key = fqname_for_cls(cls)
    if key in _ADAPTERS:
        del _ADAPTERS[key]
    _get_adapter_for_type.cache_clear()

def get_adapter_registry() -> AdapterRegistry:
    return dict(_ADAPTERS)


# ======================================================
# Lazy Library Initialization Logic
# ======================================================
# These functions are only called if an object from the library is actually encountered.

def _register_numpy_adapters() -> None:
    """Called only when a numpy object is encountered."""
    np_pkg = get_module("numpy")
    if not np_pkg:
        return

    def handle_numpy_array(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.tolist()
        except Exception:
            return list(value)
    
    register_adapter(np_pkg.ndarray, handle_numpy_array)

def _register_pandas_adapters() -> None:
    """Called only when a pandas object is encountered."""
    pd_pkg = get_module("pandas")
    if not pd_pkg:
        return

    def handle_series(value: Any, recurse: RecurseFunc) -> Any:
        return value.tolist()

    def handle_dataframe(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.to_dict(orient="list")
        except Exception:
            return value.to_dict()

    register_adapter(pd_pkg.Series, handle_series)
    register_adapter(pd_pkg.DataFrame, handle_dataframe)

def _register_torch_adapters() -> None:
    """Called only when a torch object is encountered."""
    tm = get_module("torch")
    if not tm:
        return

    def handle_tensor(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.tolist()
        except Exception:
            # handle GPU/Grad tensors
            return value.detach().cpu().numpy().tolist()

    register_adapter(tm.Tensor, handle_tensor)

    if hasattr(tm, "nn") and hasattr(tm.nn, "Parameter"):
        def handle_param(value: Any, recurse: RecurseFunc) -> Any:
            return handle_tensor(value.data, recurse)
        register_adapter(tm.nn.Parameter, handle_param)

def _register_xarray_adapters() -> None:
    """Called only when an xarray object is encountered."""
    xm = get_module("xarray")
    if not xm: 
        return

    def handle_dataarray(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.values.tolist()
        except Exception:
            return list(value.values)

    def handle_dataset(value: Any, recurse: RecurseFunc) -> Any:
        return {k: v.values.tolist() for k, v in value.data_vars.items()}

    register_adapter(xm.DataArray, handle_dataarray)
    register_adapter(xm.Dataset, handle_dataset)

# Map root module names to their registration functions
_LAZY_LIBRARY_HANDLERS: DictType[str, Callable[[], None]] = {
    "numpy": _register_numpy_adapters,
    "pandas": _register_pandas_adapters,
    "torch": _register_torch_adapters,
    "xarray": _register_xarray_adapters,
}

def _ensure_library_adapters(obj: Any) -> None:
    """
    Check if the object belongs to a library that has deferred adapters.
    If so, trigger the registration logic for that library once.
    """
    # 1. Get the top-level module name (e.g., 'numpy' from 'numpy.core.multiarray')
    try:
        obj_type = obj if isinstance(obj, type) else type(obj)
        root_module = obj_type.__module__.split(".")[0]
    except (AttributeError, IndexError):
        return

    # 2. Check if we have a pending handler for this library
    if root_module in _LAZY_LIBRARY_HANDLERS:
        handler = _LAZY_LIBRARY_HANDLERS.pop(root_module)
        logger.debug(f"Initializing deferred adapters for library: {root_module}")
        try:
            handler()
        except Exception as e:
            logger.warning(f"Failed to register adapters for {root_module}: {e}")


# ======================================================
# Fast adapter lookup using LRU cache
# ======================================================

@lru_cache(maxsize=2048)
def _get_adapter_for_type(t: TypeType[Any]) -> Adapter | None:
    """Resolve adapter by exact type or closest registered base class.

    Strategy:
    - Try exact match (module.qualname key)
    - Walk MRO from specific -> general and return first adapter found

    Cached to speed up repeated lookups for same types.
    """
    # exact
    key = f"{t.__module__}.{t.__qualname__}"
    if key in _ADAPTERS:
        return _ADAPTERS[key]

    # mro search (skip object)
    for base in inspect.getmro(t)[1:]:
        if base is object:
            break
        bkey = f"{base.__module__}.{base.__qualname__}"
        if bkey in _ADAPTERS:
            return _ADAPTERS[bkey]
    return None

def get_adapter(x: Any) -> Adapter | None:
    """Public lookup: given a value, return registered adapter or None."""
    if x is None:
        return None
    
    _ensure_library_adapters(x)

    xtype = x if isinstance(x, type) else type(x)
    return _get_adapter_for_type(xtype)


# ======================================================
# Safe construction (conservative)
# ======================================================
# Maintain a separate explicit registry for constructor defaults keyed by fqname
_CONSTRUCTOR_DEFAULTS: ArgsRegistry[Any] = {}

def register_constructor_defaults(cls: TypeType[Any], /, **defaults: Any) -> None:
    """Explicitly register constructor defaults for a class.

    This is safer than attempting to infer defaults from annotations. Use
    this for types that need special handling (deque, array, pathlib.Path, ...).
    Special keys supported:
    - `_posargs`: list of positional args
    - `_expand`: bool
    """
    fqname = fqname_for_cls(cls)
    _CONSTRUCTOR_DEFAULTS[fqname] = dict(defaults)

def unregister_constructor_defaults(cls: TypeType[Any]):
    fqname = fqname_for_cls(cls)
    if fqname in _CONSTRUCTOR_DEFAULTS:
        del _CONSTRUCTOR_DEFAULTS[fqname]

def get_defaults_registry() -> ArgsRegistry[Any]:
    return dict(_CONSTRUCTOR_DEFAULTS)

register_constructor_defaults(defaultdict, _posargs=[None])
register_constructor_defaults(ChainMap, maps=[])
register_constructor_defaults(deque, _posargs=[[]], maxlen=None)
register_constructor_defaults(array, _posargs=["b"])
register_constructor_defaults(Path, _expand=True)


def construct_from_iterable(cls: TypeType[Any], iterable: Iterable[Any]) -> Any:
    name = fqname_for_cls(cls)
    # 1. Special-case str
    if cls is str:
        return str(list(iterable))
    
    # 2. Try direct constructor
    try:
        return cls(iterable)
    except Exception:
        pass
    
    # 3. Try registered defaults
    if name in _CONSTRUCTOR_DEFAULTS:
        defaults = dict(_CONSTRUCTOR_DEFAULTS[name])  # avoid mutating
        posargs = defaults.pop("_posargs", [])
        expand = defaults.pop("_expand", False)
        
        try:
            # Path(*iterable)
            if expand:
                logger.debug(f"[debug expand] calling {name}(*{iterable})")
                return cls(*iterable, **defaults)
            # Other containers: array, deque, defaultdict, ChainMap, etc.
            logger.debug(f"[debug defaults] calling {name}(*{posargs}, iterable, **{defaults})")
            return cls(*posargs, iterable, **defaults)
        except Exception as e:
            logger.debug(f"[debug exception @ default_args] {e!r}")
            pass
    
    # 4. Fallback：list(iterable)
    return list(iterable)

def construct_from_mapping(cls: TypeType[Any], items: Iterable[TupleType[_KT, _VT]]) -> Mapping[_KT, _VT]:
    name = fqname_for_cls(cls)

    # 1. Special-case str
    if cls is str:
        return str(dict(items))

    # 2. Try direct constructor
    try:
        return cls(items)
    except Exception:
        pass

    # 3. Try registered defaults
    if name in _CONSTRUCTOR_DEFAULTS:
        defaults = dict(_CONSTRUCTOR_DEFAULTS[name])
        posargs = defaults.pop("_posargs", [])
        expand = defaults.pop("_expand", False)

        try:
            dict_obj = dict(items)
            if expand:
                return cls(dict_obj, **defaults)
            return cls(*posargs, dict_obj, **defaults)
        except Exception:
            pass

    # 4. Fallback
    return dict(items)


# ======================================================
# Builtin and common adapters (LAZY register)
# ======================================================

def _maybe_register_builtin_adapters() -> None:
    """Register lightweight adapters for standard library containers."""
    def handle_defaultdict(value: defaultdict[_KT, _VT], recurse: RecurseFunc) -> defaultdict[_KT, _VT]:
        return defaultdict(
            value.default_factory, 
            {k: recurse(v) for k, v in value.items()},
        )

    def handle_chainmap(value: ChainMap[_KT, _VT], recurse: RecurseFunc) -> DictType[_KT, Any]:
        merged: DictType[_KT, _VT] = {}
        for m in value.maps:
            merged.update({k: recurse(v) for k, v in m.items()})
        return merged

    register_adapter(defaultdict, handle_defaultdict)
    register_adapter(ChainMap, handle_chainmap)

_maybe_register_builtin_adapters()


# ======================================================
# Plugin discovery helper
# ======================================================

def discover_and_register_plugins(package_name: str) -> ListType[str]:
    """Discover modules under `package_name` and import them.

    Each module may call `register_adapter(...)` at import time. Returns list
    of successfully imported module names.
    """
    found: ListType[str] = []
    try:
        pkg = import_module(package_name)
    except Exception as e:
        logger.debug("package not importable: %s", e)
        return found

    if not hasattr(pkg, "__path__"):
        return found

    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        try:
            import_module(name)
            found.append(name)
        except Exception as e:
            logger.warning("Failed to import plugin %s: %r", name, e)
    return found


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # example: register a custom adapter for Path-like objects lazily
    try:
        from pathlib import Path

        def _path_adapter(p: Path, recurse: Callable[[Any], Any]):
            return str(p)
        register_adapter(Path, _path_adapter)
    except Exception:
        pass

    # explicit constructor defaults example
    from collections import deque
    register_constructor_defaults(deque, _posargs=[[]], maxlen=None)

    # test plugin discovery (no-op example)
    print("plugins:", discover_and_register_plugins("src.lattix.adapters.generic"))
