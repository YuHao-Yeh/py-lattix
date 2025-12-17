# core/__init__.py

import logging
logger = logging.getLogger(__name__)


from ._core.base import LattixNode

from . import adapters
from .adapters import (
    register_adapter,
    unregister_adapter,
    get_adapter,
    construct_from_iterable,
)

from . import serialization
from .serialization import safe_yaml

from .structures.mapping import Lattix

from .utils import exceptions


__all__ = [
    # _core
    "LattixNode",

    # adapters
    "adapters",
    "register_adapter", "unregister_adapter", "get_adapter",
    "construct_from_iterable",

    # serialization
    "serialization", "safe_yaml",

    # structures
    "Lattix",

    # utils
    "exceptions",
]


__version__ = "0.1.0"
