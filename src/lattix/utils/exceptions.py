__all__ = [
   # Import Exceptions
   "PackageImportError",
   "NoPyYAMLError",
   # Threading
   "ThreadingError",
   "ThreadSafetyLevelTypeError",
   "ThreadSafetyLevelValueError",
   "ThreadingObjectTypeError",
   "UnattachableError",
   "LockExistenceError",
   # Input Exceptions
   "InvalidPayloadError",
   "InvalidJSONTypeError",
   "InvalidJSONValueError",
   "InvalidYAMLValueError",
   "NonPairIterableError",
   "ArgTypeError",
   # Internal Access
   "InternalAccessError",
   "InvalidAttributeNameError",
   "InternalAttributeError",
   "ReservedNameConflictError",
   "MissingAttributeError",
   # Key Exceptions
   "KeyPathError",
   "KeyNotFoundError",
   "PathNotFoundError",
   "DuplicatedKeyError",
   "UnexpectedNodeTypeError",
   # Operators
   "OperandTypeError",
]


from typing import Any


# ──────────────────────────────
# Import Exceptions
# ──────────────────────────────
class PackageImportError(ImportError):
   """Base class for all package import errors."""
   pass

class NoPyYAMLError(PackageImportError):
   """Raised when PyYAML is not installed."""
   def __init__(self):
      super().__init__(
         "PyYAML not installed; cannot use YAML support."
         "Please install it via 'pip install pyyaml'."
      )


# ──────────────────────────────
# Thread Safety Level Exceptions
# ──────────────────────────────
class ThreadingError(Exception):
   """Base class for all threading-related errors."""

# --- Argument Validation Errors ---
class ThreadSafetyLevelTypeError(ThreadingError, TypeError):
   """Raised when ts_level is not an integer."""
   def __init__(self, value: Any):
      super().__init__(
         f"Invalid type for ts_level ({type(value).__name__})."
         "Expected int (0, 1, 2)."
      )

class ThreadSafetyLevelValueError(ThreadingError, ValueError):
   """Raised when ts_level has an invalid integer value."""
   def __init__(self, value: Any):
      super().__init__(
         f"Invalid value for ts_level ({value!r})."
         "Must be 0, 1, or 2."
      )

class ThreadingObjectTypeError(ThreadingError, TypeError):
   """Raised when a non-ThreadingMixin object is passed where one is required."""
   def __init__(self, name: str, value: Any):
      typename = type(value).__name__ if value is not None else "NoneType"
      super().__init__(
         f"Invalid type for '{name}' ({typename})."
         "Expected a ThreadingMixin instance."
      )

# --- State Errors (No dynamic data needed) ---
class UnattachableError(ThreadingError, RuntimeError):
   """Raised when a ThreadingMixin object is already attached."""
   def __init__(self):
      super().__init__(
         "Cannot attach: this node is not detached or already attached."
      )

class LockExistenceError(ThreadingError, RuntimeError):
   """Raised when a ThreadingMixin object holds its own locks."""
   def __init__(self):
      super().__init__(
         "Cannot attach: this subtree holds locks. Call detach(clear_locks=True)."
      )


# ──────────────────────────────
# Payload Exceptions
# ──────────────────────────────
class InvalidPayloadError(ValueError):
   """Base class for input validation errors."""
   pass

class InvalidJSONTypeError(InvalidPayloadError, TypeError):
   """Raised when unsupported type encountered during JSON parsing."""
   def __init__(self, data: Any):
      typename = type(data).__name__ if data is not None else "NoneType"
      super().__init__(f"Unsupported input type for from_json: {typename}")

class InvalidJSONValueError(InvalidPayloadError):
   """Raised when invalid JSON value occurred."""
   def __init__(self, data: Any):
      super().__init__(f"Invalid JSON input: {data!r}")

class InvalidYAMLValueError(InvalidPayloadError):
   """Raised when invalid YAML value occurred."""
   def __init__(self, data: Any):
      super().__init__(f"Invalid YAML input: {data!r}")

class NonPairIterableError(InvalidPayloadError, TypeError):
   def __init__(self, func: str, actual_type: Any):
      super().__init__(
         f"'{func}()' iterable items must be (key, value) pairs. "
         f"Got: {actual_type!r}"
      )

class ArgTypeError(InvalidPayloadError, TypeError):
   def __init__(self, func: str, arg_name: str, expected_type: str, actual_type: str):
      super().__init__(
         f"Expected {expected_type} for '{func}()' argument '{arg_name}', "
         f"got '{actual_type}'"
      )


# ──────────────────────────────
# Internal Access Exceptions
# ──────────────────────────────
class InternalAccessError(AttributeError):
   """Base class for internal access violations."""
   pass

class InvalidAttributeNameError(InternalAccessError):
   """Raised when attribute name is invalid."""
   def __init__(self, name: str):
      super().__init__(f"Invalid attribute name: {name!r}")

class InternalAttributeError(InternalAccessError):
   """Raised when accessing internal attribute directly."""
   def __init__(self, name: str):
      super().__init__(f"Cannot access internal attribute {name!r}")

class ReservedNameConflictError(InternalAccessError):
   """Raised when using reserved internal name via dot-access."""
   def __init__(self, name: str):
      super().__init__(
         f"'{name}' is a reserved internal name; "
         f"use d[{name!r}] instead of d.{name}"
      )

class MissingAttributeError(InternalAccessError):
   """Raised when an attribute does not exist and lazy creation is disabled."""
   def __init__(self, name: str):
      super().__init__(
         f"No such attribute: {name!r}. "
         "Initialize with `lazy_create=True` to enable dynamic attribute creation."
      )


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

class UnexpectedNodeTypeError(KeyPathError, TypeError):
   """Raised when a node in the path is not an expected instance."""
   def __init__(self, node_key: str, val: Any = None):
      type_name = type(val).__name__
      super().__init__(f"Unexpected node at {node_key!r} (type={type_name}).")


# ──────────────────────────────
# Operator Exceptions
# ──────────────────────────────
class OperandTypeError(TypeError):
   """Raised when unsupported operand types are used with an operator."""
   def __init__(self, operand_a: Any, operand_b: Any, operator: str):
      a_name = type(operand_a).__name__
      b_name = type(operand_b).__name__
      super().__init__(
         f"Unsupported operand type(s) for {operator}: '{a_name}' and '{b_name}'"
      )
