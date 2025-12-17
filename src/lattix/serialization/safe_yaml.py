"""
safe_yaml.py — Secure and Extensible YAML Parsing Module
========================================================

This module extends PyYAML’s `SafeLoader` to provide a safer and more flexible
YAML parsing system through `load` and `dump`.

**Purpose**
-----------
- Maintain the same security level as `yaml.safe_load()`
- Support additional common Python data types
  (e.g., tuple, set, frozenset, Decimal, datetime, Path)
- Restrict unsafe object types to prevent arbitrary code execution.

**Comparison — YAML Loading Methods**
-------------------------------------

| Function Name | Security | Supported Types | Arbitrary Code | Recommended Use |
|----------------|-----------|------------------|----------------|-----------------|
| `yaml.safe_load` | ✅ High | Basic YAML types | ❌ No | General configs |
| `yaml.load(..., Loader=yaml.FullLoader)` | ⚠️ Medium | All Python objects | ⚠️ Yes | Trusted sources |
| `load` | ✅ High | Extended but controlled set | ❌ No | Safe type support |

**Security Warning**
--------------------
⚠️ **Never use** `yaml.FullLoader` or `yaml.UnsafeLoader` on untrusted data.
These can execute arbitrary code and lead to **RCE** (remote code execution).

✅ Recommended safe alternatives:
- `load()` — secure and type-aware YAML loading.
- `dump()` — safe dumping that preserves custom tags.

**Extensibility**
-----------------
You can register custom YAML tags safely:
    >>> def custom_func(loader, node): ...
    >>> EnhancedSafeLoader.add_constructor('!tag_name', custom_func)

**Example**
-----------
```python
from safe_yaml import load, dump

yaml_str = '''
a: !tuple [1, 2, 3]
b: !set [apple, banana]
c: !decimal "12.34"
d: !datetime "2025-10-27T05:30:00"
'''

data = load(yaml_str)
print(data)
# {'a': (1, 2, 3), 'b': {'apple', 'banana'},
#  'c': Decimal('12.34'), 'd': datetime.datetime(...)}

print(dump(data))
# a: !tuple [1, 2, 3]
# b: !set [apple, banana]
# c: !decimal '12.34'
# d: !datetime '2025-10-27T05:30:00'
"""
from __future__ import annotations

__all__ = [
    "EnhancedSafeLoader",
    "EnhancedSafeDumper",
    "register_type",
    "load",
    "dump",
    "inspect_registry",
]

from collections.abc import Callable
import datetime
import decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast


from ..utils.compat import HAS_YAML, yaml
from ..utils.exceptions import NoPyYAMLError

if TYPE_CHECKING:   # pragma: no cover
    from typing import TypeVar, IO
    from yaml import Dumper, Loader, SafeDumper, SafeLoader
    from yaml.nodes import Node, ScalarNode, SequenceNode
    from ..utils.types import DictType, ListType, SetType, TupleType, TypeType

    _T = TypeVar("_T")
    _NodeT = TypeVar("_NodeT", bound=Node)
    Representer = Callable[["EnhancedSafeDumper", _T], Node]
    Constructor = Callable[["EnhancedSafeLoader", _NodeT], _T]


# ======================================================
# Conditional Definition (Handling missing PyYAML)
# ======================================================

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
    class Node: pass
    class ScalarNode(Node): pass
    class SequenceNode(Node): pass
    
    class Loader:
        def __init__(self, stream=None):
            self.stream = stream
        @classmethod
        def add_constructor(cls, tag, constructor): pass
        def construct_scalar(self, node): return ""
        def construct_sequence(self, node, deep=False): return []
        def construct_mapping(self, node, deep=False): return {}
    class SafeLoader(Loader): ...

    class Dumper:
        def __init__(self, stream=None):
            self.stream = stream
        @classmethod
        def add_representer(cls, data_type, representer): pass
        @classmethod
        def add_multi_representer(cls, data_type, representer) -> None: pass
        def represent_scalar(self, tag, value, style=None): return ScalarNode()
        def represent_sequence(self, tag, sequence, flow_style=None): return SequenceNode()
        def represent_mapping(self, tag, mapping, flow_style=None): return Node()
        # def represent_object(self, data): return Node()
    class SafeDumper(Dumper): ...

def _require_yaml() -> None:
    if not HAS_YAML or not yaml:
        raise NoPyYAMLError


# ======================================================
# Enhanced Safe Loader / Dumper
# ======================================================

class EnhancedSafeLoader(SafeLoader):
    """Custom SafeLoader with extended Python type support.
    
    This loader reconstructs extended Python data types
    (e.g., `Path`, `Decimal`, `datetime`, `complex`) while maintaining
    YAML’s security guarantees.

    Parameters
    ----------
    yaml.SafeLoader : type
        The base PyYAML safe loader class to extend.

    Example
    -------
    >>> data = yaml.load("path: !path '/tmp/example.txt'", Loader=EnhancedSafeLoader)
    >>> isinstance(data["path"], Path)
    True
    >>> from pathlib import PurePath
    >>> str(PurePath(data["path"])).replace('\\\\', '/')
    '/tmp/example.txt'
    """
    _enhanced_registered: bool = False

class EnhancedSafeDumper(SafeDumper):
    """Custom SafeDumper with extended Python type support.
    
    This dumper allows serialization of objects that are not natively
    supported by `yaml.safe_dump`, such as:
    - `Path`
    - `tuple`
    - `frozenset`
    - `Decimal`
    - `datetime`

    Methods
    -------
    increase_indent(flow=False, indentless=False)
        Ensure proper indentation for nested collections.

    Example
    -------
    >>> yaml.dump({"path": Path("/tmp/example.txt")}, Dumper=EnhancedSafeDumper).rstrip()
    "path: !path '/tmp/example.txt'"
    """
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, indentless)


# ======================================================
# Flow Style
# ======================================================

_CONTAINER_TYPES: TupleType[TypeType, ...] = (dict, list, tuple, set, frozenset)
_MAX_FLOW_LEN: int = 10 

def _should_use_flow_style(dumper: EnhancedSafeDumper, data: Any, items_to_check: Any) -> bool:
    """Determine if a collection should be represented in Flow style (inline)."""
    
    # 1. Top-level objects should always be Block for readability
    represented_map = getattr(dumper, 'represented_objects', {})
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
# CON
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
def _rep_scalar(dumper: EnhancedSafeDumper, tag: str, value: str, style: str | None = None) -> ScalarNode:
    # Use cast(Any, ...) because Pylance reports represent_scalar as Unknown member
    return cast(Any, dumper).represent_scalar(tag, value, style)


# ---------- Mapping ----------
# 1. dict
def _represent_dict(dumper: EnhancedSafeDumper, data: DictType[Any, Any]) -> Node:
    """Represent dict with hybrid style (flow for flat, block for nested)."""
    use_flow = _should_use_flow_style(dumper, data, data.values())
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=use_flow)


# ---------- Sequence ----------
# 1. list
def _represent_list(dumper: EnhancedSafeDumper, data: ListType[Any]) -> Node:
    """Represent list with hybrid style (flow for flat, block for nested)."""
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=use_flow)

# 2. tuple
def _construct_tuple(loader: EnhancedSafeLoader, node: SequenceNode) -> TupleType[Any, ...]:
    return tuple(loader.construct_sequence(node))

def _represent_tuple(dumper: EnhancedSafeDumper, data: TupleType[Any, ...]) -> SequenceNode:
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence('!tuple', list(data), flow_style=use_flow)

# 3. set
def _construct_set(loader: EnhancedSafeLoader, node: SequenceNode) -> SetType[Any]:
    return set(loader.construct_sequence(node))

def _represent_set(dumper: EnhancedSafeDumper, data: SetType[Any]) -> SequenceNode:
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence('!set', list(data), flow_style=use_flow)

# 4. frozenset
def _construct_frozenset(loader: EnhancedSafeLoader, node: SequenceNode) -> frozenset[Any]:
    return frozenset(loader.construct_sequence(node))

def _represent_frozenset(dumper: EnhancedSafeDumper, data: frozenset[Any]) -> SequenceNode:
    use_flow = _should_use_flow_style(dumper, data, data)
    return dumper.represent_sequence('!frozenset', list(data), flow_style=use_flow)

# ---------- Scalar ----------
# 1. complex
def _construct_complex(loader: EnhancedSafeLoader, node: ScalarNode) -> complex:
    value = loader.construct_scalar(node)
    return complex(value.replace(" ", ""))

def _represent_complex(dumper: EnhancedSafeDumper, data: complex) -> ScalarNode:
    real, imag = data.real, data.imag
    value = f"{real} + {imag}j" if imag >= 0 else f"{real} - {abs(imag)}j"
    return _rep_scalar(dumper, '!complex', value)

# 2. decimal
def _construct_decimal(loader: EnhancedSafeLoader, node: ScalarNode) -> decimal.Decimal:
    return decimal.Decimal(loader.construct_scalar(node))

def _represent_decimal(dumper: EnhancedSafeDumper, data: decimal.Decimal) -> ScalarNode:
    return _rep_scalar(dumper, '!decimal', str(data))

# 3. datetime
def _construct_datetime(loader: EnhancedSafeLoader, node: ScalarNode) -> datetime.datetime:
    return datetime.datetime.fromisoformat(loader.construct_scalar(node))

def _represent_datetime(dumper: EnhancedSafeDumper, data: datetime.datetime) -> ScalarNode:
    return _rep_scalar(dumper, '!datetime', data.isoformat())

# 4. path
def _construct_path(loader: EnhancedSafeLoader, node: ScalarNode) -> Path:
    return Path(loader.construct_scalar(node))

def _represent_path(dumper: EnhancedSafeDumper, data: Path) -> ScalarNode:
    # Always use posix seperators (/) for YAML portability
    return _rep_scalar(dumper, '!path', data.as_posix())


# ======================================================
# Registration System
# ======================================================

def register_type(
    tag: str, 
    typ: TypeType[Any], 
    representer: Representer[Any], 
    constructor: Constructor[_NodeT, _T]
) -> None:
    """Register a new custom type for safe YAML serialization/deserialization.
    
    IMPORTANT: this registers on the EnhancedSafeDumper/Loader classes.

    Parameters
    ----------
    tag : str
        YAML tag (e.g. `'!decimal'`).
    typ : type
        Python type to register.
    representer : Callable
        Function converting Python → YAML node.
    constructor : Callable
        Function converting YAML node → Python.
    
    Example
    -------
    >>> from decimal import Decimal
    >>> register_type('!decimal', Decimal, _represent_decimal, _construct_decimal)
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
    if not HAS_YAML:
        return
    
    if force or not getattr(EnhancedSafeLoader, "_enhanced_registered", False):
        # 1. Built-in hybrid types
        EnhancedSafeDumper.add_representer(dict, _represent_dict)
        EnhancedSafeDumper.add_representer(list, _represent_list)

        # 2. Custom extensions
        _builtin_types: ListType[TupleType[str, TypeType[Any], Any, Any]] = [
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
_ensure_enhanced_registered()


# ======================================================
#  Public API
# ======================================================

def load(stream: str | bytes | IO[str] | IO[bytes], encoding: str = "utf-8"):
    """Safely load YAML string or bytes with extended Python type support.

    Parameters
    ----------
    data : str | bytes
        YAML input to parse.

    Returns
    -------
    Any
        Parsed Python object (dict, list, etc.)

    Example
    -------
    >>> yaml_str = "a: !tuple [1, 2, 3]"
    >>> load(yaml_str)
    {'a': (1, 2, 3)}
    """
    _require_yaml()
    
    if isinstance(stream, bytes):
        stream = stream.decode(encoding)
    
    return yaml.load(stream, Loader=EnhancedSafeLoader)

def dump(
    data: Any, 
    stream: IO[str] | None = None,
    **kwargs: Any
) -> str | None:
    """Safely dump Python object to YAML with extended type support.
    
    Parameters
    ----------
    data : Any
        Python object to serialize.
    default_flow_style : bool, default=False
        Whether to use flow style for sequences/mappings.
    indent : int, default=2
        Indentation spaces.
    allow_unicode : bool, default=True
        Whether to allow unicode characters.
    sort_keys : bool, default=False
        Whether to sort dictionary keys.
    **kwargs : Any
        Additional keyword arguments passed to `yaml.dump()`.

    Returns
    -------
    str | None
        YAML string representation if stream is None, otherwise None.

    Example
    -------
    >>> from pathlib import Path
    >>> dump({"path": Path("/tmp/test.txt")})
    "path: !path '/tmp/test.txt'"
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
    return result.rstrip() + '\n'

def inspect_registry(verbose: bool = True) -> DictType[str, ListType[Any]]:
    """Show current registration of representers and constructors.

    Parameters
    ----------
    verbose : bool, default=True
        Whether to print current registration info.

    Returns
    -------
    dict[str, list[Any]]
        A dictionary summarizing current YAML type registrations.
    """
    if not HAS_YAML:
        return {}
    
    record: DictType[str, ListType[Any]] = {
        "Representer keys": list(EnhancedSafeDumper.yaml_representers.keys()),
        "Multi-Representer keys": list(EnhancedSafeDumper.yaml_multi_representers.keys()),
        "Constructor keys": list(EnhancedSafeLoader.yaml_constructors.keys())
    }
    if verbose:
        for k, v in record.items():
            print(k)
            for keys in v:
                print(" ", keys)
    return record


if __name__ == "__main__":
    import doctest
    doctest.testmod(verbose=True, optionflags=doctest.ELLIPSIS)

    if HAS_YAML:
        data: DictType[Any, Any] = {
            "tuple": (1, 2, 3),
            "set": {1, 2, 3},
            "frozenset": frozenset([4, 5, 6]),
            "complex": 3 + 4j,
            "decimal": decimal.Decimal("12.34"),
            "datetime": datetime.datetime(2025, 10, 27, 12, 45),
            "path": Path("/tmp/example.txt"),
            "nested_dict": {"a": 1, "b": 2},    # Should be flow style
            "deep_dict": {"x": {"y": "z"}},     # Should be block style
            "nested_list": [1, 2, 3, 4, 5],
            "deep_list": [[1], [2], [3, [4, [5]]]],
        }

        print("=== Dump Output ===")
        yaml_str = dump(data, sort_keys=True, default_flow_style=True)
        print(yaml_str)
        print(dump(data, sort_keys=True))

        print("=== Load Output ===")
        print(load(yaml_str))

        from pprint import pprint
        pprint(yaml.SafeLoader.yaml_constructors)
        print("---")
        pprint(yaml.Loader.yaml_constructors)

        pprint(yaml.SafeDumper.yaml_representers)
        print("---")
        pprint(yaml.Dumper.yaml_representers)
    else:
        print("PyYAML not installed.")
    
    print(hasattr(EnhancedSafeDumper, "represented_objects"))
    print(getattr(EnhancedSafeDumper, "represented_objects", {}))