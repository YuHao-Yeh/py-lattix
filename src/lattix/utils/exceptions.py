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


from typing import Any
from .types import TupleType


# ──────────────────────────────
# Helper
# ──────────────────────────────
def _format_types(t: type | str | tuple[type, ...]) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, tuple):
        return " | ".join(tp.__name__ for tp in t)
    return t.__name__


# ──────────────────────────────
# Import Exceptions
# ──────────────────────────────
class PackageImportError(ImportError):
    """Base class for optional dependency import errors."""
    pass

class OptionalImportError(PackageImportError):
    """Raised when a package is not installed."""
    def __init__(self, package: str, purpose: str | None = None, extra: str | None = None):
        msg = f"Optional dependency '{package}' is not installed."
        if purpose:
            msg += f" Required for {purpose}."
        if extra:
            msg += f" Install via: `pip install {extra}`"
        super().__init__(msg)


# ──────────────────────────────
# Thread Safety Exceptions
# ──────────────────────────────
class ThreadingError(Exception):
    """Base class for all threading-related errors."""
    pass

class LockExistenceError(ThreadingError, RuntimeError):
    """Raised when a ThreadingMixin object holds its own locks."""
    def __init__(self):
        super().__init__(
            "Cannot attach: this subtree holds locks. Call `detach(clear_locks=True)`."
        )


# ──────────────────────────────
# Node Exceptions
# ──────────────────────────────
class NodeError(Exception):
    """Base class for node-related errors."""
    pass

class UnattachableError(NodeError, ValueError):
    """Raised when a node is already attached."""
    def __init__(self):
        super().__init__(
            "Cannot attach: this node is not detached or already attached."
        )

class UnexpectedNodeError(NodeError, TypeError):
    """Raised when a node is not an expected instance."""
    def __init__(self, node_key: str, val: Any = None):
        super().__init__(f"Unexpected node at {node_key!r} (type={type(val).__name__}).")


# ──────────────────────────────
# Payload Exceptions
# ──────────────────────────────
class PayloadError(Exception):
    """Base class for input validation errors."""
    pass

class UnsupportedPayloadError(PayloadError, TypeError):
    def __init__(self, func: str, value: Any, ideal: type | str | TupleType[type, ...]):
        super().__init__(
            f"Unsupported payload type for '{func}()': '{type(value).__name__}', "
            f"expected {_format_types(ideal)}."
        )

class InvalidPayloadError(PayloadError, ValueError):
    """Raised when invalid payload value occurred."""
    def __init__(self, value: Any, target: str):
        super().__init__(f"Invalid {target} payload: {value!r}")

class ArgTypeError(PayloadError, TypeError):
    def __init__(self, arg: str, value: Any, ideal_type: type | str | TupleType[type, ...], func: str | None = None):
        msg = f"Expected {_format_types(ideal_type)} for "
        if func:
            msg += f"'{func}()' argument "
        msg += f"'{arg}', got '{type(value).__name__}'."
        super().__init__(msg)


# ──────────────────────────────
# Internal Access Exceptions
# ──────────────────────────────
class InternalAccessError(Exception):
   """Base class for internal access violations."""
   pass

class InvalidAttributeNameError(InternalAccessError, ValueError):
    """Raised when attribute name is invalid."""
    def __init__(self, name: str):
        super().__init__(f"Invalid attribute name: {name!r}")

class AttributeAccessDeniedError(InternalAccessError, AttributeError):
    """Raised when dot-access attributes are not allowed."""
    def __init__(self, name: str, cause: str | None = None):
        msg = f"Cannot access internal attribute '{name}'."
        if cause:
            msg += cause
        super().__init__(msg)

class AttributeNotFoundError(InternalAccessError, AttributeError):
    """Raised when an attribute does not exist and lazy creation is disabled."""
    def __init__(self, name: str):
        super().__init__(
            f"No such attribute: {name!r}. "
            "Initialize with `lazy_create=True` to enable dynamic attribute creation."
        )

class ModificationDeniedError(InternalAccessError, TypeError):
    """Raised when modification is forbidden."""
    def __init__(self, cls: str | type):
        super().__init__(f"{_format_types(cls)} is frozen and cannot be modified.")


# ──────────────────────────────
# Key Exceptions
# ──────────────────────────────
class KeyPathError(KeyError):
    """Base exception for all key/path-related errors."""
    pass

class KeyNotFoundError(KeyPathError):
    """Raised when a key does not exist."""
    def __init__(self, key: str):
        super().__init__(f"Key not found: {key!r}")

class PathNotFoundError(KeyPathError):
    """Raised when a key is missing within a specific hierarchical path."""
    def __init__(self, key: str, path: str):
        super().__init__(f"Missing key {key!r} in path {path!r}")

class DuplicatedKeyError(KeyPathError):
    """Raised when a key is already exist."""
    def __init__(self, key: str):
        super().__init__(f"Parent already has a child with key {key!r}")


# ──────────────────────────────
# Operator Exceptions
# ──────────────────────────────
class OperationError(Exception):
    """Base exception for operation violations."""
    pass

class OperandTypeError(OperationError, TypeError):
    """Raised when unsupported operand types are used with an operator."""
    def __init__(self, operand_a: Any, operand_b: Any, operator: str):
        a_name = type(operand_a).__name__
        b_name = type(operand_b).__name__
        super().__init__(
            f"Unsupported operand type(s) for {operator}: '{a_name}' and '{b_name}'"
        )

class UnsupportedOperatorError(OperationError, ValueError):
    """Raised when unsupported operator types are used."""
    def __init__(self, operator: str):
        super().__init__(f"Unsupported opertor type(s) for {operator}")