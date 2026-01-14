import json
from threading import RLock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.lattix.core import mixins
from src.lattix.utils import exceptions

top_mod = "src.lattix"

# ---------- Tests 1: ThreadingMixin ----------


class ConcreteNode(mixins.ThreadingMixin):
    def __init__(self, parent=None, enable_lock=False):
        self.children = []
        self._init_threading(parent, enable_lock)

    @staticmethod
    def _propagate_lock(obj, enable, lock, seen=None):
        # Concrete implementation of the abstract method
        if seen is None:
            seen = set()
        if obj in seen:
            return
        seen.add(obj)

        object.__setattr__(obj, "_locking_enabled", enable)
        object.__setattr__(obj, "_lock", lock)

        # Propagate to children
        if hasattr(obj, "children"):
            for child in obj.children:
                child._propagate_lock(child, enable, lock, seen)

    def add_child(self, child):
        self.children.append(child)
        # Manually attach logic usually happens here in real containers
        child.attach_thread(self)


class TestThreadingMixin:

    # --- 1. Init ---

    def test_init_defaults(self):
        """Test initialization without locking."""
        node = ConcreteNode(enable_lock=False)
        assert node.locking_enabled is False
        assert node._lock is None
        assert node._detached is True

    def test_init_enabled(self):
        """Test initialization with locking enabled."""
        node = ConcreteNode(enable_lock=True)
        assert node.locking_enabled is True
        assert node._lock is not None
        assert isinstance(node._lock, type(RLock()))
        assert node._detached is True

    def test_init_validation(self):
        """Test validation of enable_lock argument."""
        with pytest.raises(exceptions.ArgTypeError):
            ConcreteNode(enable_lock="NotABool")

    def test_inheritance_init(self):
        """Test inheriting lock from parent during init."""
        parent = ConcreteNode(enable_lock=True)
        child = ConcreteNode(parent=parent)

        assert child.locking_enabled is True
        assert child._lock is parent._lock  # Identity check
        assert child._detached is False

    # --- 2. Propagate Lock ---
    def test_propagate_lock(sel):
        """Test the propagation of lock."""
        from threading import RLock

        parent = ConcreteNode(enable_lock=False)
        child = ConcreteNode(enable_lock=False)
        parent.add_child(child)

        # Pre-condition
        assert child in parent.children
        assert child._lock is None
        assert child._detached is False

        # None -> RLock()
        parent.propagate_lock(True, RLock())
        assert child.locking_enabled is True
        assert child._lock is parent._lock
        assert child._detached is False
        assert parent._detached is True

        parent.propagate_lock(False, None)
        assert child.locking_enabled is False
        assert child._lock is None

    # --- 3. Attach ---

    def test_attach_thread(self):
        """Test attaching a detached node to a parent."""
        parent = ConcreteNode(enable_lock=True)
        child = ConcreteNode(enable_lock=False)

        # Pre-condition
        assert child._lock is None

        child.attach_thread(parent)

        assert child.locking_enabled is True
        assert child._lock is parent._lock
        assert child._detached is False

    def test_attach_errors(self):
        """Test errors when attaching invalid objects."""
        parent = ConcreteNode(enable_lock=True)

        # 1. Invalid parent type
        child = ConcreteNode()
        with pytest.raises(exceptions.ArgTypeError):
            child.attach_thread("NotAThreadingMixin")

        # 2. Child already has a lock (LockExistenceError)
        locked_child = ConcreteNode(enable_lock=True)
        with pytest.raises(exceptions.LockExistenceError):
            locked_child.attach_thread(parent)

        # 3. Child already attached (UnattachableError)
        child_clean = ConcreteNode()
        child_clean.attach_thread(parent)  # First attach works

        other_parent = ConcreteNode(enable_lock=True)
        with pytest.raises(exceptions.UnattachableError):
            child_clean.attach_thread(other_parent)  # Second fails

    # --- 4. Transplant ---

    def test_transplant_thread(self):
        """Test transplanting works even if validation would fail for attach."""
        parent = ConcreteNode(enable_lock=True)
        child = ConcreteNode(enable_lock=True)  # Has its own lock

        # Attach would fail here, but transplant should succeed
        child.transplant_thread(parent)

        assert child._lock is parent._lock
        assert child._detached is False

    # --- 5. Detach ---

    def test_detach_thread(self):
        """Test detaching preserves configuration but changes lock instance."""
        parent = ConcreteNode(enable_lock=True)
        child = ConcreteNode(parent=parent)

        old_lock = child._lock

        # Detach without clearing
        child.detach_thread(clear_locks=False)

        assert child._detached is True
        assert child.locking_enabled is True
        assert child._lock is not old_lock  # Should be a new lock
        assert child._lock is not None

    def test_detach_thread_clear(self):
        """Test detaching and clearing locks."""
        node = ConcreteNode(enable_lock=True)

        node.detach_thread(clear_locks=True)

        assert node.locking_enabled is False
        assert node._lock is None
        assert node._detached is True

    # --- 6. Properties ---

    def test_property_setter_enable(self):
        """Test enabling lock via property propagates to children."""
        root = ConcreteNode(enable_lock=False)
        child = ConcreteNode(enable_lock=False)
        root.add_child(child)  # child attaches to root

        # Enable on root
        root.locking_enabled = True

        assert root.locking_enabled is True
        assert root._lock is not None
        # Propagation check
        assert child.locking_enabled is True
        assert child._lock is root._lock

    def test_property_setter_disable(self):
        """Test disabling lock via property propagates to children."""
        root = ConcreteNode(enable_lock=True)
        child = ConcreteNode(parent=root)
        root.children.append(child)  # Link for propagation

        # Disable on root
        root.locking_enabled = False

        assert root.locking_enabled is False
        assert root._lock is None
        # Propagation check
        assert child.locking_enabled is False
        assert child._lock is None

    def test_property_setter_validation(self):
        node = ConcreteNode()
        with pytest.raises(exceptions.ArgTypeError):
            node.locking_enabled = 1  # Int instead of bool

    # --- 7. Context Manager ---

    def test_context_manager_and_locking(self):
        """Test that with statement acquires/releases lock."""
        node = ConcreteNode(enable_lock=True)

        with node:
            # RLock internal method (implementation dependent, works in CPython)
            assert node._lock._is_owned()

        assert not node._lock._is_owned()

    def test_locking_disabled_behavior(self):
        """Test acquire returns False when disabled."""
        node = ConcreteNode(enable_lock=False)

        result = node.acquire()
        assert result is False

        # Release should do nothing (no error)
        node.release()

        # Context manager should do nothing
        with node:
            pass

    # --- 8. Representation ---

    def test_describe_lock(self):
        node = ConcreteNode(enable_lock=True)
        desc = node._describe_lock()
        assert "lock=" in desc
        assert "enabled=True" in desc


# ---------- Tests 2: LogicalMixin Tests ----------


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
            if k in self:
                res[k] = self[k]
            else:
                res[k] = other[k]

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
        assert res_r == {"b": 3}  # Took value from d2 (left side)

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
        assert l1.sub_(d2) == {} if hasattr(l1, "sub_") else l1.sub(d2) == {}
        assert l1.xor(d2) == {}


# ---------- Tests 3: FormatterMixin Tests ----------


class ConcreteFormatter(mixins.FormatterMixin, dict):
    """Concrete class to test instance methods."""

    pass


class ConcreteFormatterChildren(ConcreteFormatter):
    def __init__(self, children):
        self._children = children


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
        with patch(f"{top_mod}.utils.compat.HAS_YAML", False):
            with pytest.raises(exceptions.OptionalImportError):
                obj.pprint(style="yaml")

    def test_pprint_yaml_success(self, obj):
        """Test successful YAML output."""
        mock_yaml = MagicMock()
        mock_yaml.safe_dump.return_value = "a: 1\nb: [2, 3]"

        with patch(f"{top_mod}.utils.compat.HAS_YAML", True):
            with patch(f"{top_mod}.utils.compat.yaml", mock_yaml):

                output = obj.pprint(style="yaml")
                assert "a: 1" in output
                mock_yaml.safe_dump.assert_called_once()

    def test_pprint_yaml_error(self, obj):
        """Test YAML serialization internal error."""
        mock_yaml = MagicMock()
        mock_yaml.safe_dump.side_effect = Exception("Boom")

        with patch(f"{top_mod}.utils.compat.HAS_YAML", True):
            with patch(f"{top_mod}.utils.compat.yaml", mock_yaml):

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
        assert "\n" not in out_compact.replace(" {", "{").replace(
            "} ", "}"
        )  # Ignore outer braces newlines if any

        # Expanded
        out_expanded = f.pprint(style="default", colored=False, compact=False)
        assert "[\n" in out_expanded
        assert "  1,\n" in out_expanded

    def test_default_nested_structure(self):
        f = ConcreteFormatter({"deep": {"list": [10, 20]}})
        output = f.pprint(style="default", colored=False, compact=True)
        assert "'deep': {" in output
        assert "'list': [10, 20]" in output

    def test_default_nested_structure_with_children(self):
        f = ConcreteFormatterChildren(
            {
                "deep": {
                    "set": {"foo", "bar"},
                }
            }
        )
        output = f.pprint(style="default", colored=False, compact=True)
        assert "'deep': {" in output
        assert ("'set': {'foo', 'bar'}" in output) or (
            "'set': {'bar', 'foo'}" in output
        )

    def test_cycle_detection(self):
        """Test infinite recursion handling."""
        d = {}
        d["self"] = d
        f = ConcreteFormatter(d)

        output = f.pprint(style="default", colored=False)
        assert "<Circular dict " in output

    def test_multiline_string_indentation(self):
        """Test that multiline values (like long strings) get indented."""
        val = "Line1\nLine2\nLine3"
        f = ConcreteFormatter({"key": val})

        output = f.pprint(style="default", colored=False)
        assert "'key': 'Line1" in output

    # --- 5. Pandas & Numpy Integrations ---

    def test_pandas_dataframe(self):
        class MockDataFrame:
            shape = (5, 2)

            def to_string(self, **kwargs):
                return "   A  B\n0  1  2"

        mock_pd = SimpleNamespace(
            DataFrame=MockDataFrame,
            Series=type("Series", (), {}),
        )

        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", True):
            with patch(f"{top_mod}.utils.compat.pandas", mock_pd):

                f = ConcreteFormatter({"df": MockDataFrame()})
                output = f.pprint(style="default", colored=False)

                assert "<MockDataFrame shape=(5, 2)>" in output
                assert "   A  B" in output

    def test_pandas_series(self):
        class MockSeries:
            shape = (5, 2)

            def to_string(self, **kwargs):
                return "   A  B\n0  1  2"

        mock_pd = SimpleNamespace(
            DataFrame=type("DataFrame", (), {}),
            Series=MockSeries,
        )

        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", True):
            with patch(f"{top_mod}.utils.compat.pandas", mock_pd):

                f = ConcreteFormatter({"series": MockSeries()})
                output = f.pprint(style="default", colored=False)

                assert "<MockSeries shape=(5, 2)>" in output
                assert "   A  B" in output

    def test_pandas_fallback(self):
        class MockDataFrame:
            shape = (5, 2)

            def to_string(self, **kwargs):
                raise

            def __str__(self):
                return "MockDataFrame string"

        mock_pd = SimpleNamespace(
            DataFrame=MockDataFrame,
            Series=type("Series", (), {}),
        )

        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", True):
            with patch(f"{top_mod}.utils.compat.pandas", mock_pd):

                f = ConcreteFormatter({"df": MockDataFrame()})
                output = f.pprint(style="default", colored=False)
                assert "MockDataFrame string" in output

    def test_pandas_missing(self):
        """Ensure it prints as normal object if pandas is not installed."""

        class FakeDF:
            def __repr__(self):
                return "FakeDF()"

        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", False):
            f = ConcreteFormatter({"df": FakeDF()})
            output = f.pprint(style="default", colored=False)
            assert "FakeDF()" in output

    def test_numpy_ndarray(self):
        class MockArray:
            shape = (2, 2)
            dtype = "int64"

        mock_np = MagicMock()
        mock_np.ndarray = MockArray
        mock_np.array2string.return_value = "[[1, 2],\n [3, 4]]"

        with patch(f"{top_mod}.utils.compat.HAS_NUMPY", True):
            with patch(f"{top_mod}.utils.compat.numpy", mock_np):

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
