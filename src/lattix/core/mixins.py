"""Core mixins for Lattix structural components.

This module provides specialized mixins that inject functional breadth into
Lattix structural classes. By using a mixin-based architecture, Lattix
separates specialized concerns—such as thread synchronization, logical
set-like operations, and multi-format pretty-printing—from the core
hierarchical mapping logic.

The mixins included in this module are:
    * :class:`ThreadingMixin`: Implements a lock-inheritance model where
      subtrees share a recursive lock with their parent, ensuring atomic
      operations across hierarchical boundaries.
    * :class:`LogicalMixin`: Defines the framework for deep set-like operations
      (intersection, union, difference, and symmetric difference) applied
      to mapping keys.
    * :class:`FormatterMixin`: Provides a flexible pretty-printing system with
      support for default tree views, JSON, YAML, and repr styles, including
      specialized handling for NumPy and Pandas objects.

These mixins are designed to be "plug-and-play" and rely on the concrete
implementing class to provide structural traversal logic where necessary.

Mixins:
    ThreadingMixin: Provides shared recursive locking for subtrees.
    LogicalMixin: Provides operator-based set logic for mappings.
    FormatterMixin: Provides extensible, multi-style object representation.
"""

from __future__ import annotations

import json
import logging
import pprint
import textwrap
from abc import abstractmethod
from collections.abc import Iterable, Mapping
from itertools import cycle
from threading import RLock
from typing import TYPE_CHECKING, Any, cast

from ..utils import compat
from ..utils.constant import DFLT_INDENT_OFFSET, DFLT_INDENT_WIDTH
from ..utils.exceptions import (
    ArgTypeError,
    LockExistenceError,
    OperandTypeError,
    OptionalImportError,
    UnattachableError,
)
from ..utils.transform import is_primitive, serialize

if TYPE_CHECKING:
    import sys
    from _thread import RLock as RLockType
    from types import TracebackType

    from ..utils.types import StyleHandler, StyleRegistry

    if sys.version_info >= (3, 11):
        from typing import Self  # Python 3.11+
    else:
        from typing_extensions import Self

__all__ = ["ThreadingMixin", "LogicalMixin", "FormatterMixin"]

logger = logging.getLogger(__name__)


class ThreadingMixin:
    """Mixin providing thread-safety configuration and lock inheritance.

    This mixin allows hierarchical structures to share a single recursive lock
    (RLock) across an entire tree or subtree. When a node is attached to a
    parent, it inherits the parent's lock reference. This ensures that locking
    the root node effectively synchronizes access to all its descendants.

    Attributes:
        _locking_enabled: Whether thread synchronization is active for this node.
        _lock: The RLock instance shared across the hierarchy.
        _detached: Boolean indicating if the node is independent of a parent's lock.
    """

    __slots__ = ()

    # ========== Internal attribute ==========
    _locking_enabled: bool
    _lock: RLockType | None
    _detached: bool

    # ========== Init ==========
    def _init_threading(
        self, parent: ThreadingMixin | None = None, enable_lock: bool = False
    ):
        """Initialize the threading context for the node.

        Args:
            parent: An optional parent node to inherit a lock from.
            enable_lock: Whether to create a new lock if no parent is provided.
                Defaults to False.
        """
        self._validate_bool(enable_lock)

        if parent is not None:
            # inherit parent's locks
            self.attach_thread(parent)
        else:
            # create new locks
            self_set = object.__setattr__
            self_set(self, "_locking_enabled", enable_lock)
            self_set(self, "_lock", RLock() if enable_lock else None)
            self_set(self, "_detached", True)

    # ========== Lock behavior ==========
    @property
    def locking_enabled(self):
        """bool: Returns whether locking is currently enabled for this node."""
        return getattr(self, "_locking_enabled", False)

    @locking_enabled.setter
    def locking_enabled(self, enable: bool):
        """Enable or disable locking for the entire subtree.

        Args:
            enable: True to activate a new RLock, False to disable.
        """
        self._validate_bool(enable)

        if enable:
            self._propagate_lock(self, True, RLock())
        else:
            self._propagate_lock(self, False, None)

    # ========== Validation ==========
    @staticmethod
    def _validate_bool(value: Any):
        """Validates that a value is a boolean.

        Args:
            value: The value to validate.

        Raises:
            ArgTypeError: If the value is not a boolean.
        """
        if type(value) is not bool:
            raise ArgTypeError(arg="enable_locking", value=value, ideal_type=bool)

    @staticmethod
    def _validate_parent(parent: Any):
        """Validate that the parent supports threading operations.

        Args:
            parent: The object to validate.

        Returns:
            bool: True if valid.

        Raises:
            ArgTypeError: If parent does not inherit from ThreadingMixin.
        """
        if not isinstance(parent, ThreadingMixin):
            raise ArgTypeError(arg="parent", value=parent, ideal_type=ThreadingMixin)
        return True

    @staticmethod
    def _validate_attachable(obj: ThreadingMixin):
        """Check if a node is in a state that allows it to adopt a new lock.

        Args:
            obj: The node to check.

        Returns:
            bool: True if attachable.

        Raises:
            UnattachableError: If the node is already attached to another hierarchy.
            LockExistenceError: If the node already possesses its own active lock.
        """
        if not getattr(obj, "_detached", True):
            raise UnattachableError
        if getattr(obj, "_lock", None):
            raise LockExistenceError
        return True

    # ========== Lifecycle ==========
    @staticmethod
    @abstractmethod
    def _propagate_lock(
        obj: Any,
        enable_lock: bool,
        lock: RLockType | None,
        seen: set[int] | None = None,
    ) -> None:
        """Recursively propagate a lock reference through a hierarchy.

        This method must be implemented by the concrete container class to
        traverse its specific child structures.

        Args:
            obj: The starting node for propagation.
            enable_lock: The target state for _locking_enabled.
            lock: The RLock instance to share.
            seen: A set of object IDs to prevent infinite loops in cycled trees.
        """
        raise NotImplementedError

    def propagate_lock(
        self,
        enable_lock: bool,
        lock: RLockType | None,
        seen: set[int] | None = None,
    ):
        """Instance wrapper for the static _propagate_lock method."""
        self._propagate_lock(self, enable_lock, lock, seen)

    def detach_thread(self, clear_locks: bool = False):
        """Makes this node (and its subtree) thread-independent.

        This breaks the lock-sharing link with the parent and creates a
        new independent RLock for this node.

        Args:
            clear_locks: If True, disables locking entirely for this node.
                If False, creates a new independent RLock. Defaults to False.
        """
        if clear_locks:
            enabled = False
        else:
            enabled = getattr(self, "_locking_enabled", False)

        obj_set = object.__setattr__
        obj_set(self, "_locking_enabled", enabled)
        obj_set(self, "_lock", RLock() if enabled else None)
        obj_set(self, "_detached", True)

    def attach_thread(self, parent: Any):
        """Adopts the lock configuration of a parent node.

        Args:
            parent: The ThreadingMixin node to inherit from.
        """
        self._validate_parent(parent)
        self._validate_attachable(self)

        obj_set = object.__setattr__
        obj_set(self, "_locking_enabled", parent._locking_enabled)
        obj_set(self, "_lock", parent._lock)
        obj_set(self, "_detached", False)

    def transplant_thread(self, parent: Any):
        """Forces adoption of a parent's lock, regardless of current state.

        Unlike attach_thread, this does not check if the node is already
        detached; it simply overwrites the lock reference.

        Args:
            parent: The ThreadingMixin node to inherit from.
        """
        self._validate_parent(parent)

        obj_set = object.__setattr__
        obj_set(self, "_locking_enabled", parent._locking_enabled)
        obj_set(self, "_lock", parent._lock)
        obj_set(self, "_detached", False)

    # ========== Context manager ==========
    def __enter__(self):
        """Acquires the shared recursive lock for context management.

        Returns:
            self: The current instance.
        """
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        """Releases the shared recursive lock."""
        self.release()

    # ========== Lock operations ==========
    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Acquires the shared RLock.

        Args:
            blocking: Whether to wait for the lock to be available.
                Defaults to True.
            timeout: Maximum time to wait in seconds. Defaults to -1 (infinite).

        Returns:
            bool: True if the lock was acquired, False otherwise.
        """
        if self._lock:
            return self._lock.acquire(blocking, timeout)
        return False

    def release(self):
        """Releases the shared RLock.

        Raises:
            RuntimeError: If the current thread does not own the lock.
        """
        if self._lock:
            self._lock.release()

    # ========== Representation ==========
    def _describe_lock(self) -> str:
        """Return a string describing the current lock state and ID.

        Returns:
            str: Debugging information about the RLock instance.
        """
        return str(
            f"lock={hex(id(self._lock)) if self._lock else None} "
            f"enabled={self._locking_enabled}"
        )


class LogicalMixin:
    """Abstract mixin providing logical (set-like) operations for mapping objects.

    This mixin defines logical operators (`&`, `|`, `-`, `^`) for mappings. These
    operators behave analogously to Python's built-in ``set`` operations but are
    applied to mapping keys rather than values.

    Each operator delegates its logic to a corresponding internal implementation
    method (e.g., `__and__` calls `_and_impl`). This allows for both new instance
    creation and in-place mutation (e.g., `&=` calls `_and_impl` with
    ``inplace=True``).

    Note:
        Subclasses must implement all four internal implementation methods
        (`_and_impl`, `_or_impl`, `_sub_impl`, and `_xor_impl`) to fully enable
        the logical operator suite.

    Attributes:
        None (Mixin uses __slots__ = ()).

    Supported Operators:
        & (Intersection): Returns keys present in both mappings.
        | (Union): Returns keys present in either mapping (merging values).
        - (Difference): Returns keys present in the first but not the second.
        ^ (Symmetric Difference): Returns keys present in either, but not both.

    Example:
        >>> class MyDict(LogicalMixin, dict):
        ...     def _construct(self, data):
        ...         return MyDict(data)
        ...     def _and_impl(self, other, inplace=False):
        ...         result = {k: self[k] for k in self if k in other}
        ...         if inplace:
        ...             self.clear()
        ...             self.update(result)
        ...             return self
        ...         return MyDict(result)
        ...     # ... other impls ...
        ...
        >>> d1 = MyDict({"a": 1, "b": 2})
        >>> d2 = MyDict({"b": 99, "c": 3})
        >>> d1 & d2
        {'b': 2}
    """

    __slots__ = ()

    # ========== Constructors & Classmethods ==========
    @classmethod
    @abstractmethod
    def _construct(cls, data: Any, config: Any = None, /, **kwargs: Any) -> Self:
        raise NotImplementedError

    # ========== AND (&) ==========
    def __and__(self, other: Any, /):
        """Return the intersection (`&`) of this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._and_impl(other, inplace=False)

    def __rand__(self, other: Any, /):
        """Right-hand fallback for ``Mapping & LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._and_impl(self, inplace=False)

    def __iand__(self, other: Any, /):
        """In-place intersection (``&=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "&=")
        return self._and_impl(other, inplace=True)

    @abstractmethod
    def _and_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of intersection logic."""
        pass

    def and_(self, other: Any, /):
        """Functional equivalent of the ``&`` operator."""
        return self._and_impl(other)

    # ========== OR (|) ==========
    def __or__(self, other: Any, /):
        """Return the union (``|``) of this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._or_impl(other, inplace=False)

    def __ror__(self, other: Any, /):
        """Right-hand fallback for ``Mapping | LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._or_impl(self, inplace=False)

    def __ior__(self, other: Any, /):
        """In-place union (``|=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "|=")
        return self._or_impl(other, inplace=True)

    @abstractmethod
    def _or_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of union logic."""
        pass

    def or_(self, other: Any, /):
        """Functional equivalent of the ``|`` operator."""
        return self._or_impl(other)

    # ========== SUB (-) ==========
    def __sub__(self, other: Any, /):
        """Return the difference (``-``) between this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._sub_impl(other, inplace=False)

    def __rsub__(self, other: Any, /):
        """Right-hand fallback for ``Mapping - LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._sub_impl(self, inplace=False)

    def __isub__(self, other: Any, /):
        """In-place difference (``-=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "-=")
        return self._sub_impl(other, inplace=True)

    @abstractmethod
    def _sub_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of difference logic."""
        pass

    def sub(self, other: Any, /):
        """Functional equivalent of the ``-`` operator."""
        return self._sub_impl(other)

    # ========== XOR (^) ==========
    def __xor__(self, other: Any, /):
        """Return the symmetric difference (``^``) of this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._xor_impl(other, inplace=False)

    def __rxor__(self, other: Any, /):
        """Right-hand fallback for ``Mapping ^ LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._xor_impl(self, inplace=False)

    def __ixor__(self, other: Any, /):
        """In-place symmetric difference (``^=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "^=")
        return self._xor_impl(other, inplace=True)

    @abstractmethod
    def _xor_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of symmetric difference logic."""
        pass

    def xor(self, other: Any, /):
        """Functional equivalent of the ``^`` operator."""
        return self._xor_impl(other)


class FormatterMixin:
    """Mixin providing flexible, multi-style pretty-printing support.

    This mixin provides a unified interface for converting hierarchical structures
    into human-readable strings. It supports multiple built-in formats and
    allows for the registration of custom formatting handlers.

    Built-in Styles:
        default: A recursive, indented, and optionally colored tree-like display.
            Includes special handling for NumPy arrays and Pandas DataFrames.
        json: Standard JSON-formatted string (via the internal serializer).
        yaml: YAML-formatted string (requires PyYAML).
        repr: Standard Python string representation (via pprint.pformat).

    Attributes:
        _STYLE_HANDLERS (StyleRegistry): A class-level registry mapping style
            names to their respective handler functions.
    """

    __slots__ = ()

    # ========== Internal attribute ==========
    _STYLE_HANDLERS: StyleRegistry = {}

    # ========== Style Registration ==========
    @classmethod
    def register_style(cls, name: str, func: StyleHandler):
        """Registers a new pretty-print style handler.

        Args:
            name: The lookup name for the style (e.g., 'table' or 'xml').
                Case-insensitive.
            func: A callable that accepts the object to print and formatting
                keyword arguments, returning a string.
        """
        cls._STYLE_HANDLERS[name.lower()] = func

    # ========== Public API ==========
    def pprint(
        self,
        indent: int = DFLT_INDENT_OFFSET,
        colored: bool = False,
        compact: bool = True,
        style: str = "default",
        **kwargs: Any,
    ) -> str:
        """Pretty-print the instance in the specified style.

        Args:
            indent: The base number of spaces for indentation.
                Defaults to `DFLT_INDENT_OFFSET`.
            colored: Whether to use ANSI color codes in the output.
                Supported by the 'default' style. Defaults to False.
            compact: Whether to prefer single-line output for small collections.
                Defaults to True.
            style: The name of the style handler to use. Defaults to "default".
            **kwargs: Additional keyword arguments passed to the specific
                style handler.

        Returns:
            A formatted string representation of the object.
        """
        handler = self._STYLE_HANDLERS.get(style.lower())
        if handler is None:
            return self._pprint_repr(self, **kwargs)
        return handler(self, indent=indent, colored=colored, compact=compact, **kwargs)

    # ========== Built-in Handlers ==========
    @staticmethod
    def _pprint_default(
        obj: Any,
        indent: int = DFLT_INDENT_OFFSET,
        colored: bool = True,
        compact: bool = False,
        **kwargs: Any,
    ) -> str:
        """The default recursive, indented, and optionally colored formatter.

        This handler performs deep traversal of mappings and iterables. It
        includes specialized logic for:
        1. NumPy ndarrays: Shows shape, dtype, and a preview of data.
        2. Pandas DataFrames/Series: Renders a tabular preview with dimensions.
        3. ANSI Coloring: Applies specific colors to keys, strings, and numbers.
        4. Cycle Detection: Prevents infinite loops by identifying recursive
           references.

        Args:
            obj: The object to format.
            indent: Current indentation level. Defaults to `DFLT_INDENT_OFFSET`.
            colored: Whether to enable ANSI color output. Defaults to True.
            compact: If True, small nested items will stay on one line.
                Defaults to False.
            **kwargs: Can include 'COLORS' (a list of ANSI strings) to override
                the default color palette.

        Returns:
            A visually structured string representation.
        """
        HAS_NUMPY = compat.HAS_NUMPY
        HAS_PANDAS = compat.HAS_PANDAS
        np = compat.numpy
        pd = compat.pandas

        # --- ANSI colors ---
        COLORS = kwargs.pop(
            "COLORS",
            [
                "\033[38;5;39m",  # blue
                "\033[38;5;208m",  # orange
                "\033[38;5;70m",  # green
                "\033[38;5;206m",  # pink
                "\033[38;5;244m",  # gray
            ],
        )
        RESET = "\033[0m"

        color_cycle = cycle(COLORS)
        indent_space = "  " if indent == 0 else " " * indent
        seen: set[int] = set()

        # --- Helpers ---
        def colorize(text: str, color: str) -> str:
            return f"{color}{text}{RESET}" if colored else text

        def _indent_text(text: str, level: int) -> str:
            """Indents a block of text by `level` double-spaces."""
            return textwrap.indent(text, indent_space * level)

        def _handle_pandas(curr_obj: Any) -> str | None:
            """Returns formatted string if object is Pandas, else None."""
            if not HAS_PANDAS:
                return None
            if not isinstance(curr_obj, (pd.DataFrame, pd.Series)):
                return None

            try:
                if isinstance(curr_obj, pd.DataFrame):
                    data_str = curr_obj.to_string(max_rows=10, show_dimensions=False)
                else:
                    data_str = curr_obj.to_string(length=False, dtype=True, name=True)
                return f"<{type(curr_obj).__name__} shape={curr_obj.shape}>\n{data_str}"
            except Exception:
                return str(curr_obj)

        def _handle_numpy(curr_obj: Any) -> str | None:
            """Returns formatted string if object is Numpy, else None."""
            if not (HAS_NUMPY and isinstance(curr_obj, np.ndarray)):
                return None

            header = f"<ndarray shape={curr_obj.shape} dtype={curr_obj.dtype}>"
            data_str = np.array2string(
                curr_obj, edgeitems=2, threshold=5, separator=", "
            )
            return f"{header}\n{data_str}"

        def _format_kv_pair(k_str: str, v_str: str) -> str:
            if "\n" not in v_str:
                return f"{k_str}: {v_str}"

            v_lines = v_str.split("\n")
            header = v_lines[0]
            rest = v_lines[1:]

            if rest and rest[-1].strip() in ("]", "}", ")"):
                body_middle = _indent_text("\n".join(rest[:-1]), 1)
                footer = rest[-1]  # The closing brace
                body = f"{body_middle}\n{footer}" if body_middle else footer
            else:
                # Standard indention for generic multiline block
                body = _indent_text("\n".join(rest), 1)

            return f"{k_str}: {header}\n{body}"

        def _handle_mapping(
            curr_obj: Mapping[Any, Any], level: int, curr_color: str
        ) -> str:
            # 1. Determine items to print
            items_map: Mapping[Any, Any] = getattr(curr_obj, "_children", curr_obj)
            obj_type = type(curr_obj)
            type_name = obj_type.__name__ if obj_type is not dict else ""

            # 2. Setup Braces
            if hasattr(curr_obj, "key"):
                k_repr = repr(curr_obj.key)
                colored_k = colorize(k_repr, COLORS[2]) if colored else k_repr
                open_b = f"Lattix(key={colored_k}, {{"
                close_b = "})"
            else:
                open_b = f"{type_name} {{" if type_name else "{"
                close_b = "}"

            if not items_map:
                return open_b + close_b

            # 3. Format Itms
            next_color = next(color_cycle)
            formatted_items: list[str] = []
            any_multiline = False

            for k, v in items_map.items():
                k_str = colorize(repr(k), next_color)
                v_str = _recursive_format(v, level + 1, next_color)

                # Handle multiline values (like dataframes) nicely
                if "\n" in v_str:
                    any_multiline = True

                formatted_items.append(_format_kv_pair(k_str, v_str))

            # 4. Join Logic
            if compact and (not any_multiline) and (len(formatted_items) < 5):
                inner = ", ".join(formatted_items)
                return f"{colorize(open_b, curr_color)} {', '.join(formatted_items)} {colorize('}', curr_color)}"
            else:
                inner = ",\n".join(_indent_text(item, 1) for item in formatted_items)
                return (
                    f"{colorize(open_b, curr_color)}\n"
                    f"{inner}\n"
                    f"{colorize('}', curr_color)}"
                )

        def _handle_iterable(
            curr_obj: Iterable[Any], level: int, curr_color: str
        ) -> str:
            # 1. Setup Braces
            if isinstance(curr_obj, list):
                braces = ("[", "]")
            elif isinstance(curr_obj, tuple):
                braces = ("(", ")")
            elif isinstance(curr_obj, set):
                braces = ("{", "}")
            else:
                braces = ("[", "]")  # fallback

            if not curr_obj:
                return f"{braces[0]}{braces[1]}"

            # 2. Formt Items
            next_color = next(color_cycle)
            formatted_items = [
                _recursive_format(x, level + 1, next_color) for x in curr_obj
            ]
            # Detect multiline children to force vertical expansion
            any_multiline = any("\n" in x for x in formatted_items)

            # 3. Join
            # If it's a single-element tuple, ensure we add a comma
            if compact and (not any_multiline) and (len(formatted_items) <= 5):
                inner = ", ".join(formatted_items)
                if isinstance(curr_obj, tuple) and (len(formatted_items) == 1):
                    inner += ","
                return f"{colorize(braces[0], curr_color)}{inner}{colorize(braces[1], curr_color)}"

            # Vertical Layout
            inner = ",\n".join(_indent_text(x, 1) for x in formatted_items)

            return (
                f"{colorize(braces[0], curr_color)}\n"
                f"{inner}\n"
                f"{colorize(braces[1], curr_color)}"
            )

        # --- Main Recursive Logic ---
        def _recursive_format(curr_obj: Any, level: int, curr_color: str) -> str:
            # 1. Cycle Detection
            oid = id(curr_obj)
            if oid in seen:
                return f"<Circular {type(curr_obj).__name__} at {hex(oid)}>"

            # 2. Leaf Nodes (Pandas / Numpy)
            if (res := _handle_pandas(curr_obj)) is not None:
                return res
            if (res := _handle_numpy(curr_obj)) is not None:
                return res

            # 3. Recursion
            try:
                # Mappings
                if isinstance(curr_obj, Mapping):
                    seen.add(oid)
                    return _handle_mapping(curr_obj, level, curr_color)

                # Iterable (excluding strings/bytes)
                if isinstance(curr_obj, Iterable) and not is_primitive(curr_obj):
                    seen.add(oid)
                    return _handle_iterable(curr_obj, level, curr_color)
            finally:
                if oid in seen:
                    seen.remove(oid)

            # 4. Scalars / Primitives
            if isinstance(curr_obj, str):
                return colorize(repr(curr_obj), COLORS[2])  # Greenish for strings
            if isinstance(curr_obj, (int, float)):
                return colorize(repr(curr_obj), COLORS[1])  # Orange for numbers

            return colorize(repr(curr_obj), curr_color)

        # Start recursion
        result = _recursive_format(obj, 0, next(color_cycle))
        return _indent_text(result, indent // 2) if indent > 0 else result

    @staticmethod
    def _pprint_json(obj: Any, indent: int = DFLT_INDENT_WIDTH, **kwargs: Any) -> str:
        """Format the object as a JSON string.

        Uses the library's internal `serialize` function to ensure that
        non-standard types (like Lattix nodes or NumPy scalars) are
        converted to JSON-compatible primitives.

        Args:
            obj: The object to format.
            indent: Number of spaces for JSON indentation.
                Defaults to `DFLT_INDENT_WIDTH`.
            **kwargs: Additional arguments passed to `json.dumps`.

        Returns:
            A JSON-formatted string. Returns an error message string if
            serialization fails.
        """
        try:
            safe_obj = serialize(obj)
            kwargs.pop("colored", None)
            kwargs.pop("compact", None)
            return json.dumps(safe_obj, indent=indent, ensure_ascii=False, **kwargs)
        except Exception as e:
            return f"<JSON Serialization Error: {e}>"

    @staticmethod
    def _pprint_yaml(obj: Any, indent: int = DFLT_INDENT_WIDTH, **kwargs: Any) -> str:
        """Format the object as a YAML string.

        Args:
            obj: The object to format.
            indent: Number of spaces for YAML indentation.
                Defaults to `DFLT_INDENT_WIDTH`.
            **kwargs: Additional arguments passed to `yaml.safe_dump`.

        Returns:
            A YAML-formatted string.

        Raises:
            OptionalImportError: If PyYAML is not installed.
        """
        if not compat.HAS_YAML:
            raise OptionalImportError("PyYAML", "YAML serialization", "pyyaml")
        try:
            safe_obj = serialize(obj)
            kwargs.pop("colored", None)
            kwargs.pop("compact", None)
            return cast(
                str,
                compat.yaml.safe_dump(
                    safe_obj,
                    indent=indent,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                    **kwargs,
                ),
            ).rstrip()
        except Exception as e:
            return f"<YAML Serialization Error: {e}>"

    @staticmethod
    def _pprint_repr(
        obj: Any, indent: int = DFLT_INDENT_WIDTH, compact: bool = False, **kwargs: Any
    ) -> str:
        """Standard Python representation using the pprint module.

        Args:
            obj: The object to format.
            indent: Indentation for `pprint.pformat`. Defaults to `DFLT_INDENT_WIDTH`.
            compact: Whether to use compact mode in `pformat`. Defaults to False.
            **kwargs: Additional arguments passed to `pprint.pformat`.

        Returns:
            A standard Python repr string.
        """
        kwargs.pop("colored", None)
        return pprint.pformat(obj, indent=indent, compact=compact, **kwargs)


# =====================================================
# Register Built-in Styles
# =====================================================
FormatterMixin.register_style("default", FormatterMixin._pprint_default)  # type: ignore[reportPrivateUsage]
FormatterMixin.register_style("json", FormatterMixin._pprint_json)  # type: ignore[reportPrivateUsage]
FormatterMixin.register_style("yaml", FormatterMixin._pprint_yaml)  # type: ignore[reportPrivateUsage]
FormatterMixin.register_style("repr", FormatterMixin._pprint_repr)  # type: ignore[reportPrivateUsage]
