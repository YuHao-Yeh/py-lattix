"""Generic object adaptation and reconstruction framework.

This module provides a centralized registry system for converting complex
Python objects into serializable representations (Adapters) and safely
reconstructing objects from primitive collections (Constructors).

The framework consists of three primary systems:
    1. **Adapter Registry**: Maps types to conversion functions. Supports
       Method Resolution Order (MRO) lookup, allowing a single adapter to
       handle an entire class hierarchy.
    2. **Constructor Registry**: Stores metadata required to rebuild
       specialized containers (e.g., ``deque``, ``array``, ``Path``) that
       cannot be initialized with a simple collection argument.
    3. **Plugin System**: Enables dynamic discovery and registration of
       third-party adapters at runtime.

This module is part of Lattix's internal core layer and facilitates
integration with the broader Python data stack (NumPy, Pandas, etc.)
without requiring hard dependencies.
"""

from __future__ import annotations

import inspect
import logging
import pkgutil
from array import array
from collections import ChainMap, defaultdict, deque
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from ..utils.types import (
        Adapter,
        AdapterRegistry,
        ArgsRegistry,
        Set,
    )

    dict_items = type({}.items())

__all__ = [
    # adapters
    "fqname_for_cls",
    "register_adapter",
    "unregister_adapter",
    "get_adapter_registry",
    "get_adapter",
    # constructor defaults
    "register_constructor_defaults",
    "unregister_constructor_defaults",
    "get_defaults_registry",
    "construct_from_iterable",
    "construct_from_mapping",
    # helpers
    "discover_and_register_plugins",
]


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")

logger = logging.getLogger(__name__)

# ======================================================
# Registry keyed by fully-qualified class name
# ======================================================
# Use mapping: fqname -> adapter callable
_ADAPTERS: AdapterRegistry = {}


def fqname_for_cls(cls: type[Any]) -> str:
    """Generate the fully-qualified name for a class.

    The name is formatted as ``module_name.class_name``.

    Args:
        cls: The class type to identify.

    Returns:
        str: The fully-qualified name string.
    """
    return f"{cls.__module__}.{cls.__qualname__}"


def register_adapter(cls: type[Any], func: Adapter) -> None:
    """Register a conversion adapter for a specific type.

    Args:
        cls: The class type to associate with the adapter.
        func: A callable that handles conversion for objects of this type.
            The callable typically accepts the object and a recursion function.

    Note:
        Registering an adapter automatically invalidates the internal lookup
        cache to ensure the new adapter is recognized.
    """
    key = fqname_for_cls(cls)
    _ADAPTERS[key] = func
    _get_adapter_for_type.cache_clear()  # clear cache for get_adapter


def unregister_adapter(cls: type[Any]) -> None:
    """Remove a registered adapter for a specific type.

    Args:
        cls: The class type whose adapter should be removed.
    """
    key = fqname_for_cls(cls)
    if key in _ADAPTERS:
        del _ADAPTERS[key]
    _get_adapter_for_type.cache_clear()


def get_adapter_registry() -> AdapterRegistry:
    """Return a copy of the current adapter registry.

    Returns:
        AdapterRegistry: A dictionary mapping fully-qualified names to adapters.
    """
    return dict(_ADAPTERS)


# ======================================================
# Fast adapter lookup using LRU cache
# ======================================================
_LAZY_LIBRARY_HANDLERS: Set[str] = {"numpy", "pandas", "torch", "xarray"}


def _ensure_library_adapters(obj: Any) -> None:
    """Detect if an object belongs to a library with deferred adapters.

    If the object's root module matches one of the known third-party
    libraries, this function imports the corresponding adapter module
    and executes its registration logic. Once a library is loaded,
    it is removed from the tracking set.

    Args:
        obj: The object to inspect for library membership.
    """
    try:
        obj_type = obj if isinstance(obj, type) else type(obj)
        root_module = obj_type.__module__.split(".")[0]
    except (AttributeError, IndexError):
        return

    if root_module in _LAZY_LIBRARY_HANDLERS:
        try:
            reg: Callable[[], None] | None = None

            if root_module == "numpy":
                from .numpy import _register_numpy_adapters as reg
            elif root_module == "pandas":
                from .pandas import _register_pandas_adapters as reg
            elif root_module == "torch":
                from .torch import _register_torch_adapters as reg
            elif root_module == "xarray":
                from .xarray import _register_xarray_adapters as reg

            if reg:
                reg()
                _LAZY_LIBRARY_HANDLERS.remove(root_module)
        except Exception as e:
            logger.error(f"Failed to load {root_module} adapter: {e}")


@lru_cache(maxsize=2048)
def _get_adapter_for_type(t: type) -> Adapter | None:
    """Resolve an adapter for a type using an MRO-aware strategy.

    Resolution Strategy:
        1. Attempt an exact match using the fully-qualified name.
        2. Walk the Method Resolution Order (MRO) from specific to general
           and return the first registered adapter found for a base class.

    Args:
        t: The class type to resolve.

    Returns:
        Optional[Adapter]: The resolved adapter function, or None if no
            adapter is found.
    """
    # exact
    key = fqname_for_cls(t)

    if key in _ADAPTERS:
        return _ADAPTERS[key]

    # mro search (skip object)
    for base in inspect.getmro(t)[1:]:
        if base is object:
            break
        bkey = fqname_for_cls(base)
        if bkey in _ADAPTERS:
            return _ADAPTERS[bkey]
    return None


def get_adapter(x: Any) -> Adapter | None:
    """Retrieve a registered adapter for the given value.

    This is the primary lookup method. It first triggers a check to see
    if any third-party adapters need to be loaded based on the type
    of `x`, then queries the internal adapter registry.

    Args:
        x: The object for which to find an adapter.

    Returns:
        Optional[Adapter]: A callable that handles conversion for the
            object's type, or None if no adapter is registered.
    """
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


def register_constructor_defaults(cls: type[Any], /, **defaults: Any) -> None:
    """Explicitly register initialization metadata for a class.

    This metadata is used by ``construct_from_*`` functions to rebuild
    specialized containers that require specific positional or keyword
    arguments.

    Args:
        cls: The class type to register.
        **defaults: Arbitrary configuration for the constructor.
            Special keys supported:
            - `_posargs` (list): Positional arguments passed before the data.
            - `_expand` (bool): If True, the data is expanded as (*args).

    Example:
        >>> register_constructor_defaults(deque, _posargs=[[]], maxlen=None)
    """
    fqname = fqname_for_cls(cls)
    _CONSTRUCTOR_DEFAULTS[fqname] = dict(defaults)


def unregister_constructor_defaults(cls: type[Any]):
    """Remove constructor metadata for a specific type.

    Args:
        cls: The class type to unregister.
    """
    fqname = fqname_for_cls(cls)
    if fqname in _CONSTRUCTOR_DEFAULTS:
        del _CONSTRUCTOR_DEFAULTS[fqname]


def get_defaults_registry() -> ArgsRegistry[Any]:
    """Return a copy of the current constructor defaults registry.

    Returns:
        ArgsRegistry[Any]: The internal registry dictionary.
    """
    return dict(_CONSTRUCTOR_DEFAULTS)


# Initial default registrations
register_constructor_defaults(defaultdict, _posargs=[None])
register_constructor_defaults(ChainMap, maps=[])
register_constructor_defaults(deque, _posargs=[[]], maxlen=None)
register_constructor_defaults(array, _posargs=["b"])
register_constructor_defaults(Path, _expand=True)


def construct_from_iterable(cls: type, iterable: Iterable[Any]) -> Any:
    """Reconstruct a container class from an iterable of elements.

    The function attempts the following strategies in order:
        1. String special-case conversion.
        2. Direct instantiation: ``cls(iterable)``.
        3. Registry-based instantiation using ``_posargs`` or ``_expand``.
        4. Fallback to a standard ``list``.

    Args:
        cls: The target container class.
        iterable: The collection of elements to populate.

    Returns:
        Any: An instance of `cls` containing the data, or a list fallback.
    """
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
                return cls(*iterable, **defaults)
            # Other containers: array, deque, defaultdict, ChainMap, etc.
            return cls(*posargs, iterable, **defaults)
        except Exception:
            pass

    # 4. Fallback：list(iterable)
    return list(iterable)


def construct_from_mapping(
    cls: type[Any], items: Iterable[tuple[_KT, _VT]]
) -> Mapping[_KT, _VT] | str:
    """Reconstruct a mapping class from an iterable of pairs.

    Args:
        cls: The target mapping class (e.g., dict, OrderedDict).
        items: An iterable of (key, value) tuples.

    Returns:
        Mapping: An instance of `cls` containing the items, or a dict fallback.
    """
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
# Plugin discovery helper
# ======================================================


def discover_and_register_plugins(package_name: str) -> list[str]:
    """Dynamically discovers and imports adapter modules from a package.

    This function scans the submodules of the specified package and
    attempts to import them. Submodules are expected to call
    ``register_adapter()`` at the module level upon being imported.

    Args:
        package_name: The fully-qualified name of the package to scan
            (e.g., 'lattix.adapters.ext').

    Returns:
        list[str]: A list of successfully imported module names.
    """
    found: list[str] = []
    try:
        pkg = import_module(package_name)
    except Exception:
        return found

    if not hasattr(pkg, "__path__"):
        return found

    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        try:
            import_module(name)
            found.append(name)
        except Exception as e:
            logger.error(f"Failed to import plugin {name}: {e}", exc_info=True)
            pass
    return found
