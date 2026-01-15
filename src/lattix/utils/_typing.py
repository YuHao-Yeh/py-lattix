"""Internal type aliases and version-compatibility shims.

This module serves as a private repository for complex type definitions used
across Lattix. It handles the variations in Python's typing system between
versions 3.8 and 3.10+, providing a unified set of aliases for:
    1. **Atomic Types**: Standard library primitives and scalars.
    2. **Scalar Types**: Dynamic detection of NumPy and Pandas types.
    3. **Registry Types**: Type signatures for adapters and constructors.
    4. **Enums**: Literal types for join methods and traversal orders.

Note:
    This module is intended for internal use only. Public-facing type aliases
    should be accessed via :module:`lattix.utils.types`.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeVar, Union

if sys.version_info >= (3, 10):
    from typing import TypeAlias, TypeGuard
else:
    from typing_extensions import TypeAlias, TypeGuard

if sys.version_info >= (3, 9):
    if TYPE_CHECKING:
        from typing import Dict, List, Set, Tuple, Type
    else:
        Dict = dict
        List = list
        Set = set
        Tuple = tuple
        Type = type
else:
    from typing import Dict, List, Set, Tuple, Type

__all__ = [
    "TypeAlias",
    "TypeGuard",
    "AtomicTypes",
    "ScalarTypes",
    "BuiltinAtoms",
    "StdLibAtoms",
    "ClassAttrSet",
    "StyleHandler",
    "StyleRegistry",
    "ModuleRegistry",
    "RecurseFunc",
    "Adapter",
    "AdapterRegistry",
    "ArgsRegistry",
    "JOIN_METHOD",
    "MERGE_METHOD",
    "TRAV_ORDER",
    "Dict",
    "List",
    "Set",
    "Tuple",
    "Type",
]


# ======================================================
# Atomic Types
# ======================================================
import datetime
import decimal
import fractions
import pathlib
import uuid

if sys.version_info >= (3, 10):
    BuiltinAtoms: TypeAlias = (
        str | bytes | bytearray | int | float | complex | bool | None
    )
    StdLibAtoms: TypeAlias = (
        decimal.Decimal
        | fractions.Fraction
        | pathlib.Path
        | uuid.UUID
        | datetime.date
        | datetime.time
    )
    AtomicTypes: TypeAlias = BuiltinAtoms | StdLibAtoms
else:
    BuiltinAtoms: TypeAlias = Union[
        str, bytes, bytearray, int, float, complex, bool, None
    ]
    StdLibAtoms: TypeAlias = Union[
        decimal.Decimal,
        fractions.Fraction,
        pathlib.Path,
        uuid.UUID,
        datetime.date,
        datetime.time,
    ]
    AtomicTypes: TypeAlias = Union[BuiltinAtoms, StdLibAtoms]


# ======================================================
# Scalar Types (Pandas/Numpy)
# ======================================================
from . import compat

if TYPE_CHECKING:
    if sys.version_info >= (3, 10):
        ScalarTypes: TypeAlias = AtomicTypes | Any
    else:
        ScalarTypes: TypeAlias = Union[AtomicTypes, Any]
else:
    _scalars = [AtomicTypes]

    if compat.HAS_PANDAS:
        pd = compat.pandas
        _scalars.extend([pd.DataFrame, pd.Series])

    if compat.HAS_NUMPY:
        _scalars.append(compat.numpy.ndarray)

    if compat.HAS_TORCH:
        _scalars.append(compat.torch.Tensor)

    if compat.HAS_XARRAY:
        _scalars.extend([compat.xarray.DataArray, compat.xarray.Dataset])

    if len(_scalars) == 1:
        ScalarTypes = _scalars[0]
    else:
        ScalarTypes = Union[tuple(_scalars)]


# ======================================================
# Registry Types
# ======================================================
_ArgsT = TypeVar("_ArgsT")

if sys.version_info >= (3, 9):
    ClassAttrSet: TypeAlias = set[str]
    StyleHandler: TypeAlias = Callable[..., str]
    StyleRegistry: TypeAlias = dict[str, StyleHandler]
    ModuleRegistry: TypeAlias = dict[str, Any]
    RecurseFunc: TypeAlias = Callable[[Any], Any]
    Adapter: TypeAlias = Callable[[Any, RecurseFunc], Any]
    AdapterRegistry: TypeAlias = dict[str, Adapter]
    ArgsRegistry: TypeAlias = dict[str, dict[str, _ArgsT]]
else:
    from typing import Dict as TDict
    from typing import Optional

    ClassAttrSet: TypeAlias = Set[str]
    StyleHandler: TypeAlias = Callable[..., str]
    StyleRegistry: TypeAlias = TDict[str, StyleHandler]
    ModuleRegistry: TypeAlias = TDict[str, Optional[object]]
    RecurseFunc: TypeAlias = Callable[[Any], Any]
    Adapter: TypeAlias = Callable[[Any, RecurseFunc], Any]
    AdapterRegistry: TypeAlias = TDict[str, Adapter]
    ArgsRegistry: TypeAlias = TDict[str, TDict[str, _ArgsT]]


# ======================================================
# Enums
# ======================================================
JOIN_METHOD: TypeAlias = Literal["inner", "left", "right", "outer"]
MERGE_METHOD: TypeAlias = Literal[
    "tuple", "self", "other", "prefer_self", "prefer_other"
]
TRAV_ORDER: TypeAlias = Literal[
    "preorder", "inorder", "postorder", "node", "levelorder"
]
