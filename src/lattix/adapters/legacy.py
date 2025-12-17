"""
adapters.py

Provides a lightweight adapter registry for handling special
container types during recursive data transformations.

This module allows registering custom adapters for specific
types (e.g., defaultdict, ChainMap), enabling flexible conversion
or normalization of various Python objects in a uniform way.
"""
from collections import defaultdict, ChainMap
from collections.abc import Callable, Iterable
from functools import lru_cache
from inspect import signature
import logging
from typing import Any, Type


from ..utils.types import _T, _VT, Adapter, AdapterRegistry, ArgsRegistry, DictType


logger = logging.getLogger(__name__)


__all__ = [
   "ADAPTERS", "_DEFAULT_ARGS", "register_adapter", "get_adapter", 
   "register_constructor_defaults", "construct_from_iterable"
]


ADAPTERS: AdapterRegistry = {}
_DEFAULT_ARGS: ArgsRegistry = {
   "defaultdict": {"_posargs": [None]},            # defaultdict(None)
   "ChainMap": {"maps": []},                       # ChainMap(maps)
   "deque": {"_posargs": [[]], "maxlen": None},    # deque([], maxlen = None)
   "array": {"_posargs": ["b"]},                   # array("b", iterable)
   "Path": {"_expand": True},                      # Path(*iterable)
}


def register_adapter(cls: Type[Any], func: Adapter) -> Any:
   """Register a custom adapter: register_adapter(SomeType, handler_function).
   
   Args:
      - cls : The class type to associate with the adapter.
      - func : A callable that handles conversion for objects of this type.
   """
   ADAPTERS[cls] = func


def get_adapter(value: _VT) -> Adapter:
   """Return the adapter function corresponding to the object's type.
   
   Args:
      - value : The object to look up an adapter for.

   Returns:
      - The registered adapter function if found, otherwise None.
   """
   for cls, func in ADAPTERS.items():
      if isinstance(value, cls):
         return func
   return None


def register_constructor_defaults(cls: Type[Any], **defaults: Any) -> None:
   """Register default constructor arguments for a given class.

   This function allows manual registration of known constructor patterns
   for use by `construct_from_iterable`. It helps avoid repeated introspection or
   failed attempts to guess parameter defaults dynamically.

   Args:
      cls: The class whose constructor defaults should be registered.
      **defaults: Default keyword arguments to use when constructing
                  an instance. You can also include special keys:
                     - `_posargs`: a list of positional arguments
                     - `_expand`: if True, expand the iterable as `*args`

   Example:
      >>> register_constructor_defaults(Path, _expand = True)
      >>> register_constructor_defaults(deque, _posargs = [[]], maxlen = None)
   """
   name = getattr(cls, "__name__", str(cls))
   _DEFAULT_ARGS[name] = dict(defaults)


@lru_cache(maxsize = 64)
def _infer_constructor_defaults(cls: Type[Any]) -> DictType[str, Any]:
   """Infer reasonable constructor defaults for a given class.

   Used internally by `construct_from_iterable` to auto-learn initialization patterns.
   Once inferred, the result is cached (via `lru_cache`) to improve performance.
   """
   # Default return structure
   defaults: DictType[str, Any] = {"_posargs": [], "_expand": False}

   try:
      sig = signature(cls)
   except (ValueError, TypeError):
      # builtin or non-inspectable constructors
      return defaults
   
   # Extract all explicit keyword parameters
   for pname, param in sig.parameters.items():
      if pname == "self":
         continue

      if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
         # Allow expansion in safe_construct()
         defaults["_expand"] = True
         continue
      
      # --- KWARG ---
      if param.default is not param.empty:
         defaults[pname] = param.default
      else:
         ann = param.annotation
         if ann in (int, float):
            defaults[pname] = 0
         elif ann is str:
            defaults[pname] = ""
         elif ann is bool:
            defaults[pname] = False
         elif ann in (list, tuple, set, dict):
            defaults[pname] = ann()
         else:
            pass
            # defaults[pname] = None
   return defaults


def construct_from_iterable(cls: Type[_T], iterable: Iterable) -> Any:
   """Attempt to safely reconstruct a class instance from an iterable.

   `construct_from_iterable` tries multiple strategies to build a container-like
   object from the provided `iterable`. It is designed to handle both
   built-in and user-defined types gracefully, even if their constructors
   are not directly compatible with a single-argument iterable.

   Construction priority:
      1. Directly try `cls(iterable)`
      2. If registered defaults exist in `_DEFAULT_ARGS`, use them
      3. Attempt automatic inference via `signature(cls)` (cached via LRU)
         → and auto-register learned pattern
      4. Fallback to `list(iterable)` or `[iterable]` as last resort

   Args:
      cls: The class type to construct.
      iterable: The data to initialize the instance with.

   Returns:
      An instance of `cls`, or a fallback list if reconstruction fails.

   Notes:
      - `_DEFAULT_ARGS` serves as a registry of known constructor patterns.
      - Use `register_constructor_defaults(cls, **defaults)` to extend it.
      - Automatically caches new patterns after successful introspection.
   """
   if cls is str:
      try:
         return ''.join(map(str, iterable))
      except Exception:    # pragma: no cover
         return str(list(iterable))
   
   # 1. try direct constructor
   try:
      return cls(iterable)
   except Exception:
      pass
   
   # 2. try registered defaults
   name = getattr(cls, "__name__", str(cls))
   if name in _DEFAULT_ARGS:
      defaults = dict(_DEFAULT_ARGS[name])  # avoid mutating
      posargs = defaults.pop("_posargs", [])
      expand = defaults.pop("_expand", False)
         
      try:
         # Path(*iterable)
         if expand:
            logger.debug(f"[debug expand] calling {__name__}(*{iterable})")
            return cls(*iterable, **defaults)
         # Other containers: array, deque, defaultdict, ChainMap 等
         logger.debug(f"[debug defaults] calling {__name__}(*{posargs}, iterable, **{defaults})")
         return cls(*posargs, iterable, **defaults)
      except Exception as e:
         logger.debug(f"[debug exception @ default_args] {e!r}")
         pass
   
   # 3. infer defaults (but DO NOT mutate global defaults)
   inferred = _infer_constructor_defaults(cls)
   cleaned = {k: v for k, v in inferred.items() if not k.startswith('_')}
   register_constructor_defaults(cls, _posargs=[], _expand=inferred.get("_expand", True), **cleaned)
   
   logger.debug(f"[cache learned] {name}: {_DEFAULT_ARGS[name]}")
   try:
      return cls(*iterable, **cleaned) 
   except Exception as e:
      logger.debug(f"[debug exception @ infer] {e!r}")
      pass
   
   # 4. fallback：list(iterable)
   return list(iterable)


# --- Register built-in adapters ---
def _register_builtin_adapters() -> None:
   """Register special handling for Python built-in containers."""
   
   def handle_defaultdict(value: defaultdict = None, recurse: Callable[[Any], Any] = None) -> defaultdict:
      """Adapt a defaultdict by recursively processing its items."""
      return defaultdict(
         value.default_factory,
         {k: recurse(v) for k, v in value.items()}
      )
   
   def handle_chainmap(value: ChainMap = None, recurse: Callable[[Any], Any] = None) -> ChainMap:
      """Adapt a ChainMap by merging all underlying mappings."""
      merged = {}
      for m in value.maps:
         merged.update({k: recurse(v) for k, v in m.items()})
      return dict(merged)

   register_adapter(defaultdict, handle_defaultdict)
   register_adapter(ChainMap, handle_chainmap)

_register_builtin_adapters()
