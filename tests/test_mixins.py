# import threading
# import unittest
# from unittest.mock import MagicMock


# from src.lattix import Lattix
# from src.lattix._core.mixins import *


# class ConcreteThreading(ThreadingMixin):
#     """A concrete class to instantiate and test the abstract mixin."""
#     def __init__(self, level=0):
#         self._init_threading(level=level)

#     def _propagate_lock(self, obj, level, lock, rlock, seen=None):
#         # Minimal implementation to satisfy ABC
#         pass


# class TestThreadingMixinLockOperations(unittest.TestCase):
#     def setUp(self):
#         # Create instances, but we will often inject Mock locks to verify calls
#         pass

#     def test_acquire_release_level_0_no_locks(self):
#         """Test that acquire/release do nothing (and don't crash) when level is 0."""
#         tm = ConcreteThreading(level=0)
        
#         # Should not raise error
#         res = tm.acquire()
#         tm.release()
        
#         self.assertIsNone(res) 

#     def test_acquire_release_level_1_standard_lock(self):
#         """Test that acquire/release delegate to self._lock when level is 1."""
#         tm = ConcreteThreading(level=1)
        
#         # Replace the real lock with a Mock to verify interaction
#         mock_lock = MagicMock()
#         # We assign it using object.__setattr__ to mimic the class behavior, 
#         # though standard assignment works too.
#         object.__setattr__(tm, "_lock", mock_lock)
        
#         # Test Acquire
#         tm.acquire()
#         mock_lock.acquire.assert_called_once()
        
#         # Test Release
#         tm.release()
#         mock_lock.release.assert_called_once()

#     def test_acquire_release_level_2_reentrant_lock(self):
#         """Test that acquire/release delegate to self._rlock when level is 2."""
#         tm = ConcreteThreading(level=2)
        
#         mock_rlock = MagicMock()
#         object.__setattr__(tm, "_rlock", mock_rlock)
        
#         # Test Acquire
#         tm.acquire()
#         mock_rlock.acquire.assert_called_once()
        
#         # Test Release
#         tm.release()
#         mock_rlock.release.assert_called_once()

#     def test_acquire_arguments_passing(self):
#         """Test that arguments (timeout, blocking) are passed to the underlying lock."""
#         tm = ConcreteThreading(level=1)
#         mock_lock = MagicMock()
#         object.__setattr__(tm, "_lock", mock_lock)
        
#         # Call with arguments
#         tm.acquire(False, timeout=5)
        
#         # Check if arguments were passed correctly
#         mock_lock.acquire.assert_called_with(False, timeout=5)

#     def test_context_manager_protocol(self):
#         """Test the 'with' statement usage (__enter__ and __exit__)."""
#         tm = ConcreteThreading(level=1)
#         mock_lock = MagicMock()
#         object.__setattr__(tm, "_lock", mock_lock)
        
#         with tm as returned_obj:
#             # check that __enter__ returns self
#             self.assertIs(returned_obj, tm)
#             # check that acquire was called immediately
#             mock_lock.acquire.assert_called_once()
            
#             # reset mock to ensure release isn't called yet
#             mock_lock.release.assert_not_called()
        
#         # After exiting block, release should be called
#         mock_lock.release.assert_called_once()

#     def test_describe_lock_output(self):
#         """Test the debug string formatter."""
#         # Level 0
#         tm0 = ConcreteThreading(level=0)
#         desc0 = tm0._describe_lock()
#         self.assertIn("lock=None", desc0)
#         self.assertIn("rlock=None", desc0)
#         self.assertIn("level=0", desc0)

#         # Level 1
#         tm1 = ConcreteThreading(level=1)
#         desc1 = tm1._describe_lock()
#         # Check for memory address format (hex)
#         self.assertIn("lock=0x", desc1) 
#         self.assertIn("rlock=None", desc1)
#         self.assertIn("level=1", desc1)

#     def test_priority_rlock_over_lock(self):
#         """
#         Edge case: If both _rlock and _lock exist (shouldn't happen in normal flow, 
#         but defensively coded in your snippet), verify _rlock takes precedence.
#         """
#         tm = ConcreteThreading(level=0) # Init empty
        
#         mock_lock = MagicMock()
#         mock_rlock = MagicMock()
        
#         # Force both to exist
#         object.__setattr__(tm, "_lock", mock_lock)
#         object.__setattr__(tm, "_rlock", mock_rlock)
        
#         tm.acquire()
        
#         # Only RLock should be called based on: if getattr(self, "_rlock")... elif...
#         mock_rlock.acquire.assert_called_once()
#         mock_lock.acquire.assert_not_called()
    
#     def test_propagate_lock(self):
#         d = Lattix({"a": {"b": {"c": 1}}}, ts_level=2)
#         new_rlk = threading.RLock()

#         d.propagate_lock(2, None, new_rlk)

#         sub = d.a.b
#         self.assertIsNone(d._lock)
#         self.assertIsNone(d.a._lock)

#         self.assertIs(d._rlock, new_rlk)
#         self.assertIs(sub._rlock, d._rlock)


import sys
import pytest
import logging
from unittest.mock import MagicMock, patch, ANY
from threading import Lock, RLock


# =============================================================================
# 1. Setup / Mocking the Environment
# =============================================================================
# We need to simulate the lattix package structure and external dependencies 
# before importing the mixins to ensure we can control behavior (like missing libraries).

# Define dummy exceptions matching those in ../utils/exceptions
# class BaseTestError(Exception): pass
# class NoPyYAMLError(BaseTestError): pass
# class OperandTypeError(BaseTestError): pass
# class ThreadSafetyLevelTypeError(BaseTestError): pass
# class ThreadSafetyLevelValueError(BaseTestError): pass
# class ThreadingObjectTypeError(BaseTestError): pass
# class UnattachableError(BaseTestError): pass
# class LockExistenceError(BaseTestError): pass

# # Mock the internal utils modules
# mock_exceptions = MagicMock()
# mock_exceptions.NoPyYAMLError = NoPyYAMLError
# mock_exceptions.OperandTypeError = OperandTypeError
# mock_exceptions.ThreadSafetyLevelTypeError = ThreadSafetyLevelTypeError
# mock_exceptions.ThreadSafetyLevelValueError = ThreadSafetyLevelValueError
# mock_exceptions.ThreadingObjectTypeError = ThreadingObjectTypeError
# mock_exceptions.UnattachableError = UnattachableError
# mock_exceptions.LockExistenceError = LockExistenceError

# mock_common = MagicMock()
# mock_common.serialize = lambda x: x  # Pass-through for serialization

# mock_types = MagicMock()

# # Mock compat module (will be configured per test for numpy/pandas/yaml presence)
# mock_compat = MagicMock()
# mock_compat.HAS_NUMPY = False
# mock_compat.HAS_PANDAS = False
# mock_compat.HAS_YAML = False
# mock_compat.numpy = None
# mock_compat.pandas = None
# mock_compat.yaml = None

# # Apply patches to sys.modules
# sys.modules["lattix.utils.exceptions"] = mock_exceptions
# sys.modules["lattix.utils.common"] = mock_common
# sys.modules["lattix.utils.types"] = mock_types
# sys.modules["lattix.utils.compat"] = mock_compat

from src.lattix._core import mixins
from src.lattix.utils import exceptions, common, types, compat

top_mod = "src.lattix"

# ---------- Tests 1: ThreadingMixin ----------
# --- Status: Not tested ---

# class ConcreteThreading(mixins.ThreadingMixin):
#     """Concrete implementation for testing abstract ThreadingMixin."""
#     def __init__(self, level=0):
#         self._init_threading(level=level)
#         self.propagate_calls = []

#     def _propagate_lock(self, obj, level, lock, rlock, seen=None):
#         # Capture call for verification
#         self.propagate_calls.append({
#             "level": level, 
#             "lock": lock, 
#             "rlock": rlock
#         })

# class TestThreadingMixin:
    
#     def test_init_validation(self):
#         obj = ConcreteThreading()
        
#         # Test Invalid Type
#         with pytest.raises(exceptions.ThreadSafetyLevelTypeError):
#             obj._init_threading(level="invalid") # type: ignore

#         # Test Invalid Value
#         with pytest.raises(exceptions.ThreadSafetyLevelValueError):
#             obj._init_threading(level=99)

#     def test_init_levels(self):
#         # Level 0
#         t0 = ConcreteThreading(0)
#         assert t0._ts_level == 0
#         assert t0._lock is None
#         assert t0._rlock is None
#         assert t0._detached is True

#         # Level 1
#         t1 = ConcreteThreading(1)
#         assert t1._ts_level == 1
#         assert isinstance(t1._lock, type(Lock()))
#         assert t1._rlock is None

#         # Level 2
#         t2 = ConcreteThreading(2)
#         assert t2._ts_level == 2
#         assert t2._lock is None
#         assert isinstance(t2._rlock, type(RLock()))

#     def test_init_with_parent(self):
#         parent = ConcreteThreading(1)
#         child = ConcreteThreading()
#         # Init child with parent
#         child._init_threading(parent=parent)
        
#         assert child._ts_level == 1
#         assert child._lock is parent._lock
#         assert child._detached is False

#     def test_validate_parent_error(self):
#         t = ConcreteThreading()
#         with pytest.raises(exceptions.ThreadingObjectTypeError):
#             t._validate_parent("not_a_threading_mixin")

#     def test_validate_attachable_error(self):
#         # 1. Already attached
#         parent = ConcreteThreading(1)
#         child = ConcreteThreading()
#         child.attach_thread(parent) # Sets _detached = False
        
#         with pytest.raises(exceptions.UnattachableError):
#             child._validate_attachable(child)
            
#         # 2. Existing locks (LockExistenceError)
#         t_locked = ConcreteThreading(1) # Has _lock
#         with pytest.raises(exceptions.LockExistenceError):
#             t_locked._validate_attachable(t_locked)

#     def test_ts_level_setter_propagation(self):
#         t = ConcreteThreading(0)
        
#         # Set to 1
#         t.ts_level = 1
#         assert len(t.propagate_calls) == 1
#         assert t.propagate_calls[0]['level'] == 1
#         assert isinstance(t.propagate_calls[0]['lock'], type(Lock()))
        
#         # Set to 2
#         t.propagate_calls.clear()
#         t.ts_level = 2
#         assert len(t.propagate_calls) == 1
#         assert t.propagate_calls[0]['level'] == 2
#         assert isinstance(t.propagate_calls[0]['rlock'], type(RLock()))

#         # Set to 0
#         t.propagate_calls.clear()
#         t.ts_level = 0
#         assert len(t.propagate_calls) == 1
#         assert t.propagate_calls[0]['lock'] is None

#     def test_detach_thread(self, caplog):
#         caplog.set_level(logging.DEBUG)
#         t = ConcreteThreading(1)
#         original_lock = t._lock
        
#         # Detach keeping level
#         t.detach_thread(clear_locks=False)
#         assert t._ts_level == 1
#         assert t._lock is not original_lock
#         assert t._lock is not None
#         assert t._detached is True
#         assert "[TM:DETACH]" in caplog.text

#         # Detach clearing locks
#         t.detach_thread(clear_locks=True)
#         assert t._ts_level == 0
#         assert t._lock is None

#     def test_attach_thread(self, caplog):
#         caplog.set_level(logging.DEBUG)
#         parent = ConcreteThreading(2)
#         child = ConcreteThreading(0)
        
#         child.attach_thread(parent)
#         assert child._rlock is parent._rlock
#         assert child._ts_level == 2
#         assert child._detached is False
#         assert "[TM:ATTACH]" in caplog.text

#     def test_transplant_thread(self, caplog):
#         caplog.set_level(logging.DEBUG)
#         target = ConcreteThreading(0)
#         source = ConcreteThreading(1)
        
#         target.transplant_thread(source)
#         assert target._lock is source._lock
#         assert target._ts_level == 1
#         assert "[TM:TRANSPLANT]" in caplog.text

#     def test_locking_mechanisms(self):
#         # Case: No Lock
#         t0 = ConcreteThreading(0)
#         assert t0.acquire() is False # returns False
#         t0.release() # Should not error
        
#         # Case: Lock (Level 1)
#         t1 = ConcreteThreading(1)
#         t1.release() # uses self._lock.release()
        
#         # Case: RLock (Level 2)
#         t2 = ConcreteThreading(2)
#         assert t2.acquire() is True
#         t2.release()
        
#         # Context Manager
#         with t2 as obj:
#             assert obj is t2
#             # acquired in enter

#     def test_describe_lock(self):
#         t = ConcreteThreading(2)
#         desc = t._describe_lock()
#         assert "rlock=" in desc
#         assert "level=2" in desc

#     def test_manual_propagate_call(self):
#         t = ConcreteThreading(0)
#         t.propagate_lock(1, None, None)
#         assert len(t.propagate_calls) == 1


# ---------- Tests 2: LogicalMixin Tests ----------
# --- Status: Done ---

class ConcreteLogical(mixins.LogicalMixin, dict):
    """
    Concrete implementation of LogicalMixin backed by a dict.
    Operations simulate set operations on keys.
    """
    def __init__(self, data=None):
        if data:
            self.update(data)
            
    @classmethod
    def _construct(cls, data, config=None, /, **kwargs):
        return cls(data)

    def _and_impl(self, other, inplace=False):
        keys = self.keys() & other.keys()
        res = {k: self[k] for k in keys}
        if inplace:
            self.clear()
            self.update(res)
            return self
        return self._construct(res)

    def _or_impl(self, other, inplace=False):
        res = self.copy()
        res.update(other)
        if inplace:
            self.update(other)
            return self
        return self._construct(res)

    def _sub_impl(self, other, inplace=False):
        keys = self.keys() - other.keys()
        res = {k: self[k] for k in keys}
        if inplace:
            self.clear()
            self.update(res)
            return self
        return self._construct(res)
    
    def _xor_impl(self, other, inplace=False):
        keys = self.keys() ^ other.keys()
        # simplified XOR logic for testing: take value from self if in self, else from other
        res = {}
        for k in keys:
            if k in self: res[k] = self[k]
            else: res[k] = other[k]
        
        if inplace:
            self.clear()
            self.update(res)
            return self
        return self._construct(res)

class TestLogicalMixin:
    
    def test_and(self):
        l1 = ConcreteLogical({"a": 1, "b": 2})
        d2 = {"b": 3, "c": 4}
        
        # __and__
        res = l1 & d2
        assert res == {"b": 2}
        assert isinstance(res, ConcreteLogical)
        
        # __rand__
        res_r = d2 & l1
        assert res_r == {"b": 3} # Took value from d2 (left side)
        
        # __iand__
        l1 &= d2
        assert l1 == {"b": 2}
        
        # Type Error
        with pytest.raises(exceptions.OperandTypeError):
            l1 &= 1
        
        # NotImplemented
        assert l1.__and__(1) is NotImplemented
        assert l1.__rand__(1) is NotImplemented

    def test_or(self):
        l1 = ConcreteLogical({"a": 1})
        d2 = {"b": 2}
        
        # __or__
        res = l1 | d2
        assert res == {"a": 1, "b": 2}
        
        # __ror__
        res_r = d2 | l1
        assert res_r == {"b": 2, "a": 1}
        
        # __ior__
        l1 |= d2
        assert l1 == {"a": 1, "b": 2}

        # Type Error
        with pytest.raises(exceptions.OperandTypeError):
            l1 |= 1

        # NotImplemented
        assert l1.__or__(1) is NotImplemented
        assert l1.__ror__(1) is NotImplemented

    def test_sub(self):
        l1 = ConcreteLogical({"a": 1, "b": 2})
        d2 = {"b": 3}
        
        # __sub__
        res = l1 - d2
        assert res == {"a": 1}
        
        # __rsub__ (d2 - l1) -> {"b": 3} - {"a", "b"} -> {}
        res_r = d2 - l1
        assert res_r == {}
        
        # __isub__
        l1 -= d2
        assert l1 == {"a": 1}

        # Type Error
        with pytest.raises(exceptions.OperandTypeError):
            l1 -= 1

        # NotImplemented
        assert l1.__sub__(1) is NotImplemented
        assert l1.__rsub__(1) is NotImplemented

    def test_xor(self):
        l1 = ConcreteLogical({"a": 1, "b": 2})
        d2 = {"b": 3, "c": 4}
        
        # __xor__ -> a, c
        res = l1 ^ d2
        assert res == {"a": 1, "c": 4}
        
        # __rxor__
        res_r = d2 ^ l1
        assert res_r == {"c": 4, "a": 1}
        
        # __ixor__
        l1 ^= d2
        assert l1 == {"a": 1, "c": 4}

        # Type Error
        with pytest.raises(exceptions.OperandTypeError):
            l1 ^= 1

        # NotImplemented
        assert l1.__xor__(1) is NotImplemented
        assert l1.__rxor__(1) is NotImplemented

    def test_functional_aliases(self):
        l1 = ConcreteLogical({"a": 1})
        d2 = {"a": 1}
        
        assert l1.and_(d2) == {"a": 1}
        assert l1.or_(d2) == {"a": 1}
        assert l1.sub_(d2) == {} if hasattr(l1, 'sub_') else l1.sub(d2) == {}
        assert l1.xor(d2) == {}


# ---------- Tests 3: FormatterMixin Tests ----------
# --- Status: Done ---

import json
from types import SimpleNamespace

mock_compat = SimpleNamespace(
    HAS_NUMPY=False,
    HAS_PANDAS=False,
    HAS_YAML=False,
    numpy=None,
    pandas=None,
    yaml=None,
)
mock_utils_pkg = SimpleNamespace(compat=mock_compat)
sys.modules[f"{top_mod}.utils"] = mock_utils_pkg
sys.modules[f"{top_mod}.utils.compat"] = mock_compat


class ConcreteFormatter(mixins.FormatterMixin, dict):
    """Concrete class to test instance methods."""
    pass

class ConcreteFormatterChildren(ConcreteFormatter):
    def __init__(self, children):
        self.children = children

class TestFormatterMixin:

    @pytest.fixture
    def obj(self) -> ConcreteFormatter:
        """A sample object inheriting from FormatterMixin."""
        return ConcreteFormatter({"a": 1, "b": [2, 3]})

    # --- 1. Registry & API ---

    def test_register_style(self):
        """Test registering a custom style handler."""
        def custom_handler(obj, **kwargs):
            return "custom_output"
        
        mixins.FormatterMixin.register_style("custom", custom_handler)
        f = ConcreteFormatter()
        assert f.pprint(style="custom") == "custom_output"
        assert f.pprint(style="CUSTOM") == "custom_output"

    def test_pprint_dispatch_fallback(self, obj):
        """Test fallback to repr if style unknown."""
        output = obj.pprint(style="nonexistent_style")
        # Should look like repr({'a': 1, 'b': [2, 3]})
        assert "{'a': 1, 'b': [2, 3]}" in output or "{'b': [2, 3], 'a': 1}" in output

    # --- 2. JSON Style ---

    def test_pprint_json(self, obj):
        output = obj.pprint(style="json")
        data = json.loads(output)
        assert data["a"] == 1
        assert data["b"] == [2, 3]

    def test_pprint_json_error(self):
        """Test JSON serialization error handling."""
        def mock_serialize(obj):
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            return obj
        
        bad_obj = ConcreteFormatter()
        bad_obj["func"] = lambda x: x  # not JSON serializable
        
        with patch.object(mixins, "serialize", mock_serialize):
            output = bad_obj.pprint(style="json")
            assert "<JSON Serialization Error:" in output

    # --- 3. YAML Style ---

    def test_pprint_yaml_missing_lib(self, obj):
        """Test error when pyyaml is not installed."""
        # Force HAS_YAML to False
        compat.HAS_YAML = False
        
        with pytest.raises(exceptions.NoPyYAMLError):
            obj.pprint(style="yaml")

    def test_pprint_yaml_success(self, obj):
        """Test successful YAML output."""
        mock_compat.HAS_YAML = True
        mock_yaml = MagicMock()
        mock_yaml.safe_dump.return_value = "a: 1\nb: [2, 3]\n"
        mock_compat.yaml = mock_yaml

        output = obj.pprint(style="yaml")
        assert "a: 1" in output
        mock_yaml.safe_dump.assert_called_once()

    def test_pprint_yaml_error(self, obj):
        """Test YAML serialization internal error."""
        mock_compat.HAS_YAML = True
        mock_yaml = MagicMock()
        mock_yaml.safe_dump.side_effect = Exception("Boom")
        mock_compat.yaml = mock_yaml

        output = obj.pprint(style="yaml")
        assert "<YAML Serialization Error: Boom>" in output

    # --- 4. Default Style ---

    def test_default_primitives_no_color(self):
        f = ConcreteFormatter({"num": 10, "str": "hello"})
        output = f.pprint(style="default", colored=False, compact=True)
        # Check basic structure without ANSI codes
        assert "'num': 10" in output
        assert "'str': 'hello'" in output
        assert "\033[" not in output

    def test_default_coloring(self):
        f = ConcreteFormatter({"x": 1})
        output = f.pprint(style="default", colored=True)
        # Check for ANSI escape code start
        assert "\033[" in output

    def test_default_compact_vs_expanded(self):
        # Small list
        f = ConcreteFormatter({"l": [1, 2, 3]})
        
        # Compact
        out_compact = f.pprint(style="default", colored=False, compact=True)
        assert "[1, 2, 3]" in out_compact
        assert "\n" not in out_compact.replace(" {", "{").replace("} ", "}") # Ignore outer braces newlines if any

        # Expanded
        out_expanded = f.pprint(style="default", colored=False, compact=False)
        assert "[\n" in out_expanded
        assert "  1,\n" in out_expanded

    def test_default_nested_structure(self):
        f = ConcreteFormatter({
            "deep": {
                "list": [10, 20]
            }
        })
        output = f.pprint(style="default", colored=False, compact=True)
        assert "'deep': {" in output
        assert "'list': [10, 20]" in output

    def test_default_nested_structure_with_children(self):
        f = ConcreteFormatterChildren({
            "deep": {
                "set": {"foo", "bar"},
            }
        })
        output = f.pprint(style="default", colored=False, compact=True)
        assert "'deep': {" in output
        assert ("'set': {'foo', 'bar'}" in output) or ("'set': {'bar', 'foo'}" in output)

    def test_cycle_detection(self):
        """Test infinite recursion handling."""
        d = {}
        d["self"] = d
        f = ConcreteFormatter(d)
        
        output = f.pprint(style="default", colored=False)
        assert "<Cycle dict ...>" in output

    def test_multiline_string_indentation(self):
        """Test that multiline values (like long strings) get indented."""
        val = "Line1\nLine2\nLine3"
        f = ConcreteFormatter({"key": val})
        
        output = f.pprint(style="default", colored=False)
        assert "'key': 'Line1" in output

    # --- 5. Pandas & Numpy Integrations ---

    def test_pandas_dataframe(self):
        mock_compat.HAS_PANDAS = True
        
        # Mock DataFrame
        mock_df = MagicMock()
        mock_df.shape = (5, 2)

        class MockDataFrame:
            shape = (5, 2)
            def to_string(self, **kwargs):
                return "   A  B\n0  1  2"
        
        mock_compat.pandas = SimpleNamespace(DataFrame=MockDataFrame, Series=type("Series", (), {}))
        
        f = ConcreteFormatter({"df": MockDataFrame()})
        output = f.pprint(style="default", colored=False)
        
        assert "<MockDataFrame shape=(5, 2)>" in output
        assert "   A  B" in output
    
    def test_pandas_series(self):
        mock_compat.HAS_PANDAS = True

        # Mock Series
        mock_series = MagicMock()
        mock_series.shape = (5, 2)

        class MockSeries:
            shape = (5, 2)
            def to_string(self, **kwargs):
                return "   A  B\n0  1  2"
        
        mock_compat.pandas = SimpleNamespace(DataFrame=type("DataFrame", (), {}), Series=MockSeries)

        f = ConcreteFormatter({"series": MockSeries()})
        output = f.pprint(style="default", colored=False)

        assert "<MockSeries shape=(5, 2)>" in output
        assert "   A  B" in output
    
    def test_pandas_fallback(self):
        mock_compat.HAS_PANDAS = True

        # Mock DataFrame
        mock_df = MagicMock()
        mock_df.shape = (5, 2)

        class MockDataFrame:
            shape = (5, 2)
            def to_string(self, **kwargs):
                raise
            def __str__(self):
                return "MockDataFrame string"
        
        mock_compat.pandas = SimpleNamespace(DataFrame=MockDataFrame, Series=type("Series", (), {}))

        f = ConcreteFormatter({"df": MockDataFrame()})
        output = f.pprint(style="default", colored=False)
        assert "MockDataFrame string" in output

    def test_pandas_missing(self):
        """Ensure it prints as normal object if pandas is not installed."""
        mock_compat.HAS_PANDAS = False
        
        class FakeDF:
            def __repr__(self):
                return "FakeDF()"
            
        f = ConcreteFormatter({"df": FakeDF()})
        output = f.pprint(style="default", colored=False)
        assert "FakeDF()" in output

    def test_numpy_ndarray(self):
        mock_compat.HAS_NUMPY = True
        
        class MockArray:
            shape = (2, 2)
            dtype = "int64"
        
        mock_np = MagicMock()
        mock_np.ndarray = MockArray
        mock_np.array2string.return_value = "[[1, 2],\n [3, 4]]"
        mock_compat.numpy = mock_np
        
        f = ConcreteFormatter({"arr": MockArray()})
        output = f.pprint(style="default", colored=False)
        
        assert "<ndarray shape=(2, 2) dtype=int64>" in output
        assert "[[1, 2]" in output

    # --- 6. Edge Cases for Built-ins ---

    def test_tuple_trailing_comma(self):
        """Ensure single item tuple gets a trailing comma in compact mode."""
        f = ConcreteFormatter({"t": (1,)})
        output = f.pprint(style="default", colored=False, compact=True)
        assert "(1,)" in output

    def test_empty_containers(self):
        from collections import deque
        f = ConcreteFormatter({"l": [], "d": {}, "t": (), "de": deque()})
        output = f.pprint(style="default", colored=False, compact=True)
        assert "'l': []" in output
        assert "'d': {}" in output
        assert "'t': ()" in output
        assert "'de': []" in output
    
    def test_indent_arg(self):
        """Test the top-level indent argument."""
        f = ConcreteFormatter({"a": 1})
        output = f.pprint(style="default", indent=2, colored=False, compact=False)

        assert output.strip().startswith("ConcreteFormatter {")
        assert "'a': 1" in output
        assert "  'a': 1" in output  # 2 * 1 spaces
