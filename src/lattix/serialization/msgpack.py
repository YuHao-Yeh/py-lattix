"""MessagePack serialization utilities for Lattix.

This module provides support for the MessagePack binary serialization format.
MessagePack is more compact than JSON and is suitable for efficient
data storage or network transmission of hierarchical structures.
"""

from typing import Any

from ..utils import compat, transform
from ..utils.exceptions import OptionalImportError

__all__ = ["to_msgpack"]


def to_msgpack(obj: Any, **kwargs: Any) -> Any:
    """Serialize an object to MessagePack binary format.

    The object is first recursively converted into primitive types using
    Lattix's adapter system, then packed into bytes.

    Args:
        obj: The object to serialize.
        **kwargs: Additional keyword arguments passed to ``msgpack.packb``.

    Returns:
        bytes: The MessagePack-encoded byte string.

    Raises:
        OptionalImportError: If the ``msgpack`` library is not installed.
    """
    if not compat.HAS_MSGPACK:
        raise OptionalImportError("MessagePack", "packing suport", "msgpack")

    return compat.msgpack.packb(transform.serialize(obj), use_bin_type=True, **kwargs)
