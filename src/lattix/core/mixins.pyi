import sys
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from threading import RLock as RLockType
from types import TracebackType
from typing import Any, ClassVar, Literal, TypeVar

from ..utils.types import StyleHandler, StyleRegistry

if sys.version_info >= (3, 11):
    from typing import Self  # Python 3.11+
else:
    from typing_extensions import Self

__all__: list[str]

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")

class ThreadingMixin(metaclass=ABCMeta):
    """Mixin providing thread-safety configuration and lock inheritance."""

    # ========== Internal attributes ==========
    _locking_enabled: bool
    _lock: RLockType | None
    _detached: bool

    # ========== Init ==========
    def _init_threading(
        self, parent: ThreadingMixin | None = ..., enable_lock: bool = ...
    ) -> None: ...

    # ========== Lock behavior ==========
    @property
    def locking_enabled(self) -> bool: ...
    @locking_enabled.setter
    def locking_enabled(self, enable: bool) -> None: ...

    # ========== Validation ==========
    @staticmethod
    def _validate_bool(value: Any) -> None: ...
    @staticmethod
    def _validate_parent(parent: Any) -> Literal[True]: ...
    @staticmethod
    def _validate_attachable(obj: ThreadingMixin) -> Literal[True]: ...

    # ========== Lifecycle ==========
    @staticmethod
    @abstractmethod
    def _propagate_lock(
        obj: Any,
        enable_lock: bool,
        lock: RLockType | None,
        seen: set[int] | None = ...,
    ) -> None: ...
    def propagate_lock(
        self,
        enable_lock: bool,
        lock: RLockType | None,
        seen: set[int] | None = ...,
    ) -> None: ...
    def detach_thread(self, clear_locks: bool = ...) -> None: ...
    def attach_thread(self, parent: ThreadingMixin) -> None: ...
    def transplant_thread(self, parent: ThreadingMixin) -> None: ...

    # ========== Context manager ==========
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    # ========== Lock operations ==========
    def acquire(self, blocking: bool = ..., timeout: float = ...) -> bool: ...
    def release(self) -> None: ...

    # ========== Representation ==========
    def _describe_lock(self) -> str: ...

class LogicalMixin:
    """Abstract mixin providing logical (set-like) operations for mapping objects."""

    # ========== Constructors & Classmethods ==========
    @classmethod
    @abstractmethod
    def _construct(cls, data: Any, config: Any = ..., /, **kwargs: Any) -> Self: ...

    # ========== AND (&) ==========
    def __and__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __rand__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __iand__(self, other: Mapping[_KT, _VT]) -> Self: ...
    @abstractmethod
    def _and_impl(self, other: Mapping[_KT, _VT], inplace: bool = ...) -> Self: ...
    def and_(self, other: Mapping[_KT, _VT]) -> Self: ...

    # ========== OR (|) ==========
    def __or__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __ror__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __ior__(self, other: Mapping[_KT, _VT]) -> Self: ...
    @abstractmethod
    def _or_impl(self, other: Mapping[_KT, _VT], inplace: bool = ...) -> Self: ...
    def or_(self, other: Mapping[_KT, _VT]) -> Self: ...

    # ========== SUB (-) ==========
    def __sub__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __rsub__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __isub__(self, other: Mapping[_KT, _VT]) -> Self: ...
    @abstractmethod
    def _sub_impl(self, other: Mapping[_KT, _VT], inplace: bool = ...) -> Self: ...
    def sub(self, other: Mapping[_KT, _VT]) -> Self: ...

    # ========== XOR (^) ==========
    def __xor__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __rxor__(self, other: Mapping[_KT, _VT]) -> Self | object: ...
    def __ixor__(self, other: Mapping[_KT, _VT]) -> Self: ...
    @abstractmethod
    def _xor_impl(self, other: Mapping[_KT, _VT], inplace: bool = ...) -> Self: ...
    def xor(self, other: Mapping[_KT, _VT]) -> Self: ...

class FormatterMixin:
    """Mixin providing flexible, multi-style pretty-printing support."""

    # ========== Internal attributes ==========
    _STYLE_HANDLERS: ClassVar[StyleRegistry]

    # ========== Style Registration ==========
    @classmethod
    def register_style(cls, name: str, func: StyleHandler) -> None: ...

    # ========== Public API ==========
    def pprint(
        self,
        indent: int = ...,
        colored: bool = ...,
        compact: bool = ...,
        style: str = ...,
        **kwargs: Any,
    ) -> str: ...
    @staticmethod

    # ========== Built-in Handlers ==========
    def _pprint_default(
        obj: Any,
        indent: int = ...,
        colored: bool = ...,
        compact: bool = ...,
        **kwargs: Any,
    ) -> str: ...
    @staticmethod
    def _pprint_json(obj: Any, indent: int = ..., **kwargs: Any) -> str: ...
    @staticmethod
    def _pprint_yaml(obj: Any, indent: int = ..., **kwargs: Any) -> str: ...
    @staticmethod
    def _pprint_repr(
        obj: Any, indent: int = ..., compact: bool = ..., **kwargs: Any
    ) -> str: ...
