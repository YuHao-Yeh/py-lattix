from abc import ABCMeta
from typing import Any

from ..utils.common import scan_class_attrs

class LattixMeta(ABCMeta):
    """Metaclass that handles Lattix class-level attribute caching."""
    def __delattr__(cls, name: str):
        super().__delattr__(name)
        type.__setattr__(cls, "__CLASS_ATTRS__", None)
        scan_class_attrs.cache_clear() 

    def __setattr__(cls, name: str, value: Any):
        super().__setattr__(name, value)
        if not name.startswith("__"):
            type.__setattr__(cls, "__CLASS_ATTRS__", None)
            scan_class_attrs.cache_clear() 
