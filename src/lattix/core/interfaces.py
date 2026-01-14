"""Abstract Base Classes for Lattix mapping structures.

This module defines the formal interfaces and abstract base classes (ABCs)
that form the foundation of the Lattix library. By inheriting from these
interfaces, concrete classes ensure compatibility with Python's mapping
protocols while adding hierarchical and configuration-aware capabilities.

The interfaces are split into two levels:
    1. **Read-Only Interface** (:class:`LattixMapping`): Defines the
       minimal requirements for a hierarchical structure that can be
       traversed and queried.
    2. **Mutable Interface** (:class:`MutableLattixMapping`): Extends the
       read-only interface with methods for data modification, recursive
       updates, and deep merging.

Key Design Patterns:
    * **Standardization**: Implements ``collections.abc.Mapping`` and
      ``collections.abc.MutableMapping`` for full compatibility with
      built-in functions like ``dict()``, ``len()``, and the ``**`` operator.
    * **Self-Reconstruction**: Defines the ``_config`` and ``_construct``
      pattern, allowing subtrees to be created with the same settings
      as their parent nodes.
    * **Recursive Logic**: Provides a default implementation for
      ``to_dict`` and ``merge`` that handles nested Lattix structures
      automatically.

Classes:
    LattixMapping: Abstract base class for read-only hierarchical mappings.
    MutableLattixMapping: Abstract base class for mutable hierarchical mappings.
"""

from __future__ import annotations

import re
import sys
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

if sys.version_info >= (3, 9):
    from collections.abc import Iterator, Mapping, MutableMapping
else:
    from typing import Iterator, Mapping, MutableMapping

__all__ = ["LattixMapping", "MutableLattixMapping"]

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_ASCII_ATTR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LattixMapping(ABC, Mapping[Any, Any], Generic[_KT, _VT]):
    """Abstract base class for read-only dynamic mapping structures.

    This class defines the basic interface for hierarchical mappings that
    support both dictionary-style and potential attribute-style access.
    """

    # ========== Required core methods ==========
    @abstractmethod
    def __getitem__(self, key: _KT) -> Any: ...
    @abstractmethod
    def __iter__(self) -> Iterator[_KT]: ...
    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def _config(self) -> Any:
        """Returns the internal state required to reconstruct the object.

        Returns:
            A representation of the configuration settings (e.g., separator,
            lazy creation flags, etc.).
        """
        ...

    @classmethod
    @abstractmethod
    def _construct(
        cls,
        mapping: Mapping[_KT, _VT],
        config: tuple[Any, ...],
        /,
        **kwargs: Any,
    ) -> Any:
        """Standardized internal factory method.

        Args:
            mapping: A mapping of key-value pairs to populate the instance.
            config: A tuple containing configuration settings as returned by `_config`.
            **kwargs: Additional arguments for initialization.

        Returns:
            A new instance of the class.
        """
        raise NotImplementedError

    # ========== Optional or default implementations ==========
    def get(self, key: _KT, default: Any = None) -> Any:
        """Safely retrieves a value by key.

        Args:
            key: The key to look up.
            default: The value to return if the key is not found. Defaults to None.

        Returns:
            The value associated with the key, or the default value.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[_KT, Any]:
        """Recursively convert the hierarchical mapping into a standard dictionary.

        Returns:
            A nested dictionary representation of the mapping.
        """
        return {
            k: (v.to_dict() if isinstance(v, LattixMapping) else v)
            for k, v in self.items()
        }

    def __contains__(self, key: Any) -> bool:
        """Check if a key exists in the mapping.

        Args:
            key: The key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        try:
            self[key]
            return True
        except KeyError:
            return False

    @staticmethod
    def _valid_name(name: str) -> bool:
        """Validate if a string is a valid Python identifier for attribute access.

        Args:
            name: The string to validate.

        Returns:
            True if the name is a valid ASCII identifier, False otherwise.
        """
        return bool(name and _ASCII_ATTR_RE.match(name))


class MutableLattixMapping(LattixMapping[_KT, _VT], MutableMapping[_KT, _VT]):
    """Abstract base class for mutable hierarchical mappings.

    Extend LattixMapping with methods for modification, deletion, and
    recursive merging.
    """

    # ========== Required mutation interface ==========
    @abstractmethod
    def __setitem__(self, key: _KT, value: _VT) -> None: ...
    @abstractmethod
    def __delitem__(self, key: _KT) -> None: ...

    # ========== Optional convenience methods ==========
    def merge(
        self, other: MutableMapping[_KT, _VT], overwrite: bool = True
    ) -> MutableLattixMapping[_KT, _VT]:
        """Recursively merge another mapping into this one.

        Args:
            other: The mapping to merge into the current instance.
            overwrite: Whether to overwrite existing non-mapping values.
                Defaults to True.

        Returns:
            The current instance after merging.

        Raises:
            TypeError: If the 'other' argument is not a mapping.
        """
        if not isinstance(other, Mapping):
            raise TypeError(f"Expected map-like, got {type(other).__name__!r}")

        for k, v in other.items():
            if (
                k in self
                and isinstance(self[k], MutableMapping)
                and isinstance(v, Mapping)
            ):
                self[k].merge(v, overwrite)
            elif overwrite or k not in self:
                self[k] = v
        return self
