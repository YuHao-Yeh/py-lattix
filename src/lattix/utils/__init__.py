"""Internal utility toolset for the Lattix library.

This package consolidates the functional infrastructure required to support
hierarchical mapping, thread synchronization, and data serialization. It
provides a unified interface for type introspection, recursive data
transformation, and environment compatibility.

The utilities are organized into several specialized areas:
    * **Introspection**: Tools for identifying scalar vs. container types.
    * **Transformation**: Logic for deep conversion, flattening, and serialization.
    * **Path Parsing**: Optimized string-to-tuple parsing for tree traversal.
    * **Compatibility**: Management of optional dependencies (NumPy, Pandas, etc.).
    * **Text**: ANSI escape sequence handling for clean logging and display.

All core utility functions are exposed directly at this package level for
convenient internal use across the library.
"""

from . import compat, constant, exceptions, inspection, path, text, transform, types
from .compat import get_module, has_module
from .constant import DFLT_INDENT_OFFSET, DFLT_INDENT_WIDTH, DFLT_SEP
from .inspection import is_primitive, is_scalar, scan_class_attrs
from .path import split_path
from .text import strip_ansi
from .transform import deep_convert, flatten, serialize, unflatten

__all__ = [
    # Compat
    "compat",
    "get_module",
    "has_module",
    # Constant
    "constant",
    "DFLT_INDENT_OFFSET",
    "DFLT_INDENT_WIDTH",
    "DFLT_SEP",
    # Inspection
    "inspection",
    "is_primitive",
    "is_scalar",
    "scan_class_attrs",
    # Path
    "path",
    "split_path",
    # Text
    "text",
    "strip_ansi",
    # Transform
    "transform",
    "deep_convert",
    "serialize",
    "flatten",
    "unflatten",
    # Exceptions
    "exceptions",
    # Types
    "types",
]
