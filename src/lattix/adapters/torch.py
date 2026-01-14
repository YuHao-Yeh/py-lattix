"""PyTorch type adapter for Lattix.

This module provides conversion logic for PyTorch Tensors and Parameters.
It includes safe handling for tensors located on non-CPU devices (GPU)
and tensors requiring gradients.
"""

from typing import Any

from ..utils import compat
from ..utils.types import RecurseFunc
from .registry import register_adapter

__all__ = ["_register_torch_adapters"]


def _register_torch_adapters() -> None:
    """Registers adapters for PyTorch Tensors and nn.Parameters.

    The conversion process ensures that tensors are detached from the
    computation graph and moved to CPU memory before being converted
    to Python lists.
    """
    if not compat.HAS_TORCH:
        return
    tm = compat.torch

    def handle_tensor(value: Any, recurse: RecurseFunc) -> Any:
        try:
            return value.tolist()
        except Exception:
            return value.detach().cpu().numpy().tolist()

    register_adapter(tm.Tensor, handle_tensor)
    if hasattr(tm, "nn") and hasattr(tm.nn, "Parameter"):
        register_adapter(tm.nn.Parameter, lambda v, r: handle_tensor(v.data, r))
