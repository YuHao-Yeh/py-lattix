# type definition
# pyright: reportDeprecated=false

import sys
from typing import Any, ClassVar, Literal, TypeVar
from collections.abc import Callable

# Atomic Dependencies
import datetime
import decimal
import fractions
import pathlib
import uuid

from . import compat
HAS_NUMPY = compat.HAS_NUMPY
HAS_PANDAS = compat.HAS_PANDAS
np = compat.numpy
pd = compat.pandas


# Pyhon 3.9+
if sys.version_info >= (3, 9):
    from types import GenericAlias as GenericAlias
    DictType = dict
    ListType = list
    SetType = set
    TupleType = tuple
    TypeType = type
else:
    from typing import Dict as DictType
    from typing import List as ListType
    from typing import Set as SetType
    from typing import Tuple as TupleType
    from typing import Type as TypeType
    GenericAlias = type(ListType[int])

# Python 3.10+
if sys.version_info >= (3, 10):
    from typing import TypeAlias, TypeGuard

    BuiltinAtoms: TypeAlias = str | bytes | bytearray | int | float \
        | complex | bool | None
    StdLibAtoms = decimal.Decimal | fractions.Fraction | pathlib.Path \
        | uuid.UUID | datetime.date | datetime.time
    AtomicTypes = BuiltinAtoms | StdLibAtoms

    if HAS_PANDAS and HAS_NUMPY:
        ScalarTypes = AtomicTypes | pd.DataFrame | pd.Series | np.ndarray
    elif HAS_PANDAS:
        ScalarTypes = AtomicTypes | pd.DataFrame | pd.Series
    elif HAS_NUMPY:
        ScalarTypes = AtomicTypes | np.ndarray
    else:
        ScalarTypes = AtomicTypes
else:
    from typing import Optional, Union
    from typing_extensions import TypeAlias, TypeGuard

    BuiltinAtoms: TypeAlias = Union[
        str, bytes, bytearray, int, float, complex, bool, None
    ]
    StdLibAtoms: TypeAlias = Union[
        decimal.Decimal, fractions.Fraction, pathlib.Path, uuid.UUID, 
        datetime.date, datetime.time
    ]
    AtomicTypes: TypeAlias = Union[BuiltinAtoms, StdLibAtoms]
    
    if HAS_PANDAS and HAS_NUMPY:
        ScalarTypes = Union[AtomicTypes, pd.DataFrame, pd.Series, np.ndarray[Any, Any]]
    elif HAS_PANDAS:
        ScalarTypes = Union[AtomicTypes, pd.DataFrame, pd.Series]
    elif HAS_NUMPY:
        ScalarTypes = Union[AtomicTypes, np.ndarray[Any, Any]]
    else:
        ScalarTypes = AtomicTypes


_ATOMIC_BASE_TYPES = (
    str, bytes, bytearray, 
    int, float, complex, bool, type(None),
    decimal.Decimal, 
    fractions.Fraction,
    pathlib.Path, 
    uuid.UUID, 
    datetime.date, 
    datetime.time
)


# Class-level attribute sets
ClassAttrSet = ClassVar[SetType[str]]

# Style registry type
StyleHandler = Callable[..., str]
StyleRegistry = DictType[str, StyleHandler]

# Modules registry type
if sys.version_info >= (3, 10):
    ModuleRegistry = DictType[str, object | None]
else:
    ModuleRegistry = DictType[str, Optional[object]]
    

# Adapter type
RecurseFunc = Callable[[Any], Any]
Adapter = Callable[[Any, RecurseFunc], Any]
AdapterRegistry = DictType[str, Adapter]

# Argument registry type
ArgsRegistry = DictType[str, DictType[str, Any]]

# Data merging method enums
JOIN_METHOD = Literal["inner", "left", "right", "outer"]
MERGE_METHOD = Literal["tuple", "self", "other", "prefer_self", "prefer_other"]

# Traversal order enums
TRAV_ORDER = Literal["preorder", "inorder", "postorder", "node", "levelorder"]


__all__ = [
    "DictType", "ListType", "SetType", "TupleType", "TypeType",
    "GenericAlias", "TypeGuard",
    "AtomicTypes", "ScalarTypes", "BuiltinAtoms", "StdLibAtoms", "_ATOMIC_BASE_TYPES",
    "ClassAttrSet",
    "StyleHandler", "StyleRegistry",
    "ModuleRegistry",
    "RecurseFunc", "Adapter", "AdapterRegistry",
    "ArgsRegistry",
    "JOIN_METHOD", "MERGE_METHOD", "TRAV_ORDER",
]

del sys, datetime, decimal, fractions, pathlib, uuid, Literal, Callable, ClassVar, TypeVar
