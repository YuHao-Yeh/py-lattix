"""Lattix Hierarchical Mapping Structure.

This module provides the primary user-facing class, `Lattix`, which implements
a high-performance, hierarchical dictionary with support for dot-notation,
compound path keys, and thread-safe subtree locking.

The Lattix class integrates several core behaviors through a mixin architecture:
    - Hierarchical Node Logic: Parent-child relationships and tree traversal.
    - Threading Mixin: Lock-sharing mechanism where children inherit parent locks.
    - Logical Mixin: Deep merging and set-like operators (|, &, -, ^).
    - Formatter Mixin: Multi-style pretty printing (JSON, YAML, Default).

Example:
    Basic usage with path and dot access:

    >>> from lattix.structures.mapping import Lattix
    >>> d = Lattix(lazy_create=True)
    >>> d["app/settings/theme"] = "dark"
    >>> print(d.app.settings.theme)
    dark
    >>> d.to_dict()
    {'app': {'settings': {'theme': 'dark'}}}

    Thread-safe subtree modification:

    >>> d = Lattix(lazy_create=True, enable_lock=True)
    >>> with d:
    ...     d.user.profile.id = 101
    ...     # Entire tree is locked during this block

Classes:
    Lattix: The main hierarchical mapping class.
"""

from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from threading import RLock
from typing import TYPE_CHECKING, Any, ClassVar, Iterable, Mapping, TypeVar, Union, cast

from ..adapters import construct_from_iterable
from ..core.base import LattixNode
from ..core.interfaces import MutableLattixMapping
from ..core.meta import LattixMeta
from ..core.mixins import FormatterMixin, LogicalMixin, ThreadingMixin
from ..utils import compat
from ..utils.constant import DFLT_INDENT_WIDTH, DFLT_SEP
from ..utils.exceptions import (
    ArgTypeError,
    AttributeAccessDeniedError,
    AttributeNotFoundError,
    InvalidAttributeNameError,
    InvalidPayloadError,
    KeyNotFoundError,
    KeyPathError,
    ModificationDeniedError,
    NodeError,
    OperandTypeError,
    OptionalImportError,
    PathNotFoundError,
    PayloadError,
    UnexpectedNodeError,
    UnsupportedOperatorError,
    UnsupportedPayloadError,
)
from ..utils.inspection import is_primitive, is_scalar, scan_class_attrs
from ..utils.path import split_path
from ..utils.transform import deep_convert, serialize
from ..utils.types import Dict, GenericAlias, List, Set, Tuple

if TYPE_CHECKING:
    from _thread import RLock as RLockType
    from collections.abc import Callable
    from typing import Any, SupportsIndex

    from ..utils.types import (
        JOIN_METHOD,
        MERGE_METHOD,
        ClassAttrSet,
    )

__all__ = ["Lattix"]

_T = TypeVar("_T")
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")

_sentinel = object()
logger = logging.getLogger(__name__)
LattixValue = Union[_VT, "Lattix[_KT, _VT]"]


class Lattix(
    MutableLattixMapping[_KT, _VT],
    LattixNode[_KT, _VT],
    ThreadingMixin,
    LogicalMixin,
    FormatterMixin,
    metaclass=LattixMeta,
):
    """A hierarchical, thread-safe, and observable mapping structure.

    Lattix combines the flexibility of a dictionary with tree-like properties,
    allowing access via dot-notation, path-strings (e.g., 'a/b/c'), or iterables.
    It supports deep merging, logical set operations, and native integration
    with common data science libraries.

    Attributes:
        sep (str): The symbol used to separate keys in path strings.
        lazy_create (bool): If True, missing intermediate nodes are created
            automatically during access or assignment.
    """

    __slots__ = (
        "_sep",
        "_lazy_create",
        "_locking_enabled",
        "_lock",
        "_detached",
        "_frozen",
    )

    # ========== Class-level constants ==========
    __INTERNAL_ATTRS__: ClassVar[ClassAttrSet] = frozenset(
        {"_sep", "_lazy_create", "_locking_enabled", "_lock", "_detached", "_frozen"}
    )
    __CLASS_ATTRS__: ClassVar[ClassAttrSet] | None = None

    # ========== Constructors & Classmethods ==========
    def __init__(
        self,
        data: Any = None,
        *,
        key: str = "",
        parent: Any = None,
        sep: str = DFLT_SEP,
        lazy_create: bool = False,
        enable_lock: bool = False,
        frozen: bool = False,
        **kwargs: Any,
    ):
        """Initializes a Lattix node.

        Args:
            data (Any, optional): Initial mapping or iterable to populate the node.
            key (str, optional): The key associated with this node in the parent.
            parent (Lattix, optional): The parent node in the hierarchy.
            sep (str, optional): The path separator. Defaults to `DFLT_SEP`.
            lazy_create (bool, optional): Auto-create missing nodes. Defaults to False.
            enable_lock (bool, optional): Enable thread-safe lock sharing for this
                subtree. Defaults to False.
            **kwargs: Additional key-value pairs to insert.
        """
        self_set = object.__setattr__
        self_set(self, "_sep", sep)
        self_set(self, "_lazy_create", lazy_create)
        self_set(self, "_frozen", frozen)

        # --- inlined ThreadingMixin init ---
        self_set(self, "_locking_enabled", False)
        self_set(self, "_lock", None)
        self_set(self, "_detached", True)

        # --- inlined LattixNode init ---
        self_set(self, "_key", key)
        self_set(self, "_children", {})
        self_set(self, "_parent", None)

        self._init_threading(parent, enable_lock)
        if parent is not None:
            LattixNode.attach(self, parent)

        if data:
            if isinstance(data, Mapping):
                for k, v in data.items():
                    self._fast_set(k, v)
            else:
                self.update(data)

        if kwargs:
            for k, v in kwargs.items():
                self._fast_set(k, v)

    def __init_subclass__(cls, **kwargs: Any):
        """Internal: Scans class attributes upon subclassing to update metadata caching."""
        super().__init_subclass__(**kwargs)
        cls.__CLASS_ATTRS__ = scan_class_attrs(cls)

    def __new__(cls, *args: Any, **kwargs: Any):
        """Internal: Standard object creation."""
        return super().__new__(cls)

    def _config(self):
        """Return the current configuration state of the node.

        Returns:
            tuple: (sep, lazy_create, locking_enabled).
        """
        return self._sep, self._lazy_create, self._locking_enabled

    @classmethod
    def _construct(
        cls,
        mapping: Any,
        config: tuple[str, Any, str, bool, bool] = ("", None, DFLT_SEP, False, False),
        /,
        **kwargs: Any,
    ):
        """Internal factory method used to create new nodes during tree operations.

        Args:
            mapping: The data for the new node.
            config: Metadata configuration (key, parent, sep, lazy, lock).
            **kwargs: Additional data to update.
        """
        key, parent, sep, lazy_create, enable_lock = config
        return cls(
            mapping,
            key=key,
            parent=parent,
            sep=sep,
            lazy_create=lazy_create,
            enable_lock=enable_lock,
            **kwargs,
        )

    def __getstate__(self):
        """Internal: Prepares the node state for pickling."""
        return {
            "key": self._key,
            "data": dict(self._children),  # shallow copy
            "lazy": self._lazy_create,
            "sep": self._sep,
            "enable_lock": self._locking_enabled,
            "frozen": self._frozen,
        }

    def __setstate__(self, state: dict[str, Any], /):
        """Internal: Restores the node state from a pickle."""
        super().__setattr__("_lazy_create", state["lazy"])
        super().__setattr__("_sep", state["sep"])
        super().__setattr__("_frozen", state["frozen"])

        LattixNode.__init__(self, state["key"], None)
        ThreadingMixin._init_threading(self, None, state["enable_lock"])
        self.update(state["data"])

    def __reduce__(self):
        """Internal: Helper for pickle protocol."""
        return (self.__class__, (), self.__getstate__())

    def __reduce_ex__(self, protocol: SupportsIndex, /):
        """Internal: Helper for pickle protocol."""
        return self.__reduce__()

    @classmethod
    def __class_getitem__(cls, item: Any, /):
        """Support for Generic Type Aliases (e.g., Lattix[str, int])."""
        return GenericAlias(cls, item)  # type: ignore[name-defined]

    @classmethod
    def fromkeys(cls, iterable: Iterable[_T], value: Any = None, /):
        """Create a new Lattix from an iterable of keys with the same value.

        Args:
            iterable (Iterable): Sequence of keys.
            value (Any, optional): Default value for all keys.

        Returns:
            Lattix: A new instance populated with the keys.
        """
        return cls({key: value for key in iterable})

    @classmethod
    def from_dict(cls, d: dict[_KT, _VT], sep: str = DFLT_SEP):
        """Create a Lattix from an existing dictionary."""
        return cls(d, sep=sep)

    @classmethod
    def from_json(
        cls, data: str | bytes, encoding: str = "utf-8", *, from_file: bool = False
    ):
        """Create a Lattix instance from JSON data.

        Args:
            data (str | bytes): JSON string, bytes, or a file path.
            encoding (str, optional): Text encoding. Defaults to "utf-8".
            from_file (bool, optional): If True, treats `data` as a path to a file.

        Returns:
            Lattix: A tree structure populated from the JSON.

        Example:
            >>> Lattix.from_json('{"a": {"b": 1}}')
            Lattix({'a': Lattix({'b': 1})})
        """

        def convert(obj: Any) -> Any:
            if isinstance(obj, dict):
                map_obj = cast(Mapping[_KT, _VT], obj)
                return cls({key: convert(v) for key, v in map_obj.items()})
            elif isinstance(obj, list):
                return [convert(v) for v in cast(List[Any], obj)]
            return obj

        try:
            if from_file:
                with open(data, encoding=encoding) as f:
                    parsed = json.load(f)
            elif isinstance(data, (bytes, bytearray)):
                parsed = json.loads(data.decode(encoding))
            elif isinstance(data, str):
                parsed = json.loads(data)
            elif isinstance(data, dict):
                return convert(data)
            else:
                raise UnsupportedPayloadError(
                    func="from_json", value=data, ideal=(str, bytes, bytearray, dict)
                )
        except PayloadError:
            raise
        except Exception as e:
            raise InvalidPayloadError(data, "JSON") from e

        return convert(parsed)

    @classmethod
    def from_orjson(cls, data: str | bytes, /):
        """Create a Lattix instance from orjson-encoded bytes.

        Args:
            data (bytes): orjson encoded data.

        Returns:
            Lattix: Populated tree.

        Raises:
            OptionalImportError: If orjson is not installed.
        """
        if not compat.HAS_ORJSON:
            raise OptionalImportError("orjson", "JSON deserialization", "orjson")
        decoded = compat.orjson.loads(data)
        return cls(decoded)

    @classmethod
    def from_msgpack(cls, data: str | bytes, /):
        """Create a Lattix instance from MessagePack-encoded bytes.

        Args:
            data (bytes): MessagePack encoded data.

        Returns:
            Lattix: Populated tree.
        """
        if not compat.HAS_MSGPACK:
            raise OptionalImportError("MessagePack", "unpacking support", "msgpack")
        unpacked = compat.msgpack.unpackb(data, raw=False)
        return cls(unpacked)

    @classmethod
    def from_yaml(
        cls,
        data: str | bytes,
        encoding: str = "utf-8",
        *,
        from_file: bool = False,
        enhanced: bool = False,
    ):
        """Create a Lattix instance from YAML data.

        Args:
            data (str | bytes): YAML string, bytes, or a file path.
            encoding (str, optional): Text encoding. Defaults to "utf-8".
            from_file (bool, optional): If True, treats `data` as a file path.
            enhanced (bool, optional): If True, uses the EnhancedSafeLoader to
                reconstruct complex types like Path or Decimal.

        Returns:
            Lattix: A tree structure populated from the YAML.
        """

        def convert(obj: Any) -> Any:
            if isinstance(obj, dict):
                return cls(
                    {key: convert(v) for key, v in cast(Dict[_KT, _VT], obj).items()}
                )
            elif isinstance(obj, list):
                return [convert(v) for v in cast(List[Any], obj)]
            elif isinstance(obj, tuple):
                return tuple(convert(v) for v in cast(Tuple[Any], obj))
            elif isinstance(obj, set):
                return set(convert(v) for v in cast(Set[Any], obj))
            return obj

        if not compat.HAS_YAML:
            raise OptionalImportError("PyYAML", "YAML deserialization", "pyyaml")

        try:
            if from_file:
                with open(data, encoding=encoding) as f:
                    raw = f.read()
            elif isinstance(data, bytes):
                raw = data.decode(encoding)
            else:
                raw = data

            if enhanced:
                from ..serialization import yaml_safe_load

                parsed = yaml_safe_load(raw)
            else:
                parsed = compat.yaml.load(raw, Loader=compat.yaml.FullLoader)
        except Exception as e:
            raise InvalidPayloadError(data, "YAML") from e

        return convert(parsed)

    @classmethod
    def from_env(
        cls, prefix: str = "", sep: str = "__", lowercase: bool = True, **kwargs
    ) -> Lattix:
        """Create a Lattix instance from environment variables.

        Args:
            prefix (str, optional): Only load variables starting with this prefix.
            sep (str, optional): Separator in env keys to represent levels.
                Defaults to "__".
            lowercase (bool, optional): Whether to convert env keys to lowercase.
                Defaults to True.
            **kwargs: Configuration passed to the Lattix constructor.

        Returns:
            Lattix: A nested structure populated with environment data.
        """

        import os

        data = {}
        prefix_str = f"{prefix}{sep}" if prefix else ""

        for key, value in os.environ.items():
            if key.startswith(prefix_str):
                clean_key = key[len(prefix_str) :]
                if lowercase:
                    clean_key = clean_key.lower()
                # Convert double underscore (or sep) to path separator
                path_key = clean_key.replace(sep, DFLT_SEP)
                data[path_key] = value

        # Use path-access logic to build the tree
        inst = cls(lazy_create=True, **kwargs)
        for k, v in data.items():
            inst[k] = v
        return inst

    @classmethod
    def unflatten(cls, data: Mapping[str, Any], sep: str = DFLT_SEP, **kwargs: Any):
        """Create a nested Lattix from a flat dictionary of path-keys.

        Args:
            data (Mapping[str, Any]): Flat mapping like {'a/b': 1}.
            sep (str, optional): The path separator used in the keys.
                Defaults to DFLT_SEP.
            **kwargs: Configuration passed to the Lattix constructor.

        Returns:
            Lattix: A hierarchical Lattix instance.
        """
        from ..utils.transform import unflatten as _unflat

        return cls(_unflat(data, sep=sep), sep=sep, **kwargs)

    @classmethod
    def _get_class_attrs(cls, refresh: bool = False):
        """Internal: Retrieve or refreshes the cached set of class-level attributes."""
        if cls.__CLASS_ATTRS__ is None or refresh:
            cls.__CLASS_ATTRS__ = scan_class_attrs(cls)
        return cls.__CLASS_ATTRS__

    # ========== Properties ==========
    @property
    def sep(self) -> str:
        """str: The current path separator symbol (e.g., '/', '.').
        Changing this propagates to all children in the tree.
        """
        return self._sep

    @sep.setter
    def sep(self, symbol: str, /):
        self._propagate_attrs(self, {"_sep": symbol})

    @property
    def lazy_create(self) -> bool:
        """bool: If True, missing keys in a path will result in new Lattix nodes
        instead of raising a KeyError.
        """
        return self._lazy_create

    @lazy_create.setter
    def lazy_create(self, value: bool, /):
        self._propagate_attrs(self, {"_lazy_create": value})

    # ========== Internal helpers ==========
    def _fast_set(self, key: _KT, value: Any):
        """Internal: High-speed assignment bypassing path-splitting logic."""
        if is_scalar(value):
            self._children[key] = value
            return

        cls = type(self)

        # 1. Handle Node/Mapping promotion
        if type(value) is dict:
            final_val = cls(
                value,
                key=key,
                parent=self,
                sep=self._sep,
                lazy_create=self._lazy_create,
                enable_lock=self._locking_enabled,
            )
        elif type(value) is cls:
            if value.parent is None:
                value.transplant(self, key)
                return

            if value.parent is not self:
                final_val = value.copy()
                final_val.transplant(self, key)
                return

            final_val = value
        elif isinstance(value, Mapping):
            self.pop(key, None)
            final_val = cls(
                value,
                key=key,
                parent=self,
                sep=self._sep,
                lazy_create=self._lazy_create,
                enable_lock=self._locking_enabled,
            )
        elif isinstance(value, Iterable):
            final_val = self._convert_iterable(self, key, value)
        else:
            final_val = value

        self._children[key] = final_val

    def _promote_child(self, key: _KT, value: Any, parent_node: Lattix[_KT, _VT]):
        """Internal: Convert a raw mapping into a Lattix node and links it."""
        cfg = (key, None) + parent_node._config()
        new_node = parent_node._construct(value, cfg)
        new_node.transplant(parent_node, key)
        parent_node._children[key] = new_node
        return new_node

    def _walk_path(
        self,
        path: str | Iterable[Any] = "",
        stop_before_last: bool = False,
        force_no_create: bool = False,
    ) -> tuple[Lattix[_KT, _VT], _KT] | LattixValue[_KT, _VT]:
        """Internal helper to traverse the tree using a path.

        Args:
            path (str | Iterable[Any]): The path to follow. Can be a string
                separated by `self.sep` or an iterable of keys.
            stop_before_last (bool, optional): If True, returns the parent node
                and the final key. Defaults to False.
            force_no_create (bool, optional): If True, ignores `self.lazy_create`
                and raises errors on missing keys. Defaults to False.

        Returns:
            Any: The value at the end of the path, or a (node, last_key) tuple
                if `stop_before_last` is True.

        Raises:
            PathNotFoundError: If a key in the path does not exist and
                creation is disabled.
            UnexpectedNodeError: If a non-mapping is encountered mid-path.
        """

        node = self
        sep = self._sep
        cls = type(self)
        create_missing = False if force_no_create else self._lazy_create

        if isinstance(path, str):
            if (sep not in path) and (not create_missing):
                if stop_before_last:
                    return node, path
                keys = [path]
                ancestors, last_key = [], path
            else:
                keys = split_path(path, sep)
                ancestors, last_key = keys[:-1], keys[-1]
        else:
            keys = path
            ancestors, last_key = keys[:-1], keys[-1]

        # 1. Traverse up to the parent of the target
        for key in ancestors:
            try:
                val = node._children[key]
            except KeyError as e:
                if create_missing:
                    node = node._promote_child(key, None, node)
                    continue
                raise PathNotFoundError(key, path) from e

            if type(val) is cls:
                node = val
            elif isinstance(val, Mapping):
                node = node._promote_child(key, val, node)
            else:
                raise UnexpectedNodeError(key, val)

        # 2. Return based on mode
        if stop_before_last:
            return node, last_key

        # 3. Final Step for stop_before_last=False (Full Retrieval)
        try:
            val = node._children[last_key]
        except KeyError as e:
            if create_missing:
                return node._promote_child(last_key, None, node)
            raise PathNotFoundError(last_key, path) from e

        # Check if the final leaf needs promotion
        if isinstance(val, Mapping) and (type(val) is not cls):
            val = node._promote_child(last_key, val, node)

        return val

    @staticmethod
    def _convert_iterable(node: Lattix[_KT, _VT], key: str, iterable: Iterable[Any]):
        """Internal: Recursively ensure mappings inside iterables are promoted to Lattix."""
        node_cfg = (None,) + node._config()  # node cfg: (parent, sep, lazy, ts)
        res: list[Any] = []

        for idx, v in enumerate(iterable):
            if is_scalar(v):
                res.append(v)
            elif isinstance(v, Mapping):
                cfg = (str(idx),) + node_cfg  # cfg: (key, parent, sep, lazy, ts)
                res.append(node._construct(v, cfg))
            elif isinstance(v, Iterable):
                res.append(node._convert_iterable(node, key, v))
            else:
                res.append(v)
        return construct_from_iterable(type(iterable), res)

    # ========== MutableMapping core (Mapping protocol / Basic dict-like) ==========
    def __getitem__(self, key: _KT, /):
        """Retrieve an item by key or hierarchical path.

        If the key is a string containing the separator (e.g., 'a/b/c'),
        Lattix will traverse the tree to find the value.

        Args:
            key (_KT): A simple key, a path string, or a tuple/list of keys.

        Returns:
            Any: The value associated with the key or path.

        Example:
            >>> d = Lattix({"user": {"id": 1}})
            >>> d["user/id"]
            1
        """
        try:
            val = self._children[key]
        except (KeyError, TypeError):
            if (type(key) is str and self._sep in key) or isinstance(
                key, (list, tuple)
            ):
                return self._walk_path(key, stop_before_last=False)
            raise KeyNotFoundError(key) from None

        if isinstance(val, Mapping) and (type(val) is not type(self)):
            val = self._promote_child(key, val, self)
            self._children[key] = val
        return val

    def __setitem__(self, key: _KT, value: _VT, /):
        """Set an item by key or hierarchical path.

        Automatically handles node promotion (converting dicts to Lattix)
        and path traversal.

        Args:
            key (_KT): The key or path string where the value should be stored.
            value (_VT): The value to store.

        Example:
            >>> d = Lattix(lazy_create=True)
            >>> d["database/host"] = "localhost"
            >>> d.database.host
            'localhost'
        """
        cls = type(self)

        if getattr(self, "_frozen", False):
            raise ModificationDeniedError(cls)

        if isinstance(key, str) and (self._sep in key):
            node, last = self._walk_path(key, stop_before_last=True)
        else:
            node, last = self, key

        node_children = node._children
        # Detach logic
        if last in node:
            old = node_children[last]
            if type(old) is cls:
                old.detach()

        # Transformation logic
        if is_scalar(value):
            pass
        elif type(value) is cls:
            if value.parent is None:
                value.transplant(node, last)
                return

            if value.parent is not node:
                final_val = value.copy()
                final_val.transplant(node, last)
                return
        elif isinstance(value, Mapping):
            node_children.pop(last, None)
            value = cls(
                value,
                key=last,
                parent=node,
                sep=node._sep,
                lazy_create=node._lazy_create,
                enable_lock=node._locking_enabled,
            )
        elif isinstance(value, Iterable):
            value = self._convert_iterable(node, last, value)

        node_children[last] = value

    def __delitem__(self, key: _KT, /):
        """Remove a key or a path from the Lattix.

        Args:
            key (Any): The key or path string (e.g., 'a/b/c') to delete.

        Raises:
            KeyNotFoundError: If the key or any part of the path is missing.
        """
        if (isinstance(key, str) and self._sep in key) or isinstance(
            key, (list, tuple)
        ):
            try:
                node, last = self._walk_path(key, stop_before_last=True)
            except PathNotFoundError:
                raise KeyNotFoundError(key) from None
        else:
            node, last = self, key

        if last not in node._children:
            raise KeyNotFoundError(key)

        del node._children[last]

    def __iter__(self):
        """Return an iterator over the top-level keys."""
        return iter(self._children)

    def __len__(self):
        """Return the number of top-level items."""
        return len(self._children)

    def __contains__(self, key: object, /):
        """Check if a key or path exists in the Lattix.

        Args:
            key (Any): Key or path string.

        Returns:
            bool: True if found, False otherwise.
        """
        if key in self._children:
            return True

        if isinstance(key, str) and (self._sep in key):
            try:
                self._walk_path(key, force_no_create=True)
                return True
            except (KeyPathError, NodeError):
                return False

        return key in self._children

    def __reversed__(self):
        """Return a reversed iterator over the top-level keys."""
        return reversed(list(self._children))

    def __eq__(self, value: object, /):
        """Compare this Lattix with another mapping or Lattix."""
        if isinstance(value, Lattix):
            return dict(self) == dict(value)
        if isinstance(value, dict):
            return dict(self) == value
        return NotImplemented

    def keys(self):
        """Return a view of the top-level keys."""
        return self._children.keys()

    def values(self):
        """Return a view of the top-level values."""
        return self._children.values()

    def items(self):
        """Return a view of the top-level items."""
        return self._children.items()

    def get(self, key: _KT, default: Any = None, /):
        """Path-aware retrieval with a fallback default.

        Args:
            key (_KT): Key or path string.
            default (Any, optional): Value to return if key/path is missing.
        """
        # 1. Literal lookup
        try:
            return self._children[key]
        except KeyError:
            pass

        # 2. Path lookup
        if isinstance(key, str) and (self._sep in key):
            try:
                return self._walk_path(key, force_no_create=True)
            except (KeyPathError, KeyError):
                pass

        return default

    def setdefault(self, key: _KT, default: _VT = None, /):
        """Set default value if key not exists, else return value."""
        if key not in self:
            self.__setitem__(key, default)
        return self.__getitem__(key)

    def pop(self, key, default: _VT | _T = _sentinel, /):
        """Remove and return a top-level key's value (or default if not found)."""
        children = self._children
        if key in children:
            return children.pop(key)  # type: ignore
        if default is not _sentinel:
            return default
        raise KeyNotFoundError(key)

    def popitem(self):
        """Remove and return a (key, value) pair as a 2-tuple."""
        return self._children.popitem()

    def clear(self):
        """Remove all items from the current node."""
        self._children.clear()

    def update(self, other: Any = (), /, **kwargs: Any):
        """Update the Lattix with keys from another mapping or iterable."""
        if getattr(self, "_frozen", False):
            raise ModificationDeniedError(self.__class__)

        if isinstance(other, Mapping):
            for key, val in list(other.items()):
                self.__setitem__(key, val)
        elif hasattr(other, "__iter__") and not is_scalar(other):
            for obj in other:
                if len(obj) == 2:
                    self._fast_set(obj[0], obj[1])
                elif isinstance(obj, Mapping):
                    for key, val in list(obj.items()):
                        self.__setitem__(key, val)
                else:
                    raise ArgTypeError(
                        arg="other",
                        value=obj,
                        ideal_type="iterable of (key, value) pairs",
                        func="update",
                    )
        else:
            raise ArgTypeError(
                arg="other",
                value=other,
                ideal_type="a mapping or iterable of pairs",
                func="update",
            )

        if kwargs:
            for key, v in list(kwargs.items()):
                self.__setitem__(key, v)

    def copy(self):
        """Return a shallow copy of the Lattix."""
        return self.clone(deep=False, keep_state=True, share_lock=False)

    # ========== Attribute-style access ==========
    def __getattr__(self, name: str, /):
        """Retrieve a child node or value via dot-access.

        Args:
            name (str): The attribute name.

        Raises:
            AttributeNotFoundError: If key doesn't exist and lazy_create is False.
            AttributeAccessDeniedError: If accessing protected internal slots.
        """
        # --- stored children ---
        children = self._children
        try:
            val = children[name]
            if isinstance(val, Mapping) and (type(val) is not type(self)):
                val = self._promote_child(name, val, self)
                children[name] = val
            return val
        except KeyError:
            pass

        # --- lazy-create ---
        if self._lazy_create:
            cfg = (name, self) + self._config()
            children[name] = self._construct(None, cfg)
            return children[name]

        raise AttributeNotFoundError(name)

    def __setattr__(self, name: str, value: _VT, /):
        """Set a value via dot-access. Routes internally to __setitem__."""
        # --- reserved internals ---
        if name in self.__INTERNAL_ATTRS__:
            if name == "_frozen":
                return object.__setattr__(self, name, value)
            raise AttributeAccessDeniedError(
                name,
                cause=(
                    f"\n'{name}' is a reserved internal name; "
                    f"use d[{name!r}] instead of d.{name}"
                ),
            )

        if self._frozen:
            raise ModificationDeniedError(type(self))

        # --- class attributes ---
        if name in self._get_class_attrs():
            return object.__setattr__(self, name, value)

        # --- name validation ---
        if not self._valid_name(name):
            raise InvalidAttributeNameError(name)

        # --- stored children ---
        if (name in self._children) or self._lazy_create:
            # Route through __setitem__ for logic consistency
            self.__setitem__(name, value)
            return

        raise AttributeNotFoundError(name)

    def __delattr__(self, name: str, /):
        """Delete a child via dot-access."""
        # --- name validation ---
        if name.startswith("__") and name.endswith("__"):
            raise InvalidAttributeNameError(name)

        # --- stored ---
        children = self._children
        if name in children:
            del children[name]
            return

        # --- class attributes ---
        try:
            object.__delattr__(self, name)
            self.__INTERNAL_ATTRS__ -= {name}
            if self._get_class_attrs() is not None:
                self.__CLASS_ATTRS__ - {name}
        except AttributeError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}' "
                "(Class-level attributes cannot be deleted from instances)"
            ) from None

        if logger.isEnabledFor(logging.WARNING):
            logger.warning(f"[DD:DELATTR] Attr destroyed: '{name}'")

        return

    def __dir__(self):
        """Return a list of attributes including keys for autocompletion."""
        base_attrs = super().__dir__()
        key_attrs = [
            key
            for key in self._children.keys()
            if isinstance(key, str) and key.isidentifier()
        ]
        return sorted(set(base_attrs + key_attrs))

    # ========== Comparison & Representation ==========
    def __repr__(self):
        """Return a developer-friendly representation of the Lattix tree."""
        return f"{type(self).__name__}({self._children!r})"

    def __str__(self):
        """Return a pretty-printed string of the Lattix tree."""
        return self.pprint(colored=False, style="default")

    def __format__(self, format_spec: str, /):
        """Support formatted strings.

        Note:
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

    def _repr_pretty_(self, printer: Any, cycle: Any):
        """Integration with IPython/Rich pretty-printing."""
        name = type(self).__name__

        if cycle:
            printer.text(f"<Circular {name} at {hex(id(self))}>")
            return

        # Use FormatterMixin pprint
        try:
            formatted = self.pprint(colored=False, compact=False, style="default")
            printer.text(formatted)
        except Exception as e:
            printer.text(f"<{name} formatting error: {e}>")

    __pretty__ = _repr_pretty_

    # ========== Merge / Logical operators ==========
    # --- add (+) ---
    def __add__(self, other: Mapping[_KT, _VT], /):
        """Return a new Lattix merged with `other`."""
        d = self.copy()
        d.merge(other)
        return d

    def __iadd__(self, other: Mapping[_KT, _VT], /):
        """Merge `other` into self in-place (`+=`)."""
        self.merge(other)
        return self

    def merge(self, other: Mapping[_KT, _VT], overwrite: bool = True):
        """Recursively merge another mapping into this Lattix.

        Args:
            other (Mapping): The mapping to merge in.
            overwrite (bool, optional): Whether to overwrite existing leaf values.
                Defaults to True.

        Returns:
            Lattix: self (in-place modification).

        Raises:
            ArgTypeError: If `other` is not a Mapping.
        """
        if not isinstance(other, Mapping):
            raise ArgTypeError(
                arg="other", value=other, ideal_type="dict-like", func="merge"
            )

        cls = type(self)
        children = self._children
        for key, v in other.items():
            curr = children.get(key, None)
            if isinstance(curr, cls) and isinstance(v, Mapping):
                self.__getitem__(key).merge(v, overwrite)
            elif overwrite or (key not in children):
                if isinstance(v, cls):
                    self.__setitem__(key, v.clone(True, True, False))
                else:
                    self.__setitem__(key, v)
        return self

    # --- general function ---
    def _set_operation(
        self, other: Mapping[_KT, _VT] | Any, op: str, inplace: bool = False
    ):
        """Perform a deep logical set operation.

        Args:
            other (Mapping | Any): The operand to compare against.
            op (str): One of ('&', '|', '-', '^').
            inplace (bool, optional): Whether to modify the node in-place or
                return a clone. Defaults to False.

        Returns:
            Lattix: The result of the operation.

        Raises:
            UnsupportedOperatorError: If `op` is not recognized.
        """
        L = Lattix

        # 1. Validation
        other = cast(Mapping[_KT, _VT], other)

        if op not in ("&", "|", "-", "^"):
            raise UnsupportedOperatorError(op)

        # 2. Setup Result (Clone or Inplace)
        result = self if inplace else self.clone(True, True, False)
        res_cfg = (result,) + result._config()
        self_children = result._children
        other_children = other._children if isinstance(other, L) else other

        # 3. Determine Keys to Iterate
        # AND/SUB only need to look at keys in self.
        # OR/XOR need to look at keys in both (Union).
        if op in ("&", "-"):
            keys_to_iter = list(self_children.keys())
        else:  # "|", "^"
            keys_to_iter = list(self_children.keys()) + [
                k for k in other_children if k not in self_children
            ]

        # 4. Define Logic Flags based on Op
        keep_self_only = op in ("|", "-", "^")  # OR, SUB, XOR keep unique self keys
        is_pruning_op = op in ("-", "^")  # SUB, XOR -> Merge nested, otherwise delete
        # AND, OR -> Merge nested, otherwise overwrite with other.

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
                    dv1 = (
                        v1
                        if isinstance(v1, L)
                        else result._construct(v1, (key,) + res_cfg)
                    )
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
            else:
                # if keep_other_only:
                if isinstance(v2, L):
                    self_children[key] = v2.clone(True, True, False)
                else:
                    self_children[key] = v2

        # 5. Cleanup
        for key in delete_keys:
            del self_children[key]

        return result

    # --- and (&) / intersection ---
    def _and_impl(self, other: Any, inplace: bool = False):
        """Internal: Implementation of intersection."""
        return self._set_operation(other, op="&", inplace=inplace)

    # --- or (|) / union ---
    def _or_impl(self, other: Any, inplace: bool = False):
        """Internal: Implementation of union."""
        return self._set_operation(other, op="|", inplace=inplace)

    # --- sub (-) / difference ---
    def _sub_impl(self, other: Any, inplace: bool = False):
        """Internal: Implementation of difference."""
        return self._set_operation(other, op="-", inplace=inplace)

    # --- xor (^) / symmetric difference ---
    def _xor_impl(self, other: Any, inplace: bool = False):
        """Internal: Implementation of symmetric difference."""
        return self._set_operation(other, op="^", inplace=inplace)

    # --- join ---
    def join(
        self,
        other: Mapping[_KT, _VT],
        how: JOIN_METHOD = "inner",
        merge: MERGE_METHOD = "tuple",
    ):
        """Join two Lattix structures using SQL-style logic.

        Args:
            other (Any): The mapping to join with.
            how (str): Join strategy ('inner', 'left', 'right', 'outer').
            merge (str): Merge strategy for values ('tuple', 'self', 'other',
                'prefer_self', 'prefer_other').

        Returns:
            Lattix: A new Lattix instance containing joined results.

        Raises:
            OperandTypeError: If `other` is not a Mapping.
            ValueError: If `how` or `merge` are invalid strings.

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
            keys = list(self_children) + [
                key for key in other_children if key not in self_children
            ]
        else:
            raise ValueError(f"Invalid join type: {how}")

        # === merge strategy dispatch table (avoid match inside loop) ===
        merge_fn: Callable[[Any, Any], Any]
        if merge == "tuple":
            merge_fn = lambda v1, v2: (v1, v2)
        elif merge == "self":
            merge_fn = lambda v1, _: v1
        elif merge == "other":
            merge_fn = lambda _, v2: v2
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
    def get_path(
        self, path: str | List[_T] | Tuple[_T, ...] = "", default: _T = None, /
    ):
        """Safely retrieves a value at a specific path.

        Args:
            path (str | list | tuple): The path to the desired value.
            default (Any, optional): Value returned if the path is not found.

        Returns:
            Any: The value at the path or the default value.
        """
        try:
            return self._walk_path(path, stop_before_last=False)
        except KeyError:
            return default

    def has_path(self, path: str | List[_T] | Tuple[_T, ...] = "", /):
        """Check if a full path exists without creating missing nodes."""
        try:
            self._walk_path(path, stop_before_last=False)
            return True
        except KeyError:
            return False

    def is_leaf(self, path: str | List[_T] | Tuple[_T, ...] = "", /):
        """Check if the item at the path is a leaf (not another Lattix node)."""
        try:
            val = self._walk_path(path, stop_before_last=False)
            return not isinstance(val, Lattix)
        except KeyError:
            return False

    # ========== Serialization & Export ==========
    def to_dict(self):
        """Convert the Lattix into a nested dictionary.

        Returns:
            dict: A plain dictionary representation of the entire tree.

        Example:
            >>> d = Lattix({"a": {"b": 1}})
            >>> type(d.to_dict()["a"])
            <class 'dict'>
        """
        return {key: deep_convert(v) for key, v in self._children.items()}

    def to_list(self) -> list[tuple[_KT, _VT]]:
        """Convert the Lattix into a nested list of [key, value] pairs."""
        return [[key, deep_convert(v, list)] for key, v in self._children.items()]

    def to_tuple(self):
        """Convert the Lattix into a nested tuple of (key, value) pairs."""
        return tuple(
            [(key, deep_convert(v, tuple)) for key, v in self._children.items()]
        )

    def flatten(self, sep: str = DFLT_SEP):
        """Return a flat dictionary where keys are full path strings.

        Args:
            sep (str, optional): Separator used for the resulting keys.
                Defaults to self.sep.

        Returns:
            dict[str, Any]: A single-level dictionary of paths and values.

        Example:
            >>> d = Lattix({"app": {"theme": "dark", "ver": 1}})
            >>> d.flatten()
            {'app/theme': 'dark', 'app/ver': 1}
        """
        from ..utils.transform import flatten as _flat

        return _flat(self, sep=sep or self._sep)

    def json(self, **kwargs: Any):
        """Return a JSON string representation of the tree."""
        from ..serialization import to_json

        return to_json(self, **kwargs)

    def orjson(self, **kwargs: Any):
        """Return orjson-encoded bytes (faster than standard json)."""
        from ..serialization import to_orjson

        return to_orjson(self, **kwargs)

    def msgpack(self, **kwargs: Any):
        """Return MessagePack-encoded bytes."""
        from ..serialization import to_msgpack

        return to_msgpack(self, **kwargs)

    def yaml(self, enhanced: bool = False, **kwargs: Any):
        """Serializes the Lattix tree to a YAML string.

        Args:
            enhanced (bool, optional): If True, uses custom tags to preserve
                types like Decimal, Path, and datetime. Defaults to False.
            **kwargs: Arguments passed to the underlying YAML dumper.

        Returns:
            str: The YAML representation of the tree.

        Raises:
            OptionalImportError: If PyYAML is not installed.
        """
        if not compat.HAS_YAML:
            raise OptionalImportError(package="PyYAML", extra="pyyaml")

        serializable = serialize(self)

        kwargs.setdefault("default_flow_style", False)
        kwargs.setdefault("indent", DFLT_INDENT_WIDTH)
        kwargs.setdefault("allow_unicode", True)
        kwargs.setdefault("sort_keys", False)

        if enhanced:
            from ..serialization import yaml_safe_dump

            return yaml_safe_dump(serializable, **kwargs)

        return (
            cast(
                str,
                compat.yaml.safe_dump(serializable, **kwargs),
            ).rstrip()
            + "\n"
        )

    # ========== Copy & Sort utilities ==========
    def __copy__(self):
        """Support for the `copy.copy()` protocol."""
        return self.copy()

    def __deepcopy__(self, memo: dict[int, Any], /):
        """Support for the `copy.deepcopy()` protocol."""
        return self.clone(deep=True, keep_state=True, memo=memo)

    def clone(
        self,
        deep: bool = True,
        keep_state: bool = True,
        share_lock: bool = False,
        memo: dict[int, Any] | None = None,
    ):
        """Create a copy of the Lattix node and its subtree.

        Args:
            deep (bool, optional): Whether to perform a deep copy of values.
                Defaults to True.
            keep_state (bool, optional): Whether to copy settings like `sep`
                and `lazy_create`. Defaults to True.
            share_lock (bool, optional): If True, the clone will share the
                parent's RLock instance. Defaults to False.
            memo (dict, optional): Internal memo dictionary for deepcopy cycles.

        Returns:
            Lattix: The cloned node.
        """
        cls = type(self)
        if memo is None:
            memo = {}

        self_id = id(self)
        if self_id in memo:
            return memo[self_id]

        if keep_state:
            sep = getattr(self, "_sep", DFLT_SEP)
            lazy = getattr(self, "_lazy_create", False)
            enable_lock = getattr(self, "_locking_enabled", False)

            if share_lock:
                lock = getattr(self, "_lock", None)
                is_detached = False
            else:
                lock = RLock() if enable_lock else None
                is_detached = True
        else:
            sep, lazy = DFLT_SEP, False
            enable_lock = False
            lock = None
            is_detached = True

        obj_set = object.__setattr__

        def _copy_value(val: Any, parent_for_val: Any) -> Any:
            if type(val) is cls:
                return _reconstruct(val, parent_for_val)
            if is_primitive(val):
                return val
            return deepcopy(val, memo)

        # Main recursive constructor
        def _reconstruct(
            curr_node: LattixNode, new_parent: LattixNode | None
        ) -> Lattix[_KT, _VT]:
            node_id = id(curr_node)
            if node_id in memo:
                return memo[node_id]

            new_key: str | None = getattr(curr_node, "_key", "")
            new_node = cls(
                None,
                key=new_key,
                parent=new_parent,
                sep=sep,
                lazy_create=lazy,
                enable_lock=enable_lock,
            )
            memo[node_id] = new_node

            obj_set(new_node, "_lock", lock)
            obj_set(new_node, "_detached", is_detached)

            oldren = getattr(curr_node, "_children", {})
            new_children = {k: _copy_value(v, new_node) for k, v in oldren.items()}

            obj_set(new_node, "_children", new_children)
            return new_node

        if not deep:
            key = getattr(self, "_key", None)
            new_root = cls(
                None,
                key=key,
                parent=None,
                sep=sep,
                lazy_create=lazy,
                enable_lock=enable_lock,
            )
            memo[self_id] = new_root

            obj_set(new_root, "_lock", lock)
            obj_set(new_root, "_detached", is_detached)
            obj_set(new_root, "_children", getattr(self, "_children", {}).copy())
            return new_root
        else:
            return _reconstruct(self, None)

    def sort_by_key(self, reverse: bool = False, recursive: bool = False):
        """Sort the children of this node by their keys.

        Args:
            reverse (bool): Whether to sort in descending order.
            recursive (bool): Whether to sort all descendant subtrees.
        """
        sorted_items = sorted(
            self._children.items(), key=lambda x: x[0], reverse=reverse
        )
        children = self._children = dict(sorted_items)

        if recursive:
            main_cfg = (self,) + self._config()
            for key, v in children.items():
                cfg = (key,) + main_cfg
                if isinstance(v, Mapping):
                    dv = v if isinstance(v, Lattix) else self._construct(v, cfg)
                    dv.sort_by_key(reverse=reverse, recursive=True)
                    children[key] = dv
        return self

    def sort_by_value(self, reverse: bool = False, recursive: bool = False):
        """Sort the children of this node by their values."""

        def safe_key(item):
            v = item[1]
            if isinstance(v, (int, float)):
                return (0, v)
            if isinstance(v, str):
                return (1, v)
            return (2, repr(v))

        sorted_items = sorted(self._children.items(), key=safe_key, reverse=reverse)
        children = self._children = dict(sorted_items)

        if recursive:
            main_cfg = (self,) + self._config()
            for key, v in children.items():
                cfg = (key,) + main_cfg
                if isinstance(v, Mapping):
                    dv = v if isinstance(v, Lattix) else self._construct(v, cfg)
                    dv.sort_by_value(reverse=reverse, recursive=True)
                    children[key] = dv
        return self

    # ========== Lifecycle & Cleanup ==========
    @staticmethod
    def _propagate_attrs(
        obj: Any,
        attrs: dict[str, Any],
        seen: set[int] | None = None,
    ):
        """Internal: Recursively apply settings like 'sep' to the entire subtree."""
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
        enable_lock: bool,
        lock: RLockType | None,
        seen: set[int] | None = None,
    ):
        """Internal: Recursively share a lock instance across the entire subtree."""
        if seen is None:
            seen = set()
        oid = id(obj)
        if oid in seen:
            return
        seen.add(oid)

        if isinstance(obj, ThreadingMixin):
            obj_set = object.__setattr__
            obj_set(obj, "_locking_enabled", enable_lock)
            obj_set(obj, "_lock", lock)
            obj_set(obj, "_detached", lock is None)

        if children := getattr(obj, "_children", {}):
            for child in children.values():
                Lattix._propagate_lock(child, enable_lock, lock, seen)
        elif is_scalar(obj):
            return
        elif isinstance(obj, Mapping):
            for v in obj.values():
                Lattix._propagate_lock(v, enable_lock, lock, seen)
        elif isinstance(obj, Iterable):
            for v in obj:
                Lattix._propagate_lock(v, enable_lock, lock, seen)

    def freeze(self):
        """Recursively freeze the node and all children to prevent modification.

        Raises:
            ModificationDeniedError: If an attempt is made to change a frozen node.
        """
        self._propagate_attrs(self, {"_frozen": True})

    def unfreeze(self):
        """Recursively unfreeze the node and all children."""
        self._propagate_attrs(self, {"_frozen": False})

    def detach(self, clear_locks: bool = False):
        """Detach the node from its parent and re-initializes its lock context.

        Args:
            clear_locks (bool, optional): If True, disables locking on the
                detached subtree. Defaults to False.
        """
        self.detach_thread(clear_locks)
        LattixNode.detach(self)
        self._propagate_lock(self, self._locking_enabled, self._lock)

    def attach(self, parent: Any):
        """Attach the current node to a parent and inherits its lock context."""
        self.attach_thread(parent)
        LattixNode.attach(self, parent)
        self._propagate_lock(self, self._locking_enabled, self._lock)

    def transplant(self, parent: Any, key: str = ""):
        """Move the current node to a new parent, updating its internal path key."""
        self.transplant_thread(parent)
        LattixNode.transplant(self, parent, key)
        self._propagate_lock(self, self._locking_enabled, self._lock)

    def __del__(self):
        """Clean up internal children references upon destruction."""
        try:
            if sys.is_finalizing():
                return

            if (self.parent is not None) and not self._detached:
                logger.debug(
                    f"[DD:DEL] Undetached Lattix destroyed: {getattr(self, '_key', '?')!r}"
                )

            self._children = {}
        except Exception:
            pass
