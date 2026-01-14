"""Serialization and data interchange utilities.

This package provides a centralized interface for converting Lattix objects
and complex Python hierarchies into common data formats. It acts as a
bridge between Lattix's hierarchical internal representation and external
formats like YAML, JSON, and MessagePack.

The provided functions are "Lattix-aware," meaning they automatically
utilize the project's adapter system to ensure that specialized types
(e.g., NumPy arrays, Pandas DataFrames, or PyTorch tensors) are
transformed into appropriate serializable primitives.

Exported Functions:
    yaml_safe_load: Securely parses YAML with extended Python type support.
    yaml_safe_dump: Serializes objects to YAML with hybrid-style indentation.
    register_yaml_type: Adds custom Python types to the safe YAML registry.
    to_json: Standard JSON serialization.
    to_orjson: High-performance JSON serialization using the orjson library.
    to_msgpack: Compact binary serialization using MessagePack.
"""

# isort: skip_file
from __future__ import annotations

from .json import to_json, to_orjson
from .msgpack import to_msgpack
from .yaml import (
    dump as yaml_safe_dump,
    load as yaml_safe_load,
    register_type as register_yaml_type,
)

__all__ = [
    "register_yaml_type",
    "yaml_safe_load",
    "yaml_safe_dump",
    "to_json",
    "to_orjson",
    "to_msgpack",
]
