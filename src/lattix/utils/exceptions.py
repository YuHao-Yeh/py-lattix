"""Custom exception hierarchy for Lattix.

This module defines a structured hierarchy of exceptions used throughout the
library to signal specific logical errors. By using specialized exception
types, Lattix allows users to implement fine-grained error handling for
operations involving hierarchical paths, thread synchronization, and
data validation.

The hierarchy is organized into the following categories:
    * **Import Exceptions**: Issues with optional third-party dependencies.
    * **Threading Exceptions**: Violations of the lock-inheritance model.
    * **Node Exceptions**: Structural errors in the tree hierarchy.
    * **Payload Exceptions**: Data validation and type errors.
    * **Internal Access Exceptions**: Violations of attribute-access rules.
    * **Key/Path Exceptions**: Missing or invalid keys and path strings.
    * **Operator Exceptions**: Unsupported types in logical set operations.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    # Import Exceptions
    "PackageImportError",
    "OptionalImportError",
    # Threading Exceptions
    "ThreadingError",
    "LockExistenceError",
    # Node Exceptions
    "NodeError",
    "UnattachableError",
    "UnexpectedNodeError",
    # Input Exceptions
    "PayloadError",
    "UnsupportedPayloadError",
    "InvalidPayloadError",
    "ArgTypeError",
    # Internal Access
    "InternalAccessError",
    "InvalidAttributeNameError",
    "AttributeAccessDeniedError",
    "AttributeNotFoundError",
    "ModificationDeniedError",
    # Key Exceptions
    "KeyPathError",
    "KeyNotFoundError",
    "PathNotFoundError",
    "DuplicatedKeyError",
    # Operators
    "OperationError",
    "OperandTypeError",
    "UnsupportedOperatorError",
]


# ======================================================
# Helper
# ======================================================
def _format_types(t: type | str | tuple[type, ...]) -> str:
    """Format a type, string, or tuple of types into a readable string.

    Used for generating clear error messages showing expected vs actual types.

    Args:
        t: The type(s) to format.

    Returns:
        str: A string representation (e.g., "int | str").
    """
    if isinstance(t, str):
        return t
    if isinstance(t, tuple):
        return " | ".join(tp.__name__ for tp in t)
    return t.__name__


# ======================================================
# Import Exceptions
# ======================================================
class PackageImportError(ImportError):
    """Base class for optional dependency import errors."""


class OptionalImportError(PackageImportError):
    """Raised when an optional third-party package is not installed."""

    def __init__(
        self, package: str, purpose: str | None = None, extra: str | None = None
    ):
        """Initialize the exception with helpful installation instructions.

        Args:
            package: The name of the missing package.
            purpose: A description of the feature that requires the package.
            extra: The pip-installable name (e.g., 'py-lattix[full]').
        """
        msg = f"Optional dependency '{package}' is not installed."
        msg += f" Required for {purpose}." if purpose else ""
        msg += f" Install via: `pip install {extra}`" if extra else ""
        super().__init__(msg)


# ======================================================
# Thread Safety Exceptions
# ======================================================
class ThreadingError(Exception):
    """Base class for all threading-related errors."""


class LockExistenceError(ThreadingError, RuntimeError):
    """Raised when a ThreadingMixin object holds its own locks during attachment."""

    def __init__(self):
        super().__init__(
            "Cannot attach: this subtree holds locks. Call `detach(clear_locks=True)`."
        )


# ======================================================
# Node Exceptions
# ======================================================
class NodeError(Exception):
    """Base class for node-related errors."""


class UnattachableError(NodeError, ValueError):
    """Raised when a node cannot be attached because it is already linked."""

    def __init__(self):
        super().__init__(
            "Cannot attach: this node is not detached or already attached."
        )


class UnexpectedNodeError(NodeError, TypeError):
    """Raised when a node type at a path does not match the expected structure."""

    def __init__(self, node_key: str, val: Any = None):
        """Initialize the error with the location and actual type found.

        Args:
            node_key: The key or path where the unexpected node was found.
            val: The actual value found at that location.
        """
        super().__init__(
            f"Unexpected node at {node_key!r} (type={type(val).__name__})."
        )


# ======================================================
# Payload Exceptions
# ======================================================
class PayloadError(Exception):
    """Base class for input validation and data payload errors."""


class UnsupportedPayloadError(PayloadError, TypeError):
    """Raised when an operation is attempted with an invalid data type."""

    def __init__(self, func: str, value: Any, ideal: type | str | tuple[type, ...]):
        """Initialize the error with function context and type details.

        Args:
            func: Name of the function where the error occurred.
            value: The invalid value provided.
            ideal: The expected type(s).
        """
        super().__init__(
            f"Unsupported payload type for '{func}()': '{type(value).__name__}', "
            f"expected {_format_types(ideal)}."
        )


class InvalidPayloadError(PayloadError, ValueError):
    """Raised when a payload value is syntactically valid but logically invalid."""

    def __init__(self, value: Any, target: str):
        """Initialize the error.

        Args:
            value: The invalid value.
            target: The format or target (e.g., 'JSON', 'YAML').
        """
        super().__init__(f"Invalid {target} payload: {value!r}")


class ArgTypeError(PayloadError, TypeError):
    """Raised when a function argument does not match the expected type."""

    def __init__(
        self,
        arg: str,
        value: Any,
        ideal_type: type | str | tuple[type, ...],
        func: str | None = None,
    ):
        """Initialize the error.

        Args:
            arg: Name of the argument.
            value: The actual value passed.
            ideal_type: The expected type(s).
            func: Optional function name.
        """
        msg = f"Expected {_format_types(ideal_type)} for "
        msg += f"'{func}()' argument " if func else ""
        msg += f"'{arg}', got '{type(value).__name__}'."
        super().__init__(msg)


# ======================================================
# Internal Access Exceptions
# ======================================================
class InternalAccessError(Exception):
    """Base class for violations of Lattix internal access rules."""


class InvalidAttributeNameError(InternalAccessError, ValueError):
    """Raised when a string is not a valid Python identifier for attribute access."""

    def __init__(self, name: str):
        super().__init__(f"Invalid attribute name: {name!r}")


class AttributeAccessDeniedError(InternalAccessError, AttributeError):
    """Raised when attempting to access or modify reserved internal attributes."""

    def __init__(self, name: str, cause: str | None = None):
        msg = f"Cannot access internal attribute '{name}'."
        msg += cause if cause else ""
        super().__init__(msg)


class AttributeNotFoundError(InternalAccessError, AttributeError):
    """Raised when dot-access fails and lazy creation is disabled."""

    def __init__(self, name: str):
        super().__init__(
            f"No such attribute: {name!r}. "
            "Initialize with `lazy_create=True` to enable dynamic attribute creation."
        )


class ModificationDeniedError(InternalAccessError, TypeError):
    """Raised when an operation attempts to modify a frozen Lattix node."""

    def __init__(self, cls: str | type):
        super().__init__(f"{_format_types(cls)} is frozen and cannot be modified.")


# ======================================================
# Key Exceptions
# ======================================================
class KeyPathError(KeyError):
    """Base exception for all key and hierarchical path errors."""


class KeyNotFoundError(KeyPathError):
    """Raised when a direct key is missing from a node."""

    def __init__(self, key: str):
        super().__init__(f"Key not found: {key!r}")


class PathNotFoundError(KeyPathError):
    """Raised when a segment of a hierarchical path string is missing."""

    def __init__(self, key: str, path: str):
        """Initialize the error.

        Args:
            key: The specific key that was not found.
            path: The full path string being traversed.
        """
        super().__init__(f"Missing key {key!r} in path {path!r}")


class DuplicatedKeyError(KeyPathError):
    """Raised when an attachment would overwrite an existing key in a parent."""

    def __init__(self, key: str):
        super().__init__(f"Parent already has a child with key {key!r}")


# ======================================================
# Operator Exceptions
# ======================================================
class OperationError(Exception):
    """Base exception for logical and binary operation violations."""


class OperandTypeError(OperationError, TypeError):
    """Raised when incompatible types are used with Lattix logical operators."""

    def __init__(self, operand_a: Any, operand_b: Any, operator: str):
        """Initialize the error.

        Args:
            operand_a: The left-hand side operand.
            operand_b: The right-hand side operand.
            operator: The string representation of the operator (e.g., '&').
        """
        a_name = type(operand_a).__name__
        b_name = type(operand_b).__name__
        super().__init__(
            f"Unsupported operand type(s) for {operator}: '{a_name}' and '{b_name}'"
        )


class UnsupportedOperatorError(OperationError, ValueError):
    """Raised when an operation is requested that the current class does not support."""

    def __init__(self, operator: str):
        super().__init__(f"Unsupported opertor type(s) for {operator}")
