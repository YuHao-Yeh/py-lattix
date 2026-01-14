import importlib
import sys
from typing import Any, Iterator
from unittest.mock import patch

import pytest

from src.lattix.core import interfaces
from src.lattix.core.interfaces import LattixMapping, MutableLattixMapping

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


# ---------- Concrete Implementations ----------


class ConcreteReadOnly(LattixMapping):
    """A minimal read-only implementation."""

    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def _config(self) -> Any:
        return ()

    def _construct(self) -> Self:
        return ConcreteReadOnly()


class ConcreteMutable(MutableLattixMapping):
    """A minimal mutable implementation."""

    def __init__(self, data: dict = None):
        self._data = data if data is not None else {}

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: Any) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def _config(self) -> Any:
        return ()

    def _construct(self) -> Self:
        return ConcreteMutable()


# ---------- Tests 1: LattixMapping ----------


class TestLattixMapping:
    def test_abstract_dict_valid_name(self):
        # --- 1. _valid_name regex logic ---
        assert LattixMapping._valid_name("valid_name") is True
        assert LattixMapping._valid_name("_valid") is True
        assert LattixMapping._valid_name("valid1") is True
        assert LattixMapping._valid_name("1invalid") is False
        assert LattixMapping._valid_name("invalid-name") is False
        assert LattixMapping._valid_name("") is False

    def test_abstract_dict_get(self):
        # --- 2. get (found and default) ---
        d = ConcreteReadOnly({"a": 1})
        assert d.get("a") == 1
        assert d.get("b") is None
        assert d.get("b", 100) == 100

    def test_abstract_dict_contains(self):
        # --- 3. __contains__ ---
        d = ConcreteReadOnly({"a": 1})
        assert "a" in d
        assert "b" not in d

    def test_abstract_dict_to_dict_recursive(self):
        # --- 4. to_dict (recursive and flat) ---
        nested = ConcreteReadOnly({"inner": 2})
        d = ConcreteReadOnly({"outer": 1, "nested": nested, "plain": {"x": 1}})

        result = d.to_dict()
        assert isinstance(result, dict)
        assert result["outer"] == 1
        # Check that the nested LattixMapping was converted to a plain dict
        assert isinstance(result["nested"], dict)
        assert result["nested"]["inner"] == 2
        # Check that plain dicts remain plain dicts
        assert result["plain"] == {"x": 1}

    def test_construct_not_implemented(self):
        # --- 5. _construct raising NotImplementedError ---
        with pytest.raises(NotImplementedError):
            LattixMapping._construct({}, ())

    def test_python_old_legacy_less_than_39(self):
        # Mock version to 3.8
        with patch.object(sys, "version_info", (3, 8)):
            importlib.reload(interfaces)
            d = ConcreteReadOnly({"a": 1})
            assert d.get("a") == 1


# ---------- Tests 2: MutableLattixMapping ----------


class TestMutableLattixMapping:
    def test_mutable_update_variations(self):
        # --- 1. update ---

        # 1. Update with Mapping
        d = ConcreteMutable({"a": 1})
        d.update({"a": 2}, b=3)
        assert d["a"] == 2
        assert d["b"] == 3

        # 2. Update with Iterable of pairs
        d = ConcreteMutable()
        d.update([("c", 4)], d=5)
        assert d["c"] == 4
        assert d["d"] == 5

        # 3. Update with kwargs
        d = ConcreteMutable()
        d.update(d=5)
        assert d["d"] == 5

        # 4. Update with "Keys" object (Duck typing branch)
        # This hits the `elif hasattr(other, "keys"):` block
        class DuckMap:
            def keys(self):
                return ["k"]

            def __getitem__(self, item):
                return 99

        d = ConcreteMutable()
        d.update(DuckMap(), extra=100)
        assert d["k"] == 99
        assert d["extra"] == 100

        # 5. Empty update
        d.update()

    def test_merge_validation(self):
        # --- 2. merge type checking ---
        d = ConcreteMutable()
        with pytest.raises(TypeError):
            d.merge("not-a-map")  # type: ignore

    def test_merge_logic(self):
        # --- 3. merge (overwrite logic and recursion) ---

        # Setup for recursion test:
        # d1 = { "a": 1, "nested": { "x": 10 } }
        # d2 = { "a": 2, "nested": { "y": 20 } }

        # We use ConcreteMutable for the nested part to test recursive merging
        inner_d1 = ConcreteMutable({"x": 10})
        d1 = ConcreteMutable({"a": 1, "nested": inner_d1})

        d2 = {"a": 2, "nested": {"y": 20}, "new": 3}

        # Perform Merge with overwrite=True
        d1.merge(d2, overwrite=True)

        assert d1["a"] == 2  # Overwritten
        assert d1["new"] == 3  # New key added
        assert d1["nested"]["x"] == 10  # Preserved (recursive merge)
        assert d1["nested"]["y"] == 20  # Added (recursive merge)

    def test_merge_no_overwrite(self):
        # --- 4. merge with overwrite=False ---
        d1 = ConcreteMutable({"a": 1})
        d2 = {"a": 2, "b": 3}

        d1.merge(d2, overwrite=False)

        assert d1["a"] == 1  # Not overwritten
        assert d1["b"] == 3  # New key added


# ---------- Tests 3: Python Version ----------
class TestPyVersionImport:

    def test_python_old_legacy_less_than_39(self):
        # Mock version to 3.8
        with patch.object(sys, "version_info", (3, 8)):
            importlib.reload(interfaces)
            d = ConcreteReadOnly({"a": 1})
            assert d.get("a") == 1

        importlib.reload(interfaces)
