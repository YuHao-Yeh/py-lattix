from __future__ import annotations

__all__ = ["Lattix"]

from collections.abc import Iterable, Mapping, MutableMapping
from copy import deepcopy
import json
import sys
from threading import Lock, RLock
from typing import TYPE_CHECKING, TypeVar, cast


import logging
logger = logging.getLogger(__name__)


from .._core.abstract import MutableAbstractDict
from .._core.base import LattixNode
from .._core.mixins import ThreadingMixin, LogicalMixin, FormatterMixin

from ..adapters import construct_from_iterable

from ..utils.common import (
    deep_convert, 
    is_scalar, 
    scan_class_attrs, 
    serialize
)
from ..utils.exceptions import (
    # Import Exceptions
    NoPyYAMLError,
    # Payload Exceptions
    InvalidJSONTypeError, InvalidJSONValueError, InvalidYAMLValueError,
    NonPairIterableError, ArgTypeError,
    # Internal Access
    InvalidAttributeNameError, InternalAttributeError, 
    ReservedNameConflictError, MissingAttributeError,
    # Key Exceptions
    KeyPathError, KeyNotFoundError, PathNotFoundError, UnexpectedNodeTypeError,
    # Operators
    OperandTypeError,
)


if TYPE_CHECKING:
    from _thread import LockType, RLock as RLockType
    from collections.abc import Callable
    from typing import Any, SupportsIndex
    from ..utils.types import (
       DictType, ListType, SetType, TupleType, TypeType,
       ClassAttrSet, GenericAlias, JOIN_METHOD, MERGE_METHOD
    )
    
_S = TypeVar("_S")
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")




_sentinel = object()


class Lattix(
    MutableAbstractDict[_KT, _VT], 
    LattixNode, 
    ThreadingMixin, 
    LogicalMixin, 
    FormatterMixin, 
):
    __slots__ = (
        "_sep", "_lazy_create", "_ts_level", 
        "_lock", "_rlock", "_detached"
    )
    # ========== Class-level constants ==========
    __INTERNAL_ATTRS__: ClassAttrSet = {
        "_lazy_create", "_sep", "_ts_level", "_lock", "_rlock", 
        '_detached',
    }
    __CLASS_ATTRS__: ClassAttrSet | None = None

    # ========== Constructors & Classmethods ==========
    def __init__(
        self, 
        data: Any = None, 
        *, 
        key: str = "", 
        parent: Any = None, 
        sep: str = "/", 
        lazy_create: bool = False, 
        ts_level: int = 0, 
        **kwargs: Any
    ):
        object.__setattr__(self, "_sep", sep)
        object.__setattr__(self, "_lazy_create", lazy_create)
        # threading slots
        object.__setattr__(self, "_ts_level", 0)
        object.__setattr__(self, "_lock", None)
        object.__setattr__(self, "_rlock", None)
        object.__setattr__(self, "_detached", True)
        
        LattixNode.__init__(self, key, parent)
        self._init_threading(parent, ts_level)
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[DD:INIT] Lattix key={key}, "
                f"parent={hex(id(parent)) if parent else None}, "
                f"data={type(data).__name__}"
            )
        
        if data:
            self.update(data)
        
        if kwargs:
            self.update(kwargs)
        
        _ = self._get_class_attrs()

    def __new__(cls, *args: Any, **kwargs: Any):
        return super().__new__(cls)

    def _config(self):
        return self._sep, self._lazy_create, self._ts_level
    
    @classmethod
    def _construct(
        cls, 
        mapping: Any, 
        config: TupleType[str, Any, str, bool, int] = ("", None, "/", False, 0),
        /,
        **kwargs: Any,
    ):
        key, parent, sep, lazy_create, ts_level = config
        return cls(mapping, key=key, parent=parent, sep=sep, 
                   lazy_create=lazy_create, ts_level=ts_level, **kwargs)

    def __getstate__(self) -> DictType[str, str | int | DictType[str, _VT] | None]:
        return {
            "key" : self._key,
            "data" : dict(self._children),   # shallow copy
            "lazy" : self._lazy_create,
            "sep" : self._sep,
            "thread" : self._ts_level,
        }
    
    def __setstate__(self, state: DictType[str, Any]):
        super().__setattr__("_lazy_create", state["lazy"])
        super().__setattr__("_sep", state["sep"])

        LattixNode.__init__(self, state["key"], None)
        ThreadingMixin._init_threading(self, None, state["thread"])
        self.update(state["data"])

    def __reduce__(self):
        return (self.__class__, (), self.__getstate__())

    def __reduce_ex__(self, protocol: SupportsIndex, /):
        return self.__reduce__()
    
    @classmethod
    def __class_getitem__(cls, item: Any):
        """Support type hint syntax like Lattix[str, int]."""
        return GenericAlias(cls, item)  # type: ignore[name-defined]

    @classmethod
    def fromkeys(cls, iterable: Iterable[_T], value: Any = None):
        """Create a new Lattix from an iterable of keys with the same value."""
        return cls({key: value for key in iterable})

    @classmethod
    def from_dict(cls, d: DictType[_KT, _VT], sep: str = "/"):
        """Create a Lattix from an existing dictionary."""
        return cls(d, sep = sep)

    @classmethod
    def from_json(
        cls, 
        data: str | bytes, 
        encoding: str = "utf-8", 
        *, 
        from_file: bool = False
    ):
        def convert(obj: Any) -> Any:
            if isinstance(obj, dict):
                map_obj = cast(Mapping[_KT, _VT], obj)
                return cls({key: convert(v) for key, v in map_obj.items()})
            elif isinstance(obj, list):
                return [convert(v) for v in cast(ListType[Any], obj)]
            return obj

        try:
            if from_file:
                with open(data, "r", encoding=encoding) as f:
                    parsed = json.load(f)
            elif isinstance(data, bytes):
                parsed = json.loads(data.decode(encoding))
            elif isinstance(data, str):
                parsed = json.loads(data)
            elif isinstance(data, dict):
                return convert(data)
            else:
                raise InvalidJSONTypeError(data)
        except InvalidJSONTypeError:
            raise
        except Exception as e:
            raise InvalidJSONValueError(data) from e

        return convert(parsed)

    @classmethod
    def from_yaml(
        cls, 
        data: str | bytes, 
        encoding: str = "utf-8", 
        *, 
        from_file: bool = False, 
        enhanced: bool = False,
    ):
        from ..serialization import yaml_safe_load
        from ..utils.compat import yaml

        def convert(obj: Any) -> Any:
            if isinstance(obj, dict):
                return cls({key: convert(v) for key, v in cast(DictType[_KT, _VT], obj).items()})
            elif isinstance(obj, list):
                return [convert(v) for v in cast(ListType[Any], obj)]
            elif isinstance(obj, tuple):
                return tuple(convert(v) for v in cast(TupleType[Any], obj))
            elif isinstance(obj, set):
                return set(convert(v) for v in cast(SetType[Any], obj))
            return obj

        try:
            if from_file:
                with open(data, "r", encoding=encoding) as f:
                    raw = f.read()
            elif isinstance(data, bytes):
                raw = data.decode(encoding)
            else:
                raw = data
            
            if enhanced:
                parsed = yaml_safe_load(raw)
            else:
                parsed = yaml.safe_load(raw)
        except Exception as e:
            raise InvalidYAMLValueError(data) from e

        return convert(parsed)

    @classmethod
    def _get_class_attrs(cls):
        if cls.__CLASS_ATTRS__ is None:
            cls.__CLASS_ATTRS__ = scan_class_attrs(cls)
        return cls.__CLASS_ATTRS__   

    # ========== Properties ==========
    @property
    def sep(self) -> str:
        return self._sep
    
    @sep.setter
    def sep(self, symbol: str):
        object.__setattr__(self, "_sep", symbol)

        # cascade
        # for child in self._children.values():
        #     if isinstance(child, Lattix):
        #         child.sep = symbol
        self._propagate_attrs(self, {"_sep": symbol})

    @property
    def lazy_create(self) -> bool:
        return self._lazy_create
    
    @lazy_create.setter
    def lazy_create(self, value: bool):
        # object.__setattr__(self, "_lazy_create", value)
        
        # cascade
        # for child in self._children.values():
        #     if isinstance(child, Lattix):
        #         child.lazy_create = value
        self._propagate_attrs(self, {"_lazy_create": value})

    # ========== Internal helpers ==========
    def _promote_child(self, key: str, value: Any, parent_node: Any):
        cfg = (key, None) + parent_node._config()
        new_node = parent_node._construct(value, cfg)
        new_node.transplant(parent_node, key)
        parent_node._children[key] = new_node
        return new_node
    
    def _walk_path(self, path: str, stop_before_last: bool = False) -> TupleType[Lattix[_KT, _VT], _KT] | Any:
        """
        Internal helper for traversing a hierarchical path.

        Parameters
        ----------
        path : str
            Path string (e.g., "a/b/c").
        sep : str, optional
            Path separator; defaults to self._sep.
        stop_before_last : bool, default False
            If True, stop before the last key and return (node, last_key).
        create_missing : bool, default False
            Whether to auto-create missing intermediate Lattix nodes.

        Returns
        -------
        Tuple[Lattix, Any] or Any
            - If stop_before_last=True: returns (parent_node, last_key).
            - If stop_before_last=False: returns the final resolved object value.
        """
        node, sep = self, self._sep
        cls = type(node)

        create_missing = node.lazy_create

        if (sep not in path) and (not create_missing):
            if stop_before_last:
                return node, path
            keys = [path]
            parents_lst, last_key = [], path
        else:
            keys = path.split(sep)
            parents_lst, last_key = keys[:-1], keys[-1]

            # 1. Traverse up to the parent of the target
            for key in parents_lst:
                if key not in node._children:
                    if create_missing:
                        val = node._promote_child(key, None, node)
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"[DD:PATH] created '{key}' during traversal of {path}")
                    else:
                        logger.warning(f"[DD:PATH] not found: '{key}' in {path}")
                        raise PathNotFoundError(key, path)
                else:
                    val = node._children[key]
                
                if isinstance(val, cls):
                    node = val
                elif isinstance(val, Mapping):
                    node = node._promote_child(key, val, node)
                else:
                    raise UnexpectedNodeTypeError(key, val)

            # 2. Return based on mode
            if stop_before_last:
                return node, last_key
           
        # 3. Final Step for stop_before_last=False (Full Retrieval)
        if last_key not in node._children:
            if create_missing:
                return node._promote_child(last_key, None, node)
            logger.warning(f"[DD:PATH] not found: '{last_key}' in {path}")
            raise PathNotFoundError(last_key, path)
        
        val = node._children[last_key]

        # Check if the final leaf needs promotion
        if isinstance(val, Mapping) and not isinstance(val, cls):
            val = node._promote_child(last_key, val, node)

        return val

        """``Deprecated Method``
        node, val = self, None
        sep = node._sep
        keys = path.split(sep)
        cls = type(node)

        
        # Node config: (parent, sep, lazy_create, thread_safety)
        node_cfg = (node, sep, node.lazy_create, node.ts_level)
        create_missing |= node_cfg[2]

        # traversal
        for key in (keys[:-1] if stop_before_last else keys):
            cfg = (key, ) + node_cfg  # cfg: (key, parent, sep, lazy, ts)
            
            if key not in node._children:
                if create_missing:
                    node._children[key] = node._construct(None, cfg)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"[DD:PATH] created '{key}' during traversal of {path}")
                else:
                     logger.warning(f"[DD:PATH] not found: '{key}' in {path}")
                     raise PathNotFoundError(key, path)
               
            val = node._children[key]
            if isinstance(val, cls):
                node = val
            elif isinstance(val, Mapping):
                detached_cfg = (key, None) + node_cfg[1:]
                val = node._construct(val, detached_cfg)
                # Manually attach correct parent
                val.parent = node
                node._children[key] = val
                node = val
            elif stop_before_last:
                raise UnexpectedNodeTypeError(key, val)

        return (node, keys[-1]) if stop_before_last else val
        """
    
    @staticmethod
    def _convert_iterable(node: Lattix[_KT, _VT], key: str, iterable: Iterable[Any]):
        node_cfg = (None, ) + node._config()  # node cfg: (parent, sep, lazy, ts)
        res: ListType[Any] = []

        for idx, v in enumerate(iterable):
            if is_scalar(v):
                res.append(v)
            elif isinstance(v, Mapping):
                cfg = (str(idx), ) + node_cfg  # cfg: (key, parent, sep, lazy, ts)
                res.append(node._construct(v, cfg))
            elif isinstance(v, Iterable):
                res.append(node._convert_iterable(node, key, v))
            else:
                res.append(v)
        return construct_from_iterable(type(iterable), res)

    # ========== MutableMapping core (Mapping protocol / Basic dict-like) ==========
    def __getitem__(self, key: _KT):
        try:
            if isinstance(key, str):
                return self._walk_path(key, stop_before_last=False)
            return self._children[key]
        except UnexpectedNodeTypeError:
            raise
        except (PathNotFoundError, KeyError):
            raise KeyNotFoundError(str(key))
        
        """```Deprecated Method```
        node, last = self._walk_path(key, stop_before_last=True)
        if last not in node._children:
            logger.warning(f"[DD:GET] Missing key '{key}'")
            raise KeyNotFoundError(key)
        
        val = node._children.get(last)
        if isinstance(val, Lattix):
            return val
        elif isinstance(val, Mapping):
            cfg = (last, None) + node._config()
            val = node._construct(val, cfg)
            val.parent = node
            node._children[last] = val
            return val
        return val
        """

    def __setitem__(self, key: _KT, value: _VT):
        cls = type(self)

        if isinstance(key, str) and self._sep in key:
            node, last = self._walk_path(key, stop_before_last=True)
        else:
            node, last = self, key
        
        if last in node:
            old_child = node._children[last]
            if isinstance(old_child, cls):
                old_child.detach()

        if is_scalar(value):
            pass
        elif isinstance(value, cls):
            parent = value.parent
            if parent is None:
                value.transplant(node, last)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"[DD:SET] {key} = {type(copied_val).__name__}")
                return
            
            if parent is not node:
                copied_val = value.copy()
                copied_val.transplant(node, last)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"[DD:SET] {key} = {type(copied_val).__name__}")
                return
        elif isinstance(value, Mapping):
            _ = node._children.pop(last, None)
            value = node._construct(value, (last, node) + node._config())
        elif isinstance(value, Iterable):
            value = self._convert_iterable(node, last, value)
        
        node._children[last] = value

        if not isinstance(value, Mapping): 
            node._children[last] = value

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[DD:SET] {key} = {type(value).__name__}")

        """```Deprecated Method```
        if isinstance(key, str) and self._sep in key:
            node, last = self._walk_path(key, stop_before_last=True, create_missing=True)
            node[last] = value
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[DD:SET] Path {key} = {type(value).__name__}")
            return
        else:
            node, last = self, key

        children = self._children
        if isinstance(value, Lattix):
            if value.parent is None or value.parent is not self:
                value.parent = self
            children[key] = value
        elif isinstance(value, Mapping):
            cfg = (key, self) + self._config()
            children[key] = self._construct(value, cfg)
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            children[key] = self._convert_iterable(self, key, value)
        else:
            children[key] = value
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[DD:SET] {key} = {type(value).__name__}")
        """

    def __delitem__(self, key):
        if isinstance(key, str) and self._sep in key:
            try:
                node, last = self._walk_path(key, stop_before_last=True)
            except PathNotFoundError:
                raise KeyNotFoundError(key)
        else:
            node, last = self, key
        
        if last not in node._children:
            raise KeyNotFoundError(key)
        
        del node._children[last]

        """```Deprecated Method```
        if isinstance(key, str) and self._sep in key:
            node, last = self._walk_path(key, stop_before_last=True)
            if last not in node._children:
                raise KeyNotFoundError(key)
            del node._children[last]
        elif key not in self._children:
            raise KeyNotFoundError(key)
        else:
            del self._children[key]
        """

    def __iter__(self):
        """Return iterator over top-level keys."""
        return iter(self._children)

    def __len__(self):
        """Return the number of top-level items."""
        return len(self._children)

    def __contains__(self, key):
        if (not isinstance(key, str)) or (self._sep not in key):
            return key in self._children

        try:
            lazy_create = self._lazy_create
            object.__setattr__(self, "_lazy_create", False)
            node, key = self._walk_path(key, stop_before_last=True)
        except KeyPathError:
            return False
        else:
            return key in node._children
        finally:
            if lazy_create:
                object.__setattr__(self, "_lazy_create", lazy_create)
                # self._lazy_create = lazy_create
  
    def __reversed__(self):
        return reversed(list(self._children))

    def __eq__(self, other):
        if isinstance(other, Lattix):
            return dict(self) == dict(other)
        if isinstance(other, dict):
            return dict(self) == other
        return NotImplemented
    
    def keys(self):
        """Return all top-level keys (equivalent to dict.keys())."""
        return object.__getattribute__(self, "_children").keys()
    
    def values(self):
        """Return all top-level values (equivalent to dict.values())."""
        return object.__getattribute__(self, "_children").values()

    def items(self):
        """Return all top-level (key, value) pairs (equivalent to dict.items())."""
        return object.__getattribute__(self, "_children").items()

    def get(self, key: _KT, default: Lattix[_KT, _VT] | Any | None = None):
        """Return value for key if exists, else default."""
        try:
            lazy_create = self._lazy_create
            if isinstance(key, str):
                object.__setattr__(self, "_lazy_create", False)
                return self._walk_path(key, stop_before_last=False)
            return self._children[key]
        except (KeyPathError, KeyError):
            return default
        finally:
            if lazy_create:
                object.__setattr__(self, "_lazy_create", lazy_create)
        
        """```Deprecated Method```
        node, key = self._walk_path(key, stop_before_last=True)
        return object.__getattribute__(node, "_children").get(key, default)  # type: ignore
        """

    def setdefault(self, key, default=None):
        """Set default value if key not exists, wrapping dict as Lattix."""
        if key not in self:
            self[key] = default
        return self[key]

    def pop(self, key, default=_sentinel):
        """Remove a key and return its value (or default if not found)."""
        children = object.__getattribute__(self, "_children")
        if key in children:
            return children.pop(key)  # type: ignore
        if default is not _sentinel:
            return default
        raise KeyNotFoundError(key)

    def popitem(self):
        """Remove and return an arbitrary (key, value) pair."""
        return object.__getattribute__(self, "_children").popitem()

    def clear(self):
        """Remove all items."""
        self._children.clear()

    def update(self, other: Mapping[Any, _VT] | Iterable[TupleType[Any, _VT]] = (), **kwargs: Any):
        if isinstance(other, Mapping):
            map_obj = cast(Mapping[_KT, _VT], other)
            for key, val in list(map_obj.items()):
                self[key] = val
        elif isinstance(other, Iterable) and not is_scalar(other):
            for obj in other:
                if isinstance(obj, Mapping):
                    map_obj = cast(Mapping[_KT, _VT], other)
                    for key, val in list(map_obj.items()):
                        self[key] = val
                elif len(obj) == 2:
                    self[obj[0]] = obj[1]
                else:
                    raise NonPairIterableError("update", type(other).__name__)

            """```Deprecated Method```
            try:
                for key, v in other:
                    self[key] = v
            except ValueError:
                raise NonPairIterableError("update", type(other).__name__)
            """
        else:
            raise ArgTypeError("update", "other", "a mapping or iterable of pairs", type(other).__name__)
        
        for key, v in list(kwargs.items()):
            self[key] = v  # pyright: ignore

    def copy(self):
        """Return a shallow copy of self as Lattix."""
        return self.clone(deep=False, keep_state=True, share_lock=False)

    # ========== Attribute-style access ==========
    def __getattr__(self, name: str):
        # --- reserved internals ---
        internal = object.__getattribute__(self, "__INTERNAL_ATTRS__")
        if name in internal:
            # if name in children:
            #    raise ReservedNameConflictError(name)
            raise InternalAttributeError(name)

        # --- class attributes ---
        cls_attrs = self._get_class_attrs()
        if name in cls_attrs:
            return object.__getattribute__(self, name)

        # --- stored children ---
        children = object.__getattribute__(self, "_children")
        if name in children:
            return children[name]
        
        # --- lazy-create ---
        if object.__getattribute__(self, "_lazy_create"):
            cfg = (name, self) + self._config()
            children[name] = self._construct(None, cfg)
            return children[name]

        raise MissingAttributeError(name)

    def __setattr__(self, name: str, value: _VT):
        """Set attributes as if they were dictionary keys."""
        # --- reserved internals ---
        internal = object.__getattribute__(self, "__INTERNAL_ATTRS__")
        if name in internal:
            raise ReservedNameConflictError(name)
        
        # --- class attributes ---
        cls_attrs = self._get_class_attrs()
        if name in cls_attrs:
            return object.__setattr__(self, name, value)
        
        # --- name validation ---
        if not self._valid_name(name):
            raise InvalidAttributeNameError(name)
        
        children = object.__getattribute__(self, "_children")
        lazy_create = object.__getattribute__(self, "_lazy_create")

        # --- stored children ---
        if (name in children) or lazy_create:
            children[name] = value
            # self[name] = value # Route through __setitem__ for logic consistency
            return

        raise MissingAttributeError(name)

    def __delattr__(self, name: str):
        # --- name validation ---
        if name.startswith('__') and name.endswith('__'):
            raise InvalidAttributeNameError(name)

        # --- stored ---
        children = object.__getattribute__(self, "_children")
        if name in children:
            del children[name]
            return
        
        # --- class attributes ---
        else:
            object.__delattr__(self, name)
            # --- reserved internals ---
            self.__INTERNAL_ATTRS__.discard(name)
            if logger.isEnabledFor(logging.WARNING):
                logger.warning(f"[DD:DELATTR] Attr destroyed: '{name}'")
            return
       
    def __dir__(self):
        base_attrs = super().__dir__()
        key_attrs = [key for key in self._children.keys() if isinstance(key, str) and key.isidentifier()]
        return sorted(set(base_attrs + key_attrs))

    # ========== Comparison & Representation ==========
    def __repr__(self):
        """Developer-friendly representation."""
        return f"{type(self).__name__}({self._children!r})"

    def __str__(self):
        """User-friendly pretty string."""
        return self.pprint(colored=False, style="default")
    
    def __format__(self, format_spec: str):
        """
         Support formatted string output, e.g.:
            f"{d:pretty}"           → default style
            f"{d:json}"             → JSON style
            f"{d:yaml}"             → YAML style
            f"{d:repr}" / f"{d!r}"  → repr-style print
        """
        fmt = format_spec.lower().strip()
        if fmt in ("", "pretty", "default", "str"):
            return self.pprint(style="default")
        elif fmt in ("json", "yaml", "repr", "debug"):
            return self.pprint(style=fmt)
        else:
            raise ValueError(f"Unsupported format specifier: '{format_spec}'")

    def __pretty__(self, printer: Any, cycle: Any):
        """Pretty-printer integration (used by IPython, rich, etc.)."""
        if cycle:
            printer.text(f"{type(self).__name__}({{...}})")
            return

        # Use FormatterMixin pprint
        formatted = self.pprint(colored=False, compact=False, style="default")
        printer.text(formatted)

    # ========== Merge / Logical operators ==========
    # Basicly follow PEP 584; right value assignment
    # ===============================================
    # --- add (+) ---
    def __add__(self, other: Any):
        """Return a new Lattix merged with `other`."""
        d = self.copy()
        d.merge(other)
        return d

    def __iadd__(self, other: Any):
        """Merge `other` into self in-place (`+=`)."""
        self.merge(other)
        return self

    def merge(self, other: Mapping[_KT, _VT], overwrite: bool = True):
        if not isinstance(other, Mapping):
          raise ArgTypeError("merge", "other", "dict-like", type(other).__name__)
        
        cls = type(self)
        children = self._children
        for key, v in other.items():
            curr = children.get(key, None)
            if isinstance(curr, cls) and isinstance(v, Mapping):
                self[key].merge(v, overwrite)
            elif overwrite or (key not in children):
                if isinstance(v, cls):
                    self[key] = v.clone(True, True, False)
                else:
                    self[key] = v
        return self

    # --- and (&) / intersection ---
    def _set_operation(self, other: Mapping[_KT, _VT] | Any, op: str, inplace: bool = False):
        """
        Unified implementation for Set Operations.
        op: '&' (and), '|' (or), '-' (sub), '^' (xor)
        """

        L = Lattix

        # 1. Validation
        if not isinstance(other, Mapping):
            return self if inplace else self._construct(None, ('', None) + self._config())
        other = cast(Mapping[_KT, _VT], other)

        if op not in ("&", "|", "-", "^"):
            raise OperandTypeError(self, other, op)

        # 2. Setup Result (Clone or Inplace)
        result = self if inplace else self.clone(True, True, False)
        res_cfg = (result, ) + result._config()
        self_children = result._children
        other_children = other._children if isinstance(other, L) else other

        # 3. Determine Keys to Iterate
        # AND/SUB only need to look at keys in self.
        # OR/XOR need to look at keys in both (Union).
        if op in ("&", "-"):
            keys_to_iter = list(self_children.keys())
        else:   # "|", "^"
            keys_to_iter = list(self_children.keys()) + [k for k in other_children if k not in self_children]

        # 4. Define Logic Flags based on Op
        # (Should we keep keys only in Self? Only in Other? How to handle overlap?)
        keep_self_only  = op in ("|", "-", "^")  # OR, SUB, XOR keep unique self keys
        keep_other_only = op in ("|", "^")       # OR, XOR add unique other keys
        
        # Action on intersection: 'merge_or_overwrite' or 'merge_or_delete'
        # AND/OR -> Merge nested, otherwise overwrite with other.
        # SUB/XOR -> Merge nested, otherwise delete.
        is_pruning_op = op in ("-", "^") 

        delete_keys = []

        for key in keys_to_iter:
            v1 = self_children.get(key)
            v2 = other_children.get(key)

            in_self = v1 is not None
            in_other = v2 is not None

            # --- CASE 1: Intersection (In Both) ---
            if in_self and in_other:
                if isinstance(v1, Mapping) and isinstance(v2, Mapping):
                    # Recurse
                    dv1 = v1 if isinstance(v1, L) else result._construct(v1, (key, ) + res_cfg)
                    # Recursive call passing the same 'op'
                    sub_res = dv1._set_operation(v2, op=op, inplace=True)
                    
                    if is_pruning_op and not sub_res:
                        # For SUB/XOR, if the child becomes empty, remove the key
                        delete_keys.append(key)
                    else:
                        self_children[key] = sub_res
                else:
                    # Value collision (non-mapping)
                    if is_pruning_op:
                        # For SUB/XOR, values collision -> remove key
                        delete_keys.append(key)
                    else:
                        # For AND/OR, overwrite with v2
                        if isinstance(v2, L):
                            self_children[key] = v2.clone(True, True, False)
                        else:
                            self_children[key] = v2

            # --- CASE 2: Only in Self ---
            elif in_self:
                if not keep_self_only:
                    delete_keys.append(key)

            # --- CASE 3: Only in Other ---
            elif in_other:
                if keep_other_only:
                    if isinstance(v2, L):
                        self_children[key] = v2.clone(True, True, False)
                    else:
                        self_children[key] = v2

        # 5. Cleanup
        for key in delete_keys:
            del self_children[key]

        return result
    
    def _and_impl(self, other: Any, inplace: bool = False):
        return self._set_operation(other, op="&", inplace=inplace)

    # --- or (|) / union---
    def _or_impl(self, other: Any, inplace: bool = False):
        return self._set_operation(other, op="|", inplace=inplace)

    # --- sub (-) / difference---
    def _sub_impl(self, other: Any, inplace: bool = False):
        return self._set_operation(other, op="-", inplace=inplace)

    # --- xor (^) / symmetric difference---
    def _xor_impl(self, other: Any, inplace: bool = False):
        return self._set_operation(other, op="^", inplace=inplace)

    # --- join ---
    def join(self, other: Any, how: JOIN_METHOD = "inner", merge: MERGE_METHOD = "tuple"):
        """
        Join two Lattixs by key, similar to SQL joins.

        Args:
           how: {'inner', 'left', 'right', 'outer'}
              - 'inner' : keys in both self and other
              - 'left'  : all keys from self, fill None for missing in other
              - 'right' : all keys from other, fill None for missing in self
              - 'outer' : all keys from both
           merge: {'tuple', 'self', 'other', 'prefer_self', 'prefer_other'}
              - 'tuple'        : (self_val, other_val)
              - 'self'         : keep only self values
              - 'other'        : keep only other values
              - 'prefer_self'  : prefer self when both exist
              - 'prefer_other' : prefer other when both exist

        Example:
           >>> d1 = Lattix({"a": 1, "b": 2, "c": 3}) 
           >>> d2 = Lattix({"b": 20, "c": 30, "d": 40})

           - Inner join
           >>> d1.join(d2, how="inner")
           Lattix({'b': (2, 20), 'c': (3, 30)})

           - Left join
           >>> d1.join(d2, how="left")
           Lattix({'a': (1, None), 'b': (2, 20), 'c': (3, 30)})

           - Right join
           >>> d1.join(d2, how="right")
           Lattix({'b': (2, 20), 'c': (3, 30), 'd': (None, 40)})

           - Outer join
           >>> d1.join(d2, how="outer")
           Lattix({'a': (1, None), 'b': (2, 20), 'c': (3, 30), 'd': (None, 40)})
        """
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "join")

        cls = type(self) 
        self_children = self._children
        other_children = other._children if isinstance(other, cls) else other

        how = how.lower()
        merge = merge.lower()

        # === determine join keys ===
        if how == "inner":
            keys = [key for key in self_children if key in other_children]
        elif how == "left":
            keys = list(self_children)
        elif how == "right":
            keys = list(other_children)
        elif how == "outer":
            keys = list(self_children) + [key for key in other_children if key not in self_children]
        else:
            raise ValueError(f"Invalid join type: {how}")

        # === merge strategy dispatch table (avoid match inside loop) ===
        merge_fn : Callable[[Any, Any], Any]
        if merge == "tuple":
            merge_fn = lambda v1, v2: (v1, v2)
        elif merge == "self":
            merge_fn = lambda v1, v2: v1
        elif merge == "other":
            merge_fn = lambda v1, v2: v2
        elif merge == "prefer_self":
            merge_fn = lambda v1, v2: v1 if v1 is not None else v2
        elif merge == "prefer_other":
            merge_fn = lambda v1, v2: v2 if v2 is not None else v1
        else:
            raise ValueError(f"Invalid merge mode: {merge}")

        # === join loop ===
        result = {}
        for key in keys:
            v1 = self._children.get(key)
            v2 = other_children.get(key)

            if isinstance(v1, Mapping) and isinstance(v2, Mapping):
                dv1 = v1 if isinstance(v1, cls) else cls(v1)
                result[key] = dv1.join(v2, how=how, merge=merge)
            else:
                result[key] = merge_fn(v1, v2)

        return cls(result)

    # ========== Leaf / Traversal utilities ==========
    def get_path(self, path: str, default: Any = None):
        try:
            return self._walk_path(path, stop_before_last=False)
        except KeyError:
            return default

    def has_path(self, path: str) -> bool:
        try:
            self._walk_path(path, stop_before_last=False)
            return True
        except KeyError:
            return False

    def is_leaf(self, path: str):
        try:
            val = self._walk_path(path, stop_before_last=False)
            return not isinstance(val, Lattix)
        except KeyError:
            return False

    # ========== Serialization & Export ==========
    def to_dict(self) -> DictType[_KT, _VT]:
        # return {key: self.__deep_convert__(v) for key, v in self._children.items()}
        return {key: deep_convert(v) for key, v in self._children.items()}
    
    def to_list(self) -> ListType[TupleType[_KT, _VT]]:
        # return [[key, self.__deep_convert__(v, list)] for key, v in self._children.items()]
        return [[key, deep_convert(v, list)] for key, v in self._children.items()]
    
    def to_tuple(self):
        # return tuple([(key, self.__deep_convert__(v, tuple)) for key, v in self._children.items()])
        return tuple([(key, deep_convert(v, tuple)) for key, v in self._children.items()])

    def to_json(self, **kwargs: Any):
        import json
        # serializable = self._to_serializable(self)
        serializable = serialize(self)
        return json.dumps(serializable, **kwargs)

    def to_yaml(self, enhanced: bool = False, **kwargs: Any):
        from ..serialization import yaml_safe_dump
        from ..utils.compat import HAS_YAML, yaml

        if not HAS_YAML:
            raise NoPyYAMLError
        # serializable = self._to_serializable(self)
        serializable = serialize(self)

        if enhanced:
            return yaml_safe_dump(serializable, **kwargs)

        sort_keys = kwargs.pop("sort_keys", False)
        indent = kwargs.pop("indent", 2)
        default_flow_style = kwargs.pop("default_flow_style", False)

        return cast(str, yaml.safe_dump(
            serializable, 
            sort_keys=sort_keys, 
            indent=indent,
            default_flow_style=default_flow_style, 
            **kwargs
        )).rstrip() + "\n"

    # def __deep_convert__(self, value, ftype=dict, **kwargs):
    #     """Recursively convert Lattix and its children to a target type."""
    #     def _construct_from_items(items):
    #         """Inline helper for constructing containers safely."""
    #         if issubclass(ftype, Mapping):
    #             return construct_from_iterable(ftype, dict(items))
    #         elif issubclass(ftype, Iterable) and ftype not in (str, bytes):
    #             normalized = ([key, v] if ftype is list else tuple([key, v]) for key, v in items)
    #             built = construct_from_iterable(ftype, normalized)
    #             if (len(built) == 1) and \
    #                 isinstance(built[0], (ftype, list ,tuple)) and \
    #                 (len(built[0]) == 2):
    #                 return ftype(built[0])
    #             return built
    #         else:
    #             # return construct_from_iterable(ftype, (tuple(kv) for kv in items))
    #             return construct_from_iterable(list, items)

    #     if (adapter := get_adapter(value)):    # PEP 572
    #         return adapter(value, lambda v: self.__deep_convert__(v, ftype, **kwargs))
    #     elif isinstance(value, (str, bytes, bytearray)):
    #         return value
    #     # --- Mapping ---
    #     elif isinstance(value, Mapping):
    #         items = ((key, self.__deep_convert__(sub, ftype, **kwargs)) for key, sub in value.items())
    #         return _construct_from_items(items)
    #     # --- Iterable ---
    #     elif isinstance(value, Iterable):
    #         return construct_from_iterable(type(value), (self.__deep_convert__(v, ftype, **kwargs) for v in value))
    #     else:
    #         return value
    
    # def deep_convert(self, ftype=dict, **kwargs):
    #     """Public API: return a flattened copy of this Lattix"""
    #     return self.__deep_convert__(self, ftype=ftype, **kwargs)

    # def _to_serializable(self, obj, _seen=None):
    #     if _seen is None:
    #         _seen = set()
    #     oid = id(obj)
    #     if oid in _seen:
    #         return "<circular_ref>"
    #     _seen.add(oid)
       
    #     if isinstance(obj, Lattix):
    #         return {key: self._to_serializable(v, _seen) for key, v in obj._children.items()}
    #     elif isinstance(obj, Mapping):
    #         return {key: self._to_serializable(v, _seen) for key, v in obj.items()}
    #     elif isinstance(obj, (list, tuple)):
    #         return type(obj)(self._to_serializable(v, _seen) for v in obj)
    #     elif isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
    #         return [self._to_serializable(v, _seen) for v in obj]
    #     else:
    #         return obj

    # ========== Copy & Sort utilities ==========
    def __deepcopy__(self, memo: DictType[int, Any]):
        _id = id(self)
        if _id in memo:
            return memo[_id]
        return self.clone(deep=True, keep_state=True, memo=memo)
        
        """```Deprecated Method```
        pre-register to prevent re-entry
        memo[id(self)] = self
        new_copy = self.clone(deep = True, keep_state=True, memo=memo)
        memo[id(self)] = new_copy
        """

    def clone(
        self, 
        deep: bool = True, 
        keep_state: bool = True, 
        share_lock: bool = False, 
        memo: DictType[int, Any] | None = None
    ):
        cls = type(self)
        if memo is None:
            memo = {}

        self_id = id(self)
        if self_id in memo:
            return memo[self_id]

        if keep_state:
            sep = getattr(self, "_sep", "/")
            lazy = getattr(self, "_lazy_create", False)
            ts_level = getattr(self, "_ts_level", 0)

            if share_lock:
                lock = getattr(self, "_lock", None)
                rlock = getattr(self, "_rlock", None)
                is_detached = False
            else:
                lock = Lock() if ts_level == 1 else None
                rlock = RLock() if ts_level == 2 else None
                is_detached = True
        else:
            sep, lazy, ts_level = "/", False, 0
            lock, rlock = None, None
            is_detached = True

        def _copy_value(val: Any, parent_for_val: Any) -> Any:
            if isinstance(val, cls):
                return _reconstruct(val, parent_for_val)
            if is_scalar(val):
                return val
            if isinstance(val, Mapping):
                map_val = cast(MutableMapping[_KT, _VT], val)
                new_map: MutableMapping[_KT, _VT]
                try:
                    new_map = type(map_val)()
                except Exception:
                    new_map = {}
                for k, v in map_val.items():
                    new_map[k] = _copy_value(v, parent_for_val)
                return new_map
            if isinstance(val, Iterable):
                return construct_from_iterable(type(val), [_copy_value(x, parent_for_val) for x in val])
            return deepcopy(val, memo)

        # Main recursive constructor
        def _reconstruct(curr_node: LattixNode, new_parent: LattixNode | None) -> Lattix[_KT, _VT]:
            node_id = id(curr_node)
            if node_id in memo:
                return memo[node_id]

            new_key: str | None = getattr(curr_node, "_key", None)
            new_node = cls(None, key=new_key, parent=new_parent, sep=sep,
                           lazy_create=lazy, ts_level=ts_level)
            memo[node_id] = new_node

            object.__setattr__(new_node, "_lock", lock)
            object.__setattr__(new_node, "_rlock", rlock)
            object.__setattr__(new_node, "_detached", is_detached)

            old_children = getattr(curr_node, "_children", {})
            new_children = {}
            for k, v in old_children.items():
                new_children[k] = _copy_value(v, new_node)

            object.__setattr__(new_node, "_children", new_children)
            return new_node

        if not deep:
            key = getattr(self, "_key", None)
            new_root = cls(None, key=key, parent=None, sep=sep, 
                           lazy_create=lazy, ts_level=ts_level)
            memo[self_id] = new_root

            object.__setattr__(new_root, "_lock", lock)
            object.__setattr__(new_root, "_rlock", rlock)
            object.__setattr__(new_root, "_detached", is_detached)

            object.__setattr__(new_root, "_children", getattr(self, "_children", {}).copy())
            return new_root
        else:
            return _reconstruct(self, None)
        
        """```Deprecated Method```
        cls = type(self)

        try:
            cfg = self._config()
        except:
            cfg = ("/", False, 0)
        self_cfg = (self.key, None) + cfg
        new = self._construct(None, self_cfg)

        # --- backup locks ---
        self_lock = getattr(self, "_lock", None)
        self_rlock = getattr(self, "_rlock", None)
        ts_level = self_cfg[4]

        # ---- preserve or default state ----
        if not keep_state:
            ts_level = 0
            object.__setattr__(new, "_sep", "/")
            object.__setattr__(new, "_lazy_create", False)
            object.__setattr__(new, "_ts_level", ts_level)

        # --- recursively strip locks / parent pointers to avoid deepcopy hand ---
        _registry = {}  # object id -> (obj_ref, old_lock, old_rlock, old_parent)
        def _strip(obj, seen: set):
            oid = id(obj)
            if oid in seen:
                return
            seen.add(oid)

            if isinstance(obj, cls):
                _registry[oid] = (obj, getattr(obj, "_lock", None), 
                                  getattr(obj, "_rlock", None), 
                                  getattr(obj, "_parent", None))
                object.__setattr__(obj, "_parent", None)
                object.__setattr__(obj, "_lock", None)
                object.__setattr__(obj, "_rlock", None)
                for child in object.__getattribute__(obj, "_children").values():
                    _strip(child, seen)
            elif isinstance(obj, (str, bytes, bytearray)):
                return
            elif isinstance(obj, Mapping):
                for v in obj.values():
                    _strip(v, seen)
            elif isinstance(obj, Iterable):
                for v in obj:
                    _strip(v, seen)
        _strip(self, seen=set())
        
        children = object.__getattribute__(self, "_children")
        data = deepcopy(children, {}) if deep else children.copy()

        # ---- restore locks & parents on the original tree using registry ----
        for oid, (obj, old_lock, old_rlock, old_parent) in _registry.items():
            try:
                object.__setattr__(obj, "_lock", old_lock)
                object.__setattr__(obj, "_rlock", old_rlock)
                object.__setattr__(obj, "_parent", old_parent)
            except Exception:
                # best-effort restore: ignore if some object mutated meanwhile
                pass

        # ---- assign cloned children and basic node attrs ----
        def _rebuild_parents(node):
            children_map = getattr(node, "_children", {})
            if not isinstance(children_map, Mapping):
                return
            for key, v in children_map.items():
                if isinstance(v, cls):
                    # set child's key and parent weakref to node
                    object.__setattr__(v, "_key", key)
                    v.parent = node
                    _rebuild_parents(v)

        object.__setattr__(new, "_children", data)
        _rebuild_parents(new)
        
        if share_lock:
            new._propagate_lock(new, ts_level, self_lock, self_rlock, set())
        else:
            lock = Lock() if ts_level == 1 else None
            rlock = RLock() if ts_level == 2 else None
            new._propagate_lock(new, ts_level, lock, rlock, set())
        
        return new
        """

    def sort_by_key(self, reverse: bool = False, recursive: bool = False):
        sorted_items = sorted(self._children.items(), key=lambda x: x[0], reverse=reverse)
        object.__setattr__(self, "_children", dict(sorted_items))

        children = object.__getattribute__(self, "_children")
        if recursive:
            main_cfg = (self, ) + self._config()
            for key, v in children.items():
                cfg = (key, ) + main_cfg
                if isinstance(v, Mapping):
                    dv = v if isinstance(v, Lattix) else self._construct(v, cfg)
                    dv.sort_by_key(reverse=reverse, recursive=True)
                    children[key] = dv
        return self

    def sort_by_value(self, reverse: bool = False, recursive: bool = False):
        def safe_key(item):
            v = item[1]
            if isinstance(v, (int, float, str, bool, type(None))):
                return v
            return repr(v)

        sorted_items = sorted(self._children.items(), key=safe_key, reverse=reverse)
        object.__setattr__(self, "_children", dict(sorted_items))

        if recursive:
            main_cfg = (self, ) + self._config() 
            for key, v in self._children.items():
                cfg = (key, ) + main_cfg
                if isinstance(v, Mapping):
                    dv = v if isinstance(v, Lattix) else self._construct(v, cfg)
                    dv.sort_by_value(reverse=reverse, recursive=True)
                    self._children[key] = dv
        return self

    # ========== Lifecycle & Cleanup ==========
    @staticmethod
    def _propagate_attrs(
        obj: Any, 
        attrs: DictType[str, Any] = {}, 
        seen: SetType[int] | None = None
    ):
        if seen is None:
            seen = set()
        oid = id(obj)
        if oid in seen:
            return
        seen.add(oid)

        if isinstance(obj, Lattix):
            cast_obj = cast(Lattix[_KT, _VT], obj)
            for name, value in attrs.items():
                object.__setattr__(cast_obj, name, value)
            for child in object.__getattribute__(cast_obj, "_children").values():
                Lattix._propagate_attrs(child, attrs, seen)
        elif is_scalar(obj):
            return
        elif isinstance(obj, Mapping):
            map_obj = cast(Mapping[_KT, _VT], obj)
            for v in map_obj.values():
                Lattix._propagate_attrs(v, attrs, seen)
        elif isinstance(obj, Iterable):
            iter_obj = cast(Iterable[Any], obj)
            for v in iter_obj:
                Lattix._propagate_attrs(v, attrs, seen)

    @staticmethod
    def _propagate_lock(
        obj: Any, 
        level: int, 
        lock: LockType | None, 
        rlock: RLockType | None, 
        seen: SetType[int] | None = None
    ):
        if seen is None:
            seen = set()
        oid = id(obj)
        if oid in seen:
            return
        seen.add(oid)

        if isinstance(obj, ThreadingMixin):
            object.__setattr__(obj, "_ts_level", level)
            object.__setattr__(obj, "_lock", lock)
            object.__setattr__(obj, "_rlock", rlock)
            # object.__setattr__(obj, "_detached", (lock is None and rlock is None))

        if hasattr(obj, "_children") and isinstance(obj._children, dict):  # pyright: ignore
        # if isinstance(obj, LattixNode):
            for child in obj._children.values():
                Lattix._propagate_lock(child, level, lock, rlock, seen)
        elif is_scalar(obj):
            return
        elif isinstance(obj, Mapping):
            for v in obj.values():
                Lattix._propagate_lock(v, level, lock, rlock, seen)
        elif isinstance(obj, Iterable):
            for v in obj:
                Lattix._propagate_lock(v, level, lock, rlock, seen)

    def detach(self, clear_locks: bool = False):
        self.detach_thread(clear_locks)
        LattixNode.detach(self)
        self._propagate_lock(self, self._ts_level, 
                             self._lock, self._rlock)
    
    def attach(self, parent: Any):
        # 包裝一個tey，統一catch比較好？
        self.attach_thread(parent)
        LattixNode.attach(self, parent)
        self._propagate_lock(self, self._ts_level, 
                             self._lock, self._rlock)
    
    def transplant(self, parent: Any, key: _KT | None = None):
        # 包裝一個tey，統一catch比較好？
        # 如果parent是None怎麼辦？throw error?
        self.transplant_thread(parent)
        LattixNode.transplant(self, parent, key)
        self._propagate_lock(self, self._ts_level, 
                             self._lock, self._rlock)


    def __del__(self):
        try:
            if sys.is_finalizing():
                return
            if not getattr(self, "_detached", True):
                if logger.isEnabledFor(logging.WARNING):
                    logger.warning(f"[DD:DEL] Undetached Lattix destroyed: {getattr(self, '_key', '?')!r}")
        except:
            pass


def dict_union(a: MutableMapping[_KT, _VT], b: MutableMapping[_KT, _VT]) -> Any:  # pragma: no cover
    if isinstance(a, dict) and isinstance(b, Lattix):
        return type(b).__class__(a) | b
    elif isinstance(a, Lattix) and isinstance(b, dict):
        return a | type(a).__class__(b)
    else:
        return a | b   # pyright: ignore


if __name__ == "__main__":
    import doctest
    doctest.testmod()
    
    # print(Lattix.__annotations__)
    # print(Lattix().__getstate__())
    # print(dir(Lattix()))
    import numpy as np
    import pandas as pd
    from collections import deque, defaultdict
    d = Lattix(
        a = 1,
        b = {"x": 10, "y": {"z": 20}},
        c = [1, 2, {"x": {"y": {"z": 3}}}],
        d = {10, 11, 12},
        e = (4, 5, 6),
        f = tuple(("one",)),
        g = np.array([2, 3, 4]),
        h = pd.Series([x for x in range(7)]),
        i = pd.DataFrame({"first": [1, 2, 3], "second": (5, 6, 7)}),
        k = deque([9, 8, 7, 6, 5]),
    )
    # result = d.deep_convert(list)
    # print(result)

    # print(d)
    print(d.pprint(compact=True))
    print(d.pprint(compact=False))
    # print(d.__class__)
    # print(type(d).__name__)

    L = Lattix
    # print("=== Lattix MRO ===")
    # for c in L.__mro__:
    #     slots = getattr(c, "__slots__", None)
    #     has_dict = False
    #     # 判斷該類別的 instances 是否會有 __dict__
    #     if "__dict__" in (slots if isinstance(slots, (list, tuple)) else (slots or ())):
    #         has_dict = True
    #     # 也可檢查類別 dict 本身是否保有 __dict__ 屬性
    #     print(f"{c!r:60} | __slots__ = {slots!r:30} | has '__dict__' in slots? {has_dict}")

    # print("\n=== Check if any base is builtin heap type (like dict) ===")
    # for c in cls.__mro__:
    #     print(c, "is builtin type subclass of dict?", issubclass(c, dict) if inspect.isclass(c) else "n/a")

    # print("\n=== Show attrs related to __dict__ presence ===")
    # for c in cls.__mro__:
    #     print(c.__name__, "->", "has __dict__ attribute?", "__dict__" in c.__dict__)
    # from pprint import pprint
    # for c in cls.__mro__:
    #     pprint(f"{c.__name__}, {c.__dict__}")
    
    # print(dir(cls))
    # print(cls().__dict__)
    # print(cls.__slots__)

    # d = Lattix({"a": {"b": {"c": 123}}})
    # d = Lattix(ts_level=1)
    # print("----------")
    # d["a/b/c"] = 123
    # print("----------")
    # print(d.pprint(colored=True, compact=False))
    # print("----------")
    # print([n.parent for n in d.traverse("preorder")])
    # print("----------")
    # print("a", d.is_leaf("a"))
    # print("a/", d.is_leaf("a/"))
    # print("a/b", d.is_leaf("a/b"))
    # print("a/b/", d.is_leaf("a/b/"))
    # print("a/b/c", d.is_leaf("a/b/c"))
    # print("a/b/c/", d.is_leaf("a/b/c/"))
    # print("a/b/c/d", d.is_leaf("a/b/c/d"))
    # print()
    # print("a", d.has_path("a"))
    # print("a/", d.has_path("a/"))
    # print("a/b", d.has_path("a/b"))
    # print("a/b/", d.has_path("a/b/"))
    # print("a/b/c", d.has_path("a/b/c"))
    # print("a/b/c/", d.has_path("a/b/c/"))
    # print("a/b/c/d", d.has_path("a/b/c/d"))
    # print()
    # print(list(d.leaf_keys()))
    # print(list(d.leaf_values()))
    # print(d.__INTERNAL_ATTRS__)
    # print(d.__dict__)
    # print(d.__slots__)
   