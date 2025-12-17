from typing import Any, IO, Protocol, TypeVar, runtime_checkable
from yaml import SafeLoader, SafeDumper
from yaml.nodes import Node

from ..utils.types import DictType, ListType, TupleType, TypeType

_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)
_CONTAINER_TYPES: TupleType[TypeType, ...]
_MAX_FLOW_LEN: int

# PyYAML core types
class EnhancedSafeLoader(SafeLoader):
    _enhanced_registered: bool

class EnhancedSafeDumper(SafeDumper):
    def increase_indent(self, flow: bool = ..., indentless: bool = ...) -> None: ...


# Representer / Constructor (Protocol-based)
@runtime_checkable
class Representer(Protocol[_T_contra]):
    def __call__(self, dumper: EnhancedSafeDumper, data: _T_contra, /) -> Node: ...

@runtime_checkable
class Constructor(Protocol[_T_co]):
    def __call__(self, loader: EnhancedSafeLoader, node: Node, /) -> _T_co: ...



# Registration API
def register_type(
    tag: str, 
    typ: TypeType[Any], 
    representer: Representer[Any],  # type: ignore[name-defined] — using generic alias below
    constructor: Constructor[Any],  # type: ignore[name-defined]
) -> None: ...


#   Public API
def load(stream: str | bytes | IO[str] | IO[bytes], encoding: str = ...) -> Any: ...

def dump(
    data: Any, 
    stream: IO[str] | None = ...,
    **kwargs: Any
) -> str | None: ...

def inspect_registry(verbose: bool = ...) -> DictType[str, ListType[Any]]: ...


__all__: ListType[str]
