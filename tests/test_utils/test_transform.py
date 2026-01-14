import importlib
import sys
from unittest.mock import MagicMock, NonCallableMock, patch

import pytest

from src.lattix.utils import transform as transform

top_mod = "src.lattix"


# ---------- Tests 1: DeepConvert Logic ----------


class TestDeepConvert:
    # ---------- Primitives ----------

    def test_primitives(self):
        """Test that primitives are returned as-is."""
        assert transform.deep_convert(1) == 1
        assert transform.deep_convert("string") == "string"
        assert transform.deep_convert(None) is None

    # ---------- Adapters ----------

    def test_adapter_usage(self):
        """Test that get_adapter is called and used."""
        obj = object()
        mock_adapter = MagicMock(return_value="adapted")

        with patch.object(transform, "get_adapter", return_value=mock_adapter):
            result = transform.deep_convert(obj)
            assert result == "adapted"
            mock_adapter.assert_called_once()

    # ---------- Mapping ----------

    def test_mapping_to_dict(self):
        """Test converting a nested mapping to a dict."""
        data = {"a": 1, "b": {"c": 2}}
        result = transform.deep_convert(data, dict)
        assert isinstance(result, dict)
        assert result == {"a": 1, "b": {"c": 2}}

    def test_mapping_to_list(self):
        """Test converting a mapping to a list."""
        # Case 1: Multiple items
        # -> [["a", 1], ["b", 2]]
        data = {"a": 1, "b": 2}
        result = transform.deep_convert(data, list)
        result.sort(key=lambda x: x[0])
        assert result == [["a", 1], ["b", 2]]

        # Case 2: Single item -> edge case logic:
        # -> ["a", 1] -> ["a", 1]
        data_single = {"a": 1}
        result_single = transform.deep_convert(data_single, list)
        assert result_single == ["a", 1]

        # Case 3: Single item -> non edge case logic

    def test_mapping_to_tuple(self):
        """Test converting mapping to tuple (uses normalized generator with tuples)."""
        data = {"a": 1}
        # edge case: (("a", 1),) -> ("a", 1)
        result = transform.deep_convert(data, tuple)
        assert result == ("a", 1)

    def test_mapping_to_non_iterable(self):
        """Test converting a mapping to non-iterable."""
        data = {"a": 1}
        result = transform.deep_convert(data, str)
        assert result == "{'a': 1}"

    def test_mapping_unwrap_fail_not_list_or_tuple(self):
        class WeirdContainer:
            def __init__(self, iterable):
                self.data = ["I am a string, not a tuple"]

            def __len__(self):
                return len(self.data)

            def __getitem__(self, i):
                return self.data[i]

            def __iter__(self):
                return iter(self.data)

            def __eq__(self, other):
                return isinstance(other, WeirdContainer) and self.data == other.data

        data = {"a": 1}

        result = transform.deep_convert(data, ftype=WeirdContainer)

        assert isinstance(result, WeirdContainer)
        assert result[0] == "I am a string, not a tuple"

    def test_mapping_unwrap_fail_wrong_length(self):
        class TripleContainer:
            def __init__(self, iterable):
                self.data = [(1, 2, 3)]

            def __len__(self):
                return len(self.data)

            def __getitem__(self, i):
                return self.data[i]

            def __iter__(self):
                return iter(self.data)

            def __eq__(self, other):
                return isinstance(other, TripleContainer) and self.data == other.data

        data = {"a": 1}

        result = transform.deep_convert(data, ftype=TripleContainer)

        assert isinstance(result, TripleContainer)
        assert result[0] == (1, 2, 3)

    # ---------- Iterable ----------

    def test_iterable_conversion(self):
        """Test converting list to tuple and deep recursion."""
        data = [1, [2, 3]]
        result = transform.deep_convert(data, tuple)
        assert result == (1, (2, 3))

        data_mixed = [{"a": 1}]
        result_mixed = transform.deep_convert(data_mixed, list)
        assert result_mixed == [["a", 1]]

    # ---------- Fallback ----------

    def test_fallback(self):
        """Test fallback for objects that aren't primitive, mapping, or iterable."""
        obj = NonCallableMock(spec=object)

        # Ensure is_primitive returns False so we hit the fallback
        with patch.object(transform, "is_primitive", return_value=False):
            # Also ensure get_adapter returns None
            with patch.object(transform, "get_adapter", return_value=None):
                assert transform.deep_convert(obj) == obj


# ---------- Tests 2: Serialize Logic ----------


class TestSerialize:
    def test_primitives(self):
        assert transform.serialize(1) == 1
        assert transform.serialize("s") == "s"
        assert transform.serialize(None) is None

    def test_circular_reference(self):
        """Test cycle detection returns string marker."""
        lst = []
        lst.append(lst)
        result = transform.serialize(lst)
        assert isinstance(result, list)
        assert "Circular" in result[0]

    def test_adapter_priority(self):
        """Test that adapter is checked before mapping/iterable logic."""
        obj = {"a": 1}
        with patch.object(
            transform, "get_adapter", return_value=lambda x, r: "adapted"
        ):
            assert transform.serialize(obj) == "adapted"

    def test_mapping(self):
        """Test mapping serialization including key stringification."""
        data = {1: "one", "two": 2}
        result = transform.serialize(data)
        assert result == {"1": "one", "two": 2}

    def test_iterable(self):
        """Test iterable serialization (skipping str/bytes)."""
        data = [1, {2}, "keep_string"]
        result = transform.serialize(data)
        assert result[0] == 1
        assert isinstance(result[1], list)
        assert result[2] == "keep_string"

    def test_object_with_dict(self):
        """Test generic object with __dict__."""

        class A:
            def __init__(self):
                self.x = 1
                self._private = 2

        obj = A()
        result = transform.serialize(obj)
        assert result == {"x": 1}  # _private excluded

    def test_object_with_slots(self):
        """Test object with __slots__, ensuring unset attributes don't crash."""

        class Slotted:
            __slots__ = ["x", "y", "_z"]

            def __init__(self):
                self.x = 10
                # self.y is purposely unset to trigger hasattr check
                self._z = 99

        obj = Slotted()
        result = transform.serialize(obj)
        # Should contain "x", ignore "_z" (private), ignore "y" (unset)
        assert result == {"x": 10}

    def test_fallback_str_repr(self):
        """Test fallback to str, then repr."""

        # Case 1: Good str
        class GoodStr:
            def __str__(self):
                return "good"

        assert transform.serialize(GoodStr()) == "good"

        # Case 2: Bad str, fallback to repr
        class BadStr:
            def __str__(self):
                raise ValueError("No string for you")

            def __repr__(self):
                return "fallback_repr"

        assert transform.serialize(BadStr()) == "fallback_repr"


# ---------- Tests 3: Flatten/Unflatten ----------


class TestFlattenUnflatten:
    def test_flatten(self):
        data = {"a": 1, "b": {"c": 2}, "d": {}}
        result = transform.flatten(data, sep="/")
        assert result["a"] == 1
        assert result["b/c"] == 2
        assert result["d"] == {}

    def test_flatten_non_dict_in_stack(self):
        """
        Edge case where stack contains non-mapping
        (shouldn't happen with standard usage but code handles it).
        """
        assert transform.flatten("not_a_dict") == {"": "not_a_dict"}

    def test_unflatten_success(self):
        data = {"a": 1, "b.c": 2}
        result = transform.unflatten(data, sep=".")
        assert result == {"a": 1, "b": {"c": 2}}

    def test_unflatten_conflict_error(self):
        """Test ValueError when trying to turn a scalar into a dict."""
        # "a" is 1. Then "a.b" tries to make "a" a dict.
        data = {"a": 1, "a.b": 2}
        with pytest.raises(ValueError, match="Key conflict"):
            transform.unflatten(data)

    def test_unflatten_existing_dict(self):
        """Test merging into existing dict structure."""
        # a.b = 1, a.c = 2
        data = {"a.b": 1, "a.c": 2}
        result = transform.unflatten(data)
        assert result == {"a": {"b": 1, "c": 2}}


# ---------- Tests 3: Python Versions ----------


class TestPyVersionImport:
    def test_python_old_legacy_less_than_39(self):
        # Mock version to 3.8
        with patch.object(sys, "version_info", (3, 8)):
            importlib.reload(transform)

        importlib.reload(transform)
