from __future__ import annotations

__all__ = ["ThreadingMixin", "LogicalMixin", "FormatterMixin"]

from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping
from itertools import cycle
import json
import logging
import pprint
import textwrap
from threading import Lock, RLock
from typing import TYPE_CHECKING, Any, Protocol, cast

from ..utils.exceptions import (
   NoPyYAMLError,
   OperandTypeError,
   ThreadSafetyLevelTypeError,
   ThreadSafetyLevelValueError,
   ThreadingObjectTypeError,
   UnattachableError,
   LockExistenceError,
)
from ..utils.common import serialize


if TYPE_CHECKING:   # pragma: no cover
    from _thread import LockType, RLock as RLockType
    from types import TracebackType
    from typing_extensions import Self
    from ..utils.types import (
        StyleHandler, ListType, SetType, StyleRegistry, TypeType
    )

logger = logging.getLogger(__name__)

class _HasChildren(Protocol):
    children: Mapping[str, Any]


class ThreadingMixin(metaclass=ABCMeta):
    """
    Mixin providing thread-safety configuration and lock inheritance.
    """
    _ts_level: int
    _lock: LockType | None
    _rlock: RLockType | None
    _detached: bool
   
    # ---------- Init ----------
    def _init_threading(self, parent: ThreadingMixin | None = None, level: int = 0):
        """Initialize threading context. If parent is given, inherit its locks."""
        self._validate_level(level)

        if parent:
            # inherit parent's locks
            self.attach_thread(parent)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"[TM:INIT] inherit: self={hex(id(self))} parent={hex(id(parent))} "
                    f"level={getattr(self, '_ts_level', None)} lock={hex(id(self._lock)) if self._lock else None} "
                    f"rlock={hex(id(self._rlock)) if self._rlock else None}"
                )
        else:
            # create new locks
            object.__setattr__(self, "_ts_level", level)
            object.__setattr__(self, "_lock", Lock() if level == 1 else None)
            object.__setattr__(self, "_rlock", RLock() if level == 2 else None)
            object.__setattr__(self, "_detached", True)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"[TM:INIT] new: self={hex(id(self))} level={level} "
                    f"lock={hex(id(self._lock)) if self._lock else None} rlock={hex(id(self._rlock)) if self._rlock else None}"
                )

    @staticmethod
    def _validate_level(level: Any):
        if not isinstance(level, int):
            raise ThreadSafetyLevelTypeError(level)
        if level not in (0, 1, 2):
            raise ThreadSafetyLevelValueError(level)
    
    @staticmethod
    def _validate_parent(parent: Any):
        if not isinstance(parent, ThreadingMixin):
            raise ThreadingObjectTypeError("parent", parent)
        return True

    @staticmethod
    def _validate_attachable(obj: ThreadingMixin):
        if not getattr(obj, "_detached", True):
            raise UnattachableError
        if getattr(obj, "_lock", None) or getattr(obj, "_rlock", None):
            raise LockExistenceError
        return True

    # ---------- Lock behavior ----------
    @property
    def ts_level(self):
        return getattr(self, "_ts_level", 0)
        # return self._ts_level
    
    @ts_level.setter
    def ts_level(self, level: int):
        self._validate_level(level)
        # set locks by propagating references; do not create/destroy locks in destructors
        if level == 0:
            self._propagate_lock(self, 0, None, None)
        elif level == 1:
            self._propagate_lock(self, 1, Lock(), None)
        else:   # level == 2
            self._propagate_lock(self, 2, None, RLock())

    @staticmethod
    @abstractmethod
    def _propagate_lock(
        obj: Any, 
        level: int, 
        lock:  LockType | None, 
        rlock: RLockType | None, 
        seen:  SetType[Any] | None=None
    ) -> None:
        """Abstract: implemented by container class (Lattix) to traverse subtree."""
        raise NotImplementedError

    def propagate_lock(
        self, 
        level: int, 
        lock: LockType | None, 
        rlock: RLockType | None, 
        seen: SetType[Any] | None = None
    ):
        self._propagate_lock(self, level, lock, rlock, seen)

    def detach_thread(self, clear_locks: bool = False):
        """Reinitialize locks to make this object independent."""
        if clear_locks:
            lvl = 0
            object.__setattr__(self, "_ts_level", lvl)
        else:
            lvl = getattr(self, "_ts_level", 0)

        self._validate_level(lvl)
        object.__setattr__(self, "_lock", Lock() if lvl == 1 else None)
        object.__setattr__(self, "_rlock", RLock() if lvl == 2 else None)
        object.__setattr__(self, "_detached", True)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[TM:DETACH] id={hex(id(self))} level={lvl} "
                f"new_lock={hex(id(self._lock)) if self._lock else None} "
                f"new_rlock={hex(id(self._rlock)) if self._rlock else None}"
            )
    
    def attach_thread(self, parent: Any):
        """Adopt parent's locks."""
        self._validate_parent(parent)
        self._validate_attachable(self)

        object.__setattr__(self, "_ts_level", parent._ts_level)
        object.__setattr__(self, "_lock", parent._lock)
        object.__setattr__(self, "_rlock", parent._rlock)
        object.__setattr__(self, "_detached", False)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[TM:ATTACH] id={hex(id(self))} parent_id={hex(id(parent))} "
                f"level={self._ts_level} lock={hex(id(self._lock)) if self._lock else None} "
                f"rlock={hex(id(self._rlock)) if self._rlock else None}"
            )

    def transplant_thread(self, parent: Any):
        """Transplant locks to parent's locks."""
        self._validate_parent(parent)

        object.__setattr__(self, "_ts_level", parent._ts_level)
        object.__setattr__(self, "_lock", parent._lock)
        object.__setattr__(self, "_rlock", parent._rlock)
        object.__setattr__(self, "_detached", False)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[TM:TRANSPLANT] id={hex(id(self))} parent_id={hex(id(parent))} "
                f"level={self._ts_level} lock={hex(id(self._lock)) if self._lock else None} "
                f"rlock={hex(id(self._rlock)) if self._rlock else None}"
            )

    # ---------- Lock operations ----------
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(
        self, 
        exc_type: TypeType[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        self.release()

    def acquire(self, blocking: bool = True, timeout: float = -0.1) -> bool:
        if self._rlock:
            return self._rlock.acquire(blocking, timeout)
        return False

    def release(self):
        if self._rlock:
            self._rlock.release()
        elif self._lock:
            self._lock.release()

    def _describe_lock(self) -> str:
        """Helper for debugging lock inheritance."""
        return str(
            f"rlock={hex(id(self._rlock)) if self._rlock else None} "
            f"level={self._ts_level}"
        )


class LogicalMixin:
    """
    Abstract mixin providing logical (set-like) operations for mapping objects.

    This mixin defines logical operators (`&`, `|`, `-`, `^`) for mappings,
    which behave analogously to Python's ``set`` operations, but apply to 
    *mapping keys* rather than values.
    Each operator delegates to an internal implementation method.

    **Operators**
    - ``&`` : Intersection  
    - ``|`` : Union  
    - ``-`` : Difference  
    - ``^`` : Symmetric difference 

    **Required Methods**
    - :meth:`_and_impl(self, other, inplace=False)`  
    - :meth:`_or_impl(self, other, inplace=False)`  
    - :meth:`_sub_impl(self, other, inplace=False)`  
    - :meth:`_xor_impl(self, other, inplace=False)`  

    The ``inplace`` flag indicates whether the operation should return
    a new instance (``inplace=False``) or mutate the current instance
    (``inplace=True``), enabling support for in-place operators like ``|=``.

    Notes:
        Subclasses must implement all four internal methods to enable the
        corresponding logical operators.
    
    **Example**  
    ..  code-block:: python
        class MyDict(LogicalMixin, dict):
            def _and_impl(self, other, inplace=False):
                result = {k: self[k] for k in self if k in other}
                if inplace:
                    self.clear()
                    self.update(result)
                    return self
                return MyDict(result)

        d1 = MyDict({"a": 1, "b": 2})
        d2 = MyDict({"b": 99, "c": 3})

        print(d1 & d2)    # → {"b": 99}
        print(d1 | d2)    # → {"a": 1, "b": 99, "c": 3}
        print(d1 - d2)    # → {"a": 1}
        print(d1 ^ d2)    # → {"a": 1, "c": 3}
    """
    
    @classmethod
    @abstractmethod
    def _construct(cls, data: Any, config: Any = None, /, **kwargs: Any) -> Self:
        raise NotImplementedError
    
    # ================================================================
    #  AND (&)
    # ================================================================
    def __and__(self, other: Any):
        """Return the intersection (`&`) of this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._and_impl(other, inplace=False)

    def __rand__(self, other: Any):
        """Right-hand fallback for ``Mapping & LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._and_impl(self, inplace=False)

    def __iand__(self, other: Any):
        """In-place intersection (``&=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "&=")
        return self._and_impl(other, inplace=True)
    
    @abstractmethod
    def _and_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of intersection logic."""
        pass

    def and_(self, other: Any):
        """Functional equivalent of the ``&`` operator."""
        return self._and_impl(other)

    # ================================================================
    #  OR (|)
    # ================================================================
    def __or__(self, other: Any):
        """Return the union (``|``) of this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._or_impl(other, inplace=False)

    def __ror__(self, other: Any):
        """Right-hand fallback for ``Mapping | LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._or_impl(self, inplace=False)

    def __ior__(self, other: Any):
        """In-place union (``|=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "|=")
        return self._or_impl(other, inplace=True)

    @abstractmethod
    def _or_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of union logic."""
        pass

    def or_(self, other: Any):
        """Functional equivalent of the ``|`` operator."""
        return self._or_impl(other)

    # ================================================================
    #  SUB (-)
    # ================================================================
    def __sub__(self, other: Any):
        """Return the difference (``-``) between this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._sub_impl(other, inplace=False)

    def __rsub__(self, other: Any):
        """Right-hand fallback for ``Mapping - LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._sub_impl(self, inplace=False)

    def __isub__(self, other: Any):
        """In-place difference (``-=``)."""
        if not isinstance(other, Mapping):
           raise OperandTypeError(self, other, "-=")
        return self._sub_impl(other, inplace=True)
    
    @abstractmethod
    def _sub_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of difference logic."""
        pass

    def sub(self, other: Any):
        """Functional equivalent of the ``-`` operator."""
        return self._sub_impl(other)
    
    # ================================================================
    #  XOR (^)
    # ================================================================
    def __xor__(self, other: Any):
        """Return the symmetric difference (``^``) of this mapping and *other*."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._xor_impl(other, inplace=False)
    
    def __rxor__(self, other: Any):
        """Right-hand fallback for ``Mapping ^ LogicalMixin``."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._construct(other)._xor_impl(self, inplace=False)
    
    def __ixor__(self, other: Any):
        """In-place symmetric difference (``^=``)."""
        if not isinstance(other, Mapping):
            raise OperandTypeError(self, other, "^=")
        return self._xor_impl(other, inplace=True)
    
    @abstractmethod
    def _xor_impl(self, other: Any, inplace: bool = False):
        """Actual implementation of symmetric difference logic."""
        pass

    def xor(self, other: Any):
        """Functional equivalent of the ``^`` operator."""
        return self._xor_impl(other)


class FormatterMixin:
    """
    A mixin providing flexible, multi-style pretty-printing support.

    Built-in styles:
        - "default": Recursive, indented, optionally colored display.
        - "json": JSON-formatted output.
        - "yaml": YAML-formatted output (requires PyYAML).
        - "repr": Fallback to Python's repr().

    You can register custom pprint styles via:
        FormatterMixin.register_style("name", func)
    """
    _STYLE_HANDLERS: StyleRegistry = {}

    # =====================================================
    # Style Registration
    # =====================================================
    @classmethod
    def register_style(cls, name: str, func: StyleHandler):
        """Register a new pprint style."""
        cls._STYLE_HANDLERS[name.lower()] = func
    
    # =====================================================
    # Public API
    # =====================================================
    def pprint(self, indent: int = 0, colored: bool = False, 
               compact: bool = True, style: str = "default", 
               **kwargs: Any) -> str:
        """Pretty-print in the given style."""
        handler = self._STYLE_HANDLERS.get(style.lower())
        if handler is None:
            return self._pprint_repr(self, **kwargs)
        return handler(self, indent=indent, colored=colored, 
                       compact=compact, **kwargs)

    # =====================================================
    # Built-in Handlers
    # =====================================================
    @staticmethod
    def _pprint_default(obj: Any, indent: int = 0, colored: bool = True, 
                        compact: bool = False, **kwargs: Any) -> str:
        """Recursive, indented, optionally colored display."""
        from ..utils.compat import (
            HAS_NUMPY, HAS_PANDAS, numpy as np, pandas as pd
        )

        # --- ANSI colors ---
        COLORS = kwargs.pop("COLORS", [
            "\033[38;5;39m",   # blue
            "\033[38;5;208m",  # orange
            "\033[38;5;70m",   # green
            "\033[38;5;206m",  # pink
            "\033[38;5;244m",  # gray
        ])
        RESET = "\033[0m"

        color_cycle = cycle(COLORS)
        indent_space = "  " if indent == 0 else " " * indent
        seen: SetType[int] = set()
        
        # --- Helpers ---
        
        def colorize(text: str, color: str) -> str:
            return f"{color}{text}{RESET}" if colored else text
        
        def _indent_text(text: str, level: int) -> str:
            """Indents a block of text by `level` double-spaces."""
            return textwrap.indent(text, indent_space * level)
        
        def _handle_pandas(curr_obj: Any) -> str | None:
            """Returns formatted string if object is Pandas, else None."""
            if not (HAS_PANDAS and isinstance(curr_obj, (pd.DataFrame, pd.Series))):
                return None
            
            pd_obj = cast(Any, curr_obj)
            shape_str = f"shape={pd_obj.shape}"

            try:
                if isinstance(curr_obj, pd.DataFrame):
                    data_str = pd_obj.to_string(max_rows=10, show_dimensions=False)
                else:
                    data_str = pd_obj.to_string(length=False, dtype=True, name=True)
                return f"<{type(pd_obj).__name__} {shape_str}>\n{data_str}"
            except Exception:
                return str(pd_obj)
        
        def _handle_numpy(curr_obj: Any) -> str | None:
            """Returns formatted string if object is Numpy, else None."""
            if not (HAS_NUMPY and isinstance(curr_obj, np.ndarray)):
                return None
            
            np_obj = cast(Any, curr_obj)
            header = f"<ndarray shape={np_obj.shape} dtype={np_obj.dtype}>"
            data_str = np.array2string(np_obj, edgeitems=2, threshold=5, separator=', ')
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
        
        def _handle_mapping(curr_obj: Mapping[Any, Any], level: int, curr_color: str) -> str:
            # 1. Determine items to print
            items_map: Mapping[Any, Any]
            type_name = ""

            # Support for Lattix internal structure if needed, or standard items
            if isinstance(curr_obj, FormatterMixin) and hasattr(curr_obj, "children"):
                items_map = cast(_HasChildren, curr_obj).children
                type_name = type(curr_obj).__name__
            else:
                items_map = curr_obj
                if type(items_map) is not dict:
                    type_name = type(curr_obj).__name__

            # 2. Setup Braces
            open_brace = f"{type_name} {{" if type_name else "{"
            close_brace = "}"

            if not items_map:
                return f"{open_brace}{close_brace}"

            # 3. Format Itms
            next_color = next(color_cycle)
            formatted_items: ListType[str] = []
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
                return f"{colorize(open_brace, curr_color)} {inner} {colorize(close_brace, curr_color)}"
            else:
                # Standard indented view
                # inner = ",\n".join(f"  {item}" for item in formatted_items)
                # Add indentation to the whole block of items
                # inner = ",\n".join(textwrap.indent(item, "  ") for item in formatted_items)
                inner = ",\n".join(_indent_text(item, 1) for item in formatted_items)
                return (
                   f"{colorize(open_brace, curr_color)}\n"
                   f"{inner}\n"
                   f"{colorize(close_brace, curr_color)}"
                )
        
        def _handle_iterable(curr_obj: Iterable[Any], level: int, curr_color: str) -> str:
            # 1. Setup Braces
            if isinstance(curr_obj, list): open_b, close_b = "[", "]"
            elif isinstance(curr_obj, tuple): open_b, close_b = "(", ")"
            elif isinstance(curr_obj, set): open_b, close_b = "{", "}"
            else: open_b, close_b = "[", "]"  # fallback

            if not curr_obj:
                return f"{open_b}{close_b}"

            # 2. Formt Items
            next_color = next(color_cycle)
            formatted_items = [
                _recursive_format(x, level + 1, next_color) for x in curr_obj
            ]
            # Detect multiline children to force vertical expansion
            any_multiline = any("\n" in item for item in formatted_items)
            
            # 3. Join
            # If it's a single-element tuple, ensure we add a comma
            if compact and (not any_multiline) and (len(formatted_items) <= 5):
                inner = ", ".join(formatted_items)
                if isinstance(curr_obj, tuple) and len(formatted_items) == 1:
                    inner += ","
                return f"{colorize(open_b, curr_color)}{inner}{colorize(close_b, curr_color)}"
            
            # Vertical Layout
            inner = ",\n".join(_indent_text(x, 1) for x in formatted_items)

            return (
                f"{colorize(open_b, curr_color)}\n"
                f"{inner}\n"
                f"{colorize(close_b, curr_color)}"
            )
        
        # --- Main Recursive Logic ---

        def _recursive_format(curr_obj: Any, level: int, curr_color: str) -> str:
            # 1. Cycle Detection
            oid = id(curr_obj)
            if oid in seen:
                return f"<Cycle {type(curr_obj).__name__} ...>"
            
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
                if isinstance(curr_obj, Iterable) and not isinstance(curr_obj, (str, bytes, bytearray)):
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

        """```Deprecated```
        def _recursive_format(curr_obj: Any, level: int, curr_color: str) -> str:
            # 1. Cycle Detection
            oid = id(curr_obj)
            if oid in seen:
                return f"<Cycle {type(curr_obj).__name__} ...>"
            
            # 2. Pandas DataFrame / Series (Leaf nodes, no recursion into them)
            if HAS_PANDAS and isinstance(curr_obj, (pd.DataFrame, pd.Series)):
                pd_obj = cast(Any, curr_obj)
                shape_str = f"shape={pd_obj.shape}"
                try:
                    if isinstance(curr_obj, pd.DataFrame):
                        data_str = pd_obj.to_string(max_rows=10, show_dimensions=False)
                    else:
                        data_str = pd_obj.to_string(length=False, dtype=True, name=True)
                    return f"<{type(pd_obj).__name__} {shape_str}>\n{data_str}"
                except Exception:
                    return str(pd_obj)
            
            # 3. Numpy Array
            if HAS_NUMPY and isinstance(curr_obj, np.ndarray):
                np_obj = cast(Any, curr_obj)
                header = f"<ndarray shape={np_obj.shape} dtype={np_obj.dtype}>"
                data_str = np.array2string(np_obj, edgeitems=2, threshold=5, separator=', ')
                return f"{header}\n{data_str}"
            
            # 4. Mappings (Dicts, Lattix)
            if isinstance(curr_obj, Mapping):
                seen.add(oid)
                map_obj = cast(Mapping[Any, Any], curr_obj)
                try:
                    next_color = next(color_cycle)
                    items_map: Mapping[Any, Any]
                    
                    # Handle Lattix internals if needed, or standard items
                    if isinstance(map_obj, FormatterMixin) and hasattr(map_obj, "children"):
                        node = cast(_HasChildren, map_obj)
                        items_map = node.children
                        type_name = type(map_obj).__name__
                    else:
                        items_map = map_obj
                        type_name = ""

                    # Prepare Braces
                    open_brace = f"{type_name} {{" if type_name else "{"
                    close_brace = "}"

                    if not items_map:
                        return f"{open_brace}{close_brace}"

                    formatted_items: ListType[str] = []
                    any_multiline_items = False

                    for k, v in items_map.items():
                        k_str = colorize(repr(k), next_color)
                        v_str = _recursive_format(v, level + 1, next_color)

                        # Handle multiline values (like dataframes) nicely
                        if "\n" in v_str:
                            any_multiline_items = True
                            v_lines = v_str.split('\n')
                            header = v_lines[0]
                            rest = v_lines[1:]

                            if rest and rest[-1].strip() in ("]", "}", ")"):
                                body_middle = _indent_text("\n".join(rest[:-1]), 1)
                                footer = rest[-1]  # The closing brace
                                
                                # Reassemble
                                body = f"{body_middle}\n{footer}" if body_middle else footer
                                formatted_items.append(f"{k_str}: {header}\n{body}")
                            else:
                                # Standard block
                                body = _indent_text("\n".join(rest), 1)
                                formatted_items.append(f"{k_str}: {header}\n{body}")
                        else:
                            formatted_items.append(f"{k_str}: {v_str}")

                    # Join Logic
                    if compact and not any_multiline_items and len(formatted_items) < 5:
                        inner = ", ".join(formatted_items)
                        return f"{colorize(open_brace, curr_color)} {inner} {colorize(close_brace, curr_color)}"
                    else:
                        # Standard indented view
                        # inner = ",\n".join(f"  {item}" for item in formatted_items)
                        # Add indentation to the whole block of items
                        # inner = ",\n".join(textwrap.indent(item, "  ") for item in formatted_items)
                        inner = ",\n".join(_indent_text(item, 1) for item in formatted_items)
                        return (
                           f"{colorize(open_brace, curr_color)}\n"
                           f"{inner}\n"
                           f"{colorize(close_brace, curr_color)}"
                        )
                finally:
                    seen.remove(oid)
            
            # 5. Iterables (List, Tuple, Set)
            if isinstance(curr_obj, Iterable) and not isinstance(curr_obj, (str, bytes, bytearray)):
                seen.add(oid)
                iter_obj = cast(Iterable[Any], curr_obj)
                try:
                    next_color = next(color_cycle)
                    if isinstance(iter_obj, list): open_b, close_b = "[", "]"
                    elif isinstance(iter_obj, tuple): open_b, close_b = "(", ")"
                    elif isinstance(iter_obj, set): open_b, close_b = "{", "}"
                    else: open_b, close_b = "[", "]"  # fallback

                    if not curr_obj:
                        return f"{open_b}{close_b}"

                    formatted_items = [
                        _recursive_format(x, level + 1, next_color) for x in iter_obj
                    ]
                    # Detect multiline children to force vertical expansion
                    any_multiline = any('\n' in item for item in formatted_items)
                    
                    # If it's a single-element tuple, ensure we add a comma
                    if compact and not any_multiline and len(formatted_items) <= 5:
                        inner = ", ".join(formatted_items)
                        if isinstance(iter_obj, tuple) and len(formatted_items) == 1:
                            inner += ","
                        return f"{colorize(open_b, curr_color)}{inner}{colorize(close_b, curr_color)}"
                    
                    # Vertical Layout
                    inner = ",\n".join(_indent_text(x, 1) for x in formatted_items)

                    return (
                        f"{colorize(open_b, curr_color)}\n"
                        f"{inner}\n"
                        f"{colorize(close_b, curr_color)}"
                    )
                finally:
                    seen.remove(oid)
            
            # 6. Scalars / Primitives
            if isinstance(curr_obj, str):
                return colorize(repr(curr_obj), COLORS[2]) # Greenish for strings
            if isinstance(curr_obj, (int, float)):
                return colorize(repr(curr_obj), COLORS[1]) # Orange for numbers
            
            return colorize(repr(curr_obj), curr_color)
        """

        # Start recursion
        result = _recursive_format(obj, 0, next(color_cycle))
        # return _indent_text(result, indent) if indent > 0 else result
        return result

    @staticmethod
    def _pprint_json(obj: Any, indent: int = 2, **kwargs: Any) -> str:
       """JSON-style pretty-print."""
       try:
           safe_obj = serialize(obj)
           kwargs.pop("colored", None)
           kwargs.pop("compact", None)
           return json.dumps(safe_obj, indent=indent, ensure_ascii=False, **kwargs)
       except Exception as e:
           return f"<JSON Serialization Error: {e}>"

    @staticmethod
    def _pprint_yaml(obj: Any, indent: int = 2, **kwargs: Any) -> str:
        """YAML-style pretty-print (requires PyYAML)."""
        from ..utils.compat import HAS_YAML, yaml

        if not HAS_YAML:
            raise NoPyYAMLError
        try:
            safe_obj = serialize(obj)
            kwargs.pop("colored", None)
            kwargs.pop("compact", None)
            return cast(str, yaml.safe_dump(
                safe_obj,
                indent=indent,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                **kwargs
            )).rstrip()
        except Exception as e:
            return f"<YAML Serialization Error: {e}>"

    @staticmethod
    def _pprint_repr(obj: Any, indent: int = 2, 
                     compact: bool = False, **kwargs: Any) -> str:
        """Fallback repr-style."""
        kwargs.pop("colored", None)
        return pprint.pformat(obj, indent=indent, compact=compact, **kwargs)

# =====================================================
# Register Built-in Styles
# =====================================================
FormatterMixin.register_style("default", FormatterMixin._pprint_default)  # type: ignore[reportPrivateUsage]
FormatterMixin.register_style("json", FormatterMixin._pprint_json)        # type: ignore[reportPrivateUsage]
FormatterMixin.register_style("yaml", FormatterMixin._pprint_yaml)        # type: ignore[reportPrivateUsage]
FormatterMixin.register_style("repr", FormatterMixin._pprint_repr)        # type: ignore[reportPrivateUsage]



if __name__ == "__main__":
    import inspect
    for mixin in (ThreadingMixin, LogicalMixin, FormatterMixin):
        for c in mixin.__mro__:
            slots = getattr(c, "__slots__", None)
            has_dict = False
            if "__dict__" in (slots if isinstance(slots, (list, tuple)) else (slots or ())):
                has_dict = True
            print(f"{c!r:60} | __slots__ = {slots!r:30} | has '__dict__' in slots? {has_dict}")

        print("\n=== Check if any base is builtin heap type (like dict) ===")
        for c in mixin.__mro__:
            print(c, "is builtin type subclass of dict?", issubclass(c, dict) if inspect.isclass(c) else "n/a")

        print("\n=== Show attrs related to __dict__ presence ===")
        for c in mixin.__mro__:
            print(c.__name__, "->", "has __dict__ attribute?", "__dict__" in c.__dict__)
        # print(dir(mixin))
        # print(mixin.__dict__)
        # print(hasattr(mixin, "__dict__"), hasattr(mixin, "__slots__"))
        # if hasattr(mixin, "__slots__"):
        #    print(mixin.__slots__)
        print()
