from __future__ import annotations

__all__ = ["AbstractDict", "MutableAbstractDict"]

from abc import ABC, abstractmethod
from collections.abc import Mapping, MutableMapping
import re
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:   # pragma: no cover
    from collections.abc import Iterable, Iterator
    from typing import Any
    from ..utils.types import DictType, TupleType

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_ASCII_ATTR_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class AbstractDict(ABC, Mapping[_KT, _VT]):
    """Abstract base class for read-only dynamic mapping structures."""

    # ========== Required core methods ==========
    @abstractmethod
    def __getitem__(self, key: _KT) -> Any: ...
    @abstractmethod
    def __iter__(self) -> Iterator[_KT]: ...
    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def _config(self) -> Any:
        """
        All required state for building a new instance with the same
        settings as the current object.
        """
    
    @classmethod
    def _construct(cls, mapping: Mapping[_KT, _VT], config: TupleType[Any, ...], /, **kwargs: Any) -> Any:
        """
        A standardized constructor used internally.

        mapping: A mapping of key-value pairs. It is HIGHLY recommended
           that you use this as the internal key-value pair mapping, as
           that will allow nested assignment (e.g., attr.foo.bar = baz)
        configuration: The return value of Attr._configuration
        """
        raise NotImplementedError

    # ========== Optional or default implementations ==========
    def get(self, key: _KT, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> DictType[_KT, Any]:
        """Default recursive conversion to plain dict."""
        return {k: (v.to_dict() if isinstance(v, AbstractDict) else v)
                for k, v in self.items()}

    def __contains__(self, key: Any) -> bool:
        return any(k == key for k in self)

    @staticmethod
    def _valid_name(name: str) -> bool:
        return bool(name and _ASCII_ATTR_RE.match(name))


class MutableAbstractDict(AbstractDict[_KT, _VT], MutableMapping[_KT, _VT]):
    """Extends AbstractDict to support mutation."""

    # ========== Required mutation interface ==========
    @abstractmethod
    def __setitem__(self, key: _KT, value: _VT) -> None: ...
    @abstractmethod
    def __delitem__(self, key: _KT) -> None: ...

    # ========== Optional convenience methods ==========
    def update(self, other: Mapping[_KT, _VT] | Iterable[TupleType[_KT, _VT]] = (), /, **kwargs: _VT) -> None: # pyright: ignore
        """Generic update implementation."""
        if isinstance(other, Mapping):
            map_obj = cast(Mapping[_KT, _VT], other)
            for k, v in map_obj.items():
                self[k] = v
        elif hasattr(other, "keys"):
            for k in other.keys():  # pyright: ignore
                self[k] = other[k]  # pyright: ignore
        else:
            for k, v in other:
                self[k] = v
                
        for k, v in kwargs.items():
            self[k] = v  # pyright: ignore
    
    def merge(
        self, 
        other: MutableMapping[_KT, _VT], 
        overwrite: bool = True
    ) -> MutableAbstractDict[_KT, _VT]:
        """Recursive merge template."""
        if not isinstance(other, Mapping):  # pyright: ignore
            raise TypeError(f"Expected map-like, got {type(other).__name__}")

        for k, v in other.items():
            if (k in self
                and isinstance(self[k], MutableAbstractDict)
                and isinstance(v, Mapping)):
                self[k].merge(v, overwrite)
            elif overwrite or k not in self:
                self[k] = v
        return self


if __name__ == "__main__":
    import inspect
    for abstract in (AbstractDict, MutableAbstractDict):
        for c in abstract.__mro__:
            slots = getattr(c, "__slots__", None)
            has_dict = False
            if "__dict__" in (slots if isinstance(slots, (list, tuple)) else (slots or ())):
                has_dict = True
            print(f"{c!r:60} | __slots__ = {slots!r:30} | has '__dict__' in slots? {has_dict}")

        print("\n=== Check if any base is builtin heap type (like dict) ===")
        for c in abstract.__mro__:
            print(c, "is builtin type subclass of dict?", issubclass(c, dict) if inspect.isclass(c) else "n/a")

        print("\n=== Show attrs related to __dict__ presence ===")
        for c in abstract.__mro__:
            print(c.__name__, "->", "has __dict__ attribute?", "__dict__" in c.__dict__)
        
        print()