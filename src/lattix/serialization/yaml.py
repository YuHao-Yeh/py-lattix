"""Secure and extensible YAML parsing for Lattix.

This module extends PyYAML's ``SafeLoader`` and ``SafeDumper`` to provide a
highly secure yet flexible YAML parsing system. It maintains the security
integrity of standard safe loading while adding native support for common
Python data types that are typically omitted from safe schemas.

Supported Extended Types:
    * collections: ``tuple``, ``set``, ``frozenset``
    * math/finance: ``decimal.Decimal``, ``complex``
    * filesystem: ``pathlib.Path``
    * temporal: ``datetime.datetime``

Security Comparison:
    +-----------------+----------+------------------+-------+-----------------+
    | Method          | Security | Supported Types  | RCE?  | Recommended Use |
    +=================+==========+==================+=======+=================+
    | yaml.safe_load  | High     | Basic YAML types | No    | General configs |
    +-----------------+----------+------------------+-------+-----------------+
    | yaml.load       | Medium   | All Python types | Yes   | Trusted sources |
    +-----------------+----------+------------------+-------+-----------------+
    | Lattix load()   | High     | Extended Set     | No    | Safe type apps  |
    +-----------------+----------+------------------+-------+-----------------+

Security Warning:
    Never use ``yaml.FullLoader`` or ``yaml.UnsafeLoader`` on untrusted data.
    These loaders can execute arbitrary Python code, leading to Remote Code
    Execution (RCE) vulnerabilities. Lattix provides ``load()`` as a secure,
    type-aware alternative.

Example:
    >>> from lattix.serialization.yaml import load, dump

    >>> yaml_str = '''
    ... a: !tuple [1, 2, 3]
    ... b: !set [banana]
    ... c: !decimal "12.34"
    ... d: !datetime "2025-10-27T05:30:00"
    ... '''

    >>> data = load(yaml_str)
    >>> data
    {'a': (1, 2, 3), 'b': {'banana'}, 'c': Decimal('12.34'), 'd': datetime.datetime(2025, 10, 27, 5, 30)}

    >>> print(dump(data))
    a: !tuple [1, 2, 3]
    b: !set [banana]
    c: !decimal '12.34'
    d: !datetime '2025-10-27T05:30:00'
    <BLANKLINE>

"""

from __future__ import annotations

import datetime
import decimal
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..utils import compat
from ..utils.exceptions import OptionalImportError

if TYPE_CHECKING:
    from typing import IO, TypeVar

    from yaml import Dumper, Loader, SafeDumper, SafeLoader
    from yaml.nodes import Node, ScalarNode, SequenceNode

    _T = TypeVar("_T")
    _NodeT = TypeVar("_NodeT", bound=Node)
    Representer = Callable[["EnhancedSafeDumper", _T], Node]
    Constructor = Callable[["EnhancedSafeLoader", _NodeT], _T]

__all__ = [
    "EnhancedSafeLoader",
    "EnhancedSafeDumper",
    "register_type",
    "load",
    "dump",
    "inspect_registry",
]


# ======================================================
# Conditional Definition (Handling missing PyYAML)
# ======================================================
HAS_YAML = compat.HAS_YAML
yaml = compat.yaml

if HAS_YAML:
    Dumper = yaml.Dumper
    Loader = yaml.Loader
    SafeDumper = yaml.SafeDumper
    SafeLoader = yaml.SafeLoader

    Node = yaml.nodes.Node
    ScalarNode = yaml.nodes.ScalarNode
    SequenceNode = yaml.nodes.SequenceNode
else:
    # Dummy classes to prevent ImportsErrors during definition
    class Node:
        pass

    class ScalarNode(Node):
        pass

    class SequenceNode(Node):
        pass

    class Loader:
        def __init__(self, stream=None):
            self.stream = stream

        @classmethod
        def add_constructor(cls, tag, constructor):
            pass

        def construct_scalar(self, node):
            return ""

        def construct_sequence(self, node, deep=False):
            return []

        def construct_mapping(self, node, deep=False):
            return {}

    class SafeLoader(Loader): ...

    class Dumper:
        def __init__(self, stream=None):
            self.stream = stream

        @classmethod
        def add_representer(cls, data_type, representer):
            pass

        @classmethod
        def add_multi_representer(cls, data_type, representer) -> None:
            pass

        def represent_scalar(self, tag, value, style=None):
            return ScalarNode()

        def represent_sequence(self, tag, sequence, flow_style=None):
            return SequenceNode()

        def represent_mapping(self, tag, mapping, flow_style=None):
            return Node()

    class SafeDumper(Dumper): ...


def _require_yaml() -> None:
    if not HAS_YAML or not yaml:
        raise OptionalImportError("PyYAML", "YAML support", "pyyaml")


# ======================================================
# Enhanced Safe Loader / Dumper
# ======================================================
class EnhancedSafeLoader(SafeLoader):
    """Custom SafeLoader with extended Python type support.

    This loader reconstructs extended Python data types (e.g., Path, Decimal,
    datetime, complex) while maintaining the security guarantees of the
    standard SafeLoader by restricting reconstruction to a known allow-list.

    Example:
        >>> data = yaml.load("path: !path '/tmp/test.txt'", Loader=EnhancedSafeLoader)
        >>> isinstance(data["path"], Path)
        True
    """

    _enhanced_registered: bool = False


class EnhancedSafeDumper(SafeDumper):
    """Custom SafeDumper with extended Python type support.

    This dumper enables the serialization of Python objects not natively
    supported by standard safe dumping. It also implements a hybrid
    indentation logic to improve the readability of nested collections.

    Supported types include ``Path``, ``tuple``, ``frozenset``, ``Decimal``,
    and ``datetime``.

    Example:
        >>> yaml.dump({"p": Path("/tmp")}, Dumper=EnhancedSafeDumper)
        "p: !path '/tmp'\\n"
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        """Ensures proper indentation levels for nested YAML structures."""
        try:
            return super().increase_indent(flow, indentless)
        except AttributeError:
            return None


# ======================================================
# Flow Style
# ======================================================
_CONTAINER_TYPES: tuple[type, ...] = (dict, list, tuple, set, frozenset)
_MAX_FLOW_LEN: int = 10


def _should_use_flow_style(
    dumper: EnhancedSafeDumper, data: Any, items_to_check: Any
) -> bool:
    """Heuristic to determine if a collection should be rendered inline.

    To maximize readability, Lattix uses 'Block' style for large or
    nested collections and 'Flow' (inline) style for small, flat
    collections.

    Args:
        dumper: The active dumper instance.
        data: The collection object being inspected.
        items_to_check: The elements within the collection.

    Returns:
        bool: True if Flow style should be used, False for Block style.
    """
    # 1. Top-level objects should always be Block for readability
    represented_map = getattr(dumper, "represented_objects", {})
    if not represented_map:
        return False

    # 2. Large collections should be Block style
    if len(data) > _MAX_FLOW_LEN:
        return False

    # 3. If the collection contains other collections, use Block style
    return all(not isinstance(v, _CONTAINER_TYPES) for v in items_to_check)


# ======================================================
# Default Converters
# ======================================================
# - CON
# bool -> bool
# bytes -> bytes
# complex -> complex
# dict -> map
# float -> float
# int -> int
# list -> seq
# long -> long
# none -> null
# str -> str
# tuple -> tuple
# unicode -> unicode

# - REP
# function -> name
# builtin_function_or_method -> name
# module -> module
# collections.OrderedDict -> ordered_dict


# Helper to bypass PyYAML incomplete stubs
def _rep_scalar(
    dumper: EnhancedSafeDumper, tag: str, value: str, style: str | None = None
) -> ScalarNode:
    # Use cast(Any, ...) because Pylance reports represent_scalar as Unknown member
    return cast(Any, dumper).represent_scalar(tag, value, style)


# ========== Mapping ==========
# 1. dict
def _represent_dict(dumper: EnhancedSafeDumper, data: dict[Any, Any]) -> Node:
    """Represent dict with hybrid style (flow for flat, block for nested)."""
    use_flow = _should_use_flow_style(dumper, data, data.values())
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=use_flow)


# ========== Sequence ==========
# 1. list
def _represent_list(dumper: EnhancedSafeDumper, data: list[Any]) -> Node:
    """Represent list with hybrid style (flow for flat, block for nested)."""
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=use_flow)


# 2. tuple
def _construct_tuple(loader: EnhancedSafeLoader, node: SequenceNode) -> tuple[Any, ...]:
    return tuple(loader.construct_sequence(node))


def _represent_tuple(dumper: EnhancedSafeDumper, data: tuple[Any, ...]) -> SequenceNode:
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence("!tuple", list(data), flow_style=use_flow)


# 3. set
def _construct_set(loader: EnhancedSafeLoader, node: SequenceNode) -> set[Any]:
    return set(loader.construct_sequence(node))


def _represent_set(dumper: EnhancedSafeDumper, data: set[Any]) -> SequenceNode:
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence("!set", list(data), flow_style=use_flow)


# 4. frozenset
def _construct_frozenset(
    loader: EnhancedSafeLoader, node: SequenceNode
) -> frozenset[Any]:
    return frozenset(loader.construct_sequence(node))


def _represent_frozenset(
    dumper: EnhancedSafeDumper, data: frozenset[Any]
) -> SequenceNode:
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence("!frozenset", list(data), flow_style=use_flow)


# ========== Scalar ==========
# 1. complex
def _construct_complex(loader: EnhancedSafeLoader, node: ScalarNode) -> complex:
    value = loader.construct_scalar(node)
    return complex(value.replace(" ", ""))


def _represent_complex(dumper: EnhancedSafeDumper, data: complex) -> ScalarNode:
    real, imag = data.real, data.imag
    value = f"{real} + {imag}j" if imag >= 0 else f"{real} - {abs(imag)}j"
    return _rep_scalar(dumper, "!complex", value)


# 2. decimal
def _construct_decimal(loader: EnhancedSafeLoader, node: ScalarNode) -> decimal.Decimal:
    return decimal.Decimal(loader.construct_scalar(node))


def _represent_decimal(dumper: EnhancedSafeDumper, data: decimal.Decimal) -> ScalarNode:
    return _rep_scalar(dumper, "!decimal", str(data))


# 3. datetime
def _construct_datetime(
    loader: EnhancedSafeLoader, node: ScalarNode
) -> datetime.datetime:
    return datetime.datetime.fromisoformat(loader.construct_scalar(node))


def _represent_datetime(
    dumper: EnhancedSafeDumper, data: datetime.datetime
) -> ScalarNode:
    return _rep_scalar(dumper, "!datetime", data.isoformat())


# 4. path
def _construct_path(loader: EnhancedSafeLoader, node: ScalarNode) -> Path:
    return Path(loader.construct_scalar(node))


def _represent_path(dumper: EnhancedSafeDumper, data: Path) -> ScalarNode:
    # Always use posix seperators (/) for YAML portability
    return _rep_scalar(dumper, "!path", data.as_posix())


# ======================================================
# Registration API
# ======================================================
def register_type(
    tag: str,
    typ: type[Any],
    representer: Representer[Any],
    constructor: Constructor[_NodeT, _T],
) -> None:
    """Registers a custom Python type for YAML serialization and parsing.

    This function updates the global registries for both
    ``EnhancedSafeDumper`` and ``EnhancedSafeLoader``.

    Args:
        tag: The YAML tag string (e.g., '!my_type').
        typ: The Python class to associate with the tag.
        representer: A callable that converts a Python object to a YAML node.
        constructor: A callable that converts a YAML node back to a
            Python object.

    Example:
        >>> from decimal import Decimal
        >>> _rep_decimal = _represent_decimal
        >>> _cons_decimal = _construct_decimal
        >>> register_type('!decimal', Decimal, _rep_decimal, _cons_decimal)
    """
    if not HAS_YAML:
        return

    # Register Dumper (handle subclass ingeritance checks)
    try:
        if issubclass(typ, Path):
            EnhancedSafeDumper.add_multi_representer(typ, representer)
        else:
            EnhancedSafeDumper.add_representer(typ, representer)
    except TypeError:
        # Fallback for types that might not support issubclass cleanly
        EnhancedSafeDumper.add_representer(typ, representer)

    # Register Loader
    EnhancedSafeLoader.add_constructor(tag, constructor)


# ======================================================
# Initial Registration
# ======================================================
def _ensure_enhanced_registered(force: bool = False) -> None:
    """Internal helper to bootstrap the enhanced YAML registry.

    This function performs the initial setup of the :class:`EnhancedSafeLoader`
    and :class:`EnhancedSafeDumper`. It registers the custom representers for
    base types (dict, list) to support hybrid styling and defines the
    constructors and representers for the extended Python type set
    (e.g., ``tuple``, ``set``, ``Path``, ``Decimal``).

    The function uses an internal flag to ensure that registration only
    occurs once unless forced, preventing redundant overhead or
    clobbering of manual registrations.

    Args:
        force: If True, ignores the internal ``_enhanced_registered`` flag
            and re-executes the registration logic. Defaults to False.

    Note:
        This function is called automatically at the module level when
        ``yaml.py`` is imported, provided that PyYAML is installed.
    """
    if not HAS_YAML:
        return

    if force or not getattr(EnhancedSafeLoader, "_enhanced_registered", False):
        # 1. Built-in hybrid types
        EnhancedSafeDumper.add_representer(dict, _represent_dict)
        EnhancedSafeDumper.add_representer(list, _represent_list)

        # 2. Custom extensions
        _builtin_types: list[tuple[str, type[Any], Any, Any]] = [
            ("!tuple", tuple, _represent_tuple, _construct_tuple),
            ("!set", set, _represent_set, _construct_set),
            ("!frozenset", frozenset, _represent_frozenset, _construct_frozenset),
            ("!complex", complex, _represent_complex, _construct_complex),
            ("!decimal", decimal.Decimal, _represent_decimal, _construct_decimal),
            ("!datetime", datetime.datetime, _represent_datetime, _construct_datetime),
            ("!path", Path, _represent_path, _construct_path),
        ]

        for tag, typ, rep, cons in _builtin_types:
            register_type(tag, typ, rep, cons)

        EnhancedSafeLoader._enhanced_registered = True
    return


# Auto-register on import if YAML exists
_ensure_enhanced_registered(force=True)


# ======================================================
# Public API
# ======================================================
def load(stream: str | bytes | IO[str] | IO[bytes], encoding: str = "utf-8"):
    """Safely parse a YAML stream into Python objects with extended type support.

    This is the primary entry point for secure loading in Lattix.

    Args:
        stream: The YAML source string, bytes, or file-like object.
        encoding: The text encoding to use if bytes are provided.
            Defaults to "utf-8".

    Returns:
        Any: The reconstructed Python object (typically a dict or list).

    Example:
        >>> yaml_str = "a: !tuple [1, 2, 3]"
        >>> load(yaml_str)
        {'a': (1, 2, 3)}
    """
    _require_yaml()

    if isinstance(stream, bytes):
        stream = stream.decode(encoding)

    return yaml.load(stream, Loader=EnhancedSafeLoader)


def dump(data: Any, stream: IO[str] | None = None, **kwargs: Any) -> str | None:
    """Serialize a Python object to YAML with extended type support.

    By default, this function uses Block style for readability and
    automatically handles complex types like Paths and Decimals.

    Args:
        data: The Python object to serialize.
        stream: An optional file-like object to write to.
        **kwargs: Arguments passed to ``yaml.dump``.
            Note: The 'Dumper' argument is forced to ``EnhancedSafeDumper``.

    Returns:
        Optional[str]: The YAML string if stream is None, otherwise None.

    Example:
        >>> from pathlib import Path
        >>> dump({"path": Path("/tmp/test.txt")})
        "path: !path '/tmp/test.txt'\\n"
    """
    _require_yaml()

    # Prevent caller from overriding the Dumper
    kwargs.pop("Dumper", None)

    # Set safe defaults if not provided
    kwargs.setdefault("default_flow_style", False)
    kwargs.setdefault("indent", 2)
    kwargs.setdefault("allow_unicode", True)
    kwargs.setdefault("sort_keys", False)

    if stream is not None:
        yaml.dump(data, stream, EnhancedSafeDumper, **kwargs)
        return None

    result = yaml.dump(data, None, EnhancedSafeDumper, **kwargs)
    return result.rstrip() + "\n"


def inspect_registry(verbose: bool = True) -> dict[str, list[Any]]:
    """Returns a summary of currently registered YAML tags and handlers.

    Useful for debugging custom type registrations and verifying the
    internal state of the Enhanced loaders/dumpers.

    Args:
        verbose: If True, prints the registry details to stdout.
            Defaults to True.

    Returns:
        dict: A dictionary containing lists of registered representers
            and constructors.
    """
    record: dict[str, list[Any]] = {
        "Representer keys": list(),
        "Multi-Representer keys": list(),
        "Constructor keys": list(),
    }

    if not HAS_YAML:
        return record

    record["Representer keys"] = list(EnhancedSafeDumper.yaml_representers.keys())
    record["Multi-Representer keys"] = list(
        EnhancedSafeDumper.yaml_multi_representers.keys()
    )
    record["Constructor keys"] = list(EnhancedSafeLoader.yaml_constructors.keys())

    if verbose:
        for k, v in record.items():
            print(k)
            for keys in v:
                print(" ", keys)

    return record
