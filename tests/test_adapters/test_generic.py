from collections import ChainMap, defaultdict
from unittest.mock import ANY, MagicMock, patch

import pytest

from src.lattix import adapters
from src.lattix.adapters import registry

top_mod = "src.lattix"

# --- Fixtures ---


@pytest.fixture(autouse=True)
def reset_adapters():
    """
    Ensures a clean state for every test.
    Resets registries, handlers, and clears the LRU cache.
    """
    # 1. Snapshot
    original_adapters = registry._ADAPTERS.copy()
    original_handlers = registry._LAZY_LIBRARY_HANDLERS.copy()
    original_defaults = registry._CONSTRUCTOR_DEFAULTS.copy()

    yield

    # 2. Restore
    registry._ADAPTERS.clear()
    registry._ADAPTERS.update(original_adapters)

    registry._LAZY_LIBRARY_HANDLERS.clear()
    registry._LAZY_LIBRARY_HANDLERS.update(original_handlers)

    registry._CONSTRUCTOR_DEFAULTS.clear()
    registry._CONSTRUCTOR_DEFAULTS.update(original_defaults)

    # 3. Clear Caches
    registry._get_adapter_for_type.cache_clear()


# ---------- Tests 1: Adapters Registry/Logic ----------


class TestAdapters:
    # --- 1. Registry & Core ---

    def test_fqname_for_cls(self):
        class LocalClass:
            pass

        name = registry.fqname_for_cls(LocalClass)
        assert name.endswith("LocalClass")
        assert "test_adapters" in name  # module name usually included

    def test_adapter_registry_lifecycle(self):
        class Foo:
            pass

        def handler(x, r):
            return "bar"

        # Register
        registry.register_adapter(Foo, handler)
        assert registry.fqname_for_cls(Foo) in registry.get_adapter_registry()

        # Get
        adapter = adapters.get_adapter(Foo())
        assert adapter is handler
        assert adapter(None, None) == "bar"

        # Unregister
        registry.unregister_adapter(Foo)
        assert registry.fqname_for_cls(Foo) not in registry.get_adapter_registry()

        # Get (Should be None)
        assert adapters.get_adapter(Foo()) is None

    def test_unregister_non_existent(self):
        class Ghost:
            pass

        registry.unregister_adapter(Ghost)

    # --- 2. Adapter Lookup Logic ---

    def test_get_adapter_ingeritance(self):
        class Parent:
            pass

        class Child(Parent):
            pass

        class GrandChild(Child):
            pass

        registry.register_adapter(Parent, lambda x, r: "parent")

        # Should find Parent adapter for Child istance
        adapter = adapters.get_adapter(Child())
        assert adapter is not None
        assert adapter(None, None) == "parent"

        # 1. Direct
        assert adapters.get_adapter(Parent())(None, None) == "parent"

        # 2. Inherited (1 step)
        assert adapters.get_adapter(Child())(None, None) == "parent"

        # 3. Ingerited (2 steps)
        assert adapters.get_adapter(GrandChild())(None, None) == "parent"

    def test_adapter_lookup_miss(self):
        class Unknown:
            pass

        assert adapters.get_adapter(Unknown()) is None
        assert adapters.get_adapter(None) is None
        assert adapters.get_adapter(object) is None

    def test_get_adapter_lookup_logic_integration(self):
        # 1. None check
        assert adapters.get_adapter(None) is None

        # 2. Exact Match
        class Exact:
            pass

        registry.register_adapter(Exact, lambda x, r: "exact")
        assert adapters.get_adapter(Exact())(None, None) == "exact"

        # 3. Inheritance (MRO) Match
        class Child(Exact):
            pass

        assert adapters.get_adapter(Child())(None, None) == "exact"

        # 4. No Match
        class Unknown:
            pass

        assert adapters.get_adapter(Unknown()) is None

    # --- 3. Lazy Loading Logic (Internal) ---

    def test_ensure_library_adapters_logic(self):
        # 1. Object with no module (AttributeError branch)
        class Broken:
            @property
            def __module__(self):
                raise AttributeError

        registry._ensure_library_adapters(Broken())  # Should not crash

        # 2. Handler not exist
        class BadLibObj:
            __module__ = "badlib"

        registry._LAZY_LIBRARY_HANDLERS.add("badlib")
        with patch(f"{top_mod}.adapters.registry.logger") as mock_logger:
            registry._ensure_library_adapters(BadLibObj())
            assert mock_logger.error.call_count == 0

        # 3. Handler raises exception
        with patch(
            f"{top_mod}.adapters.numpy._register_numpy_adapters",
            side_effect=RuntimeError("Mock Crash"),
        ):
            with patch(f"{top_mod}.adapters.registry.logger") as mock_log:

                class FakeNP:
                    __module__ = "numpy"

                registry._ensure_library_adapters(FakeNP())

                mock_log.error.assert_called_with(
                    "Failed to load numpy adapter: Mock Crash"
                )

    # --- 4. Specific Library Adapters ---

    def test_library_early_exits(self):
        """
        Covers lines like 'if not np_pkg: return' inside register functions.
        We force get_module to return None.
        """
        from src.lattix.adapters import numpy, pandas, torch, xarray

        with patch(f"{top_mod}.utils.compat.HAS_NUMPY", False):
            numpy._register_numpy_adapters()
        assert "numpy.ndarray" not in registry._ADAPTERS

        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", False):
            pandas._register_pandas_adapters()
        assert "pandas.DataFrame" not in registry._ADAPTERS

        with patch(f"{top_mod}.utils.compat.HAS_TORCH", False):
            torch._register_torch_adapters()
        assert "torch.Tensor" not in registry._ADAPTERS

        with patch(f"{top_mod}.utils.compat.HAS_XARRAY", False):
            xarray._register_xarray_adapters()
        assert "xarray.DataArray" not in registry._ADAPTERS

    def test_lazy_numpy(self):
        from src.lattix.adapters import numpy as np_mod

        # Simulate numpy.ndarray
        class FakeArray:
            __module__ = "numpy"

            def __init__(self, fail=False):
                self._fail = fail

            def tolist(self):
                if self._fail:
                    raise ValueError("Simulated Error")
                return [1, 2, 3]

            def __iter__(self):
                yield 1
                yield 2
                yield 3

        # Case 1: Library Missing
        with patch(f"{top_mod}.utils.compat.HAS_NUMPY", False):
            with patch(f"{top_mod}.utils.compat.numpy", None):
                adapters.get_adapter(FakeArray())
                # Should not have registered adapter
                assert registry.fqname_for_cls(FakeArray) not in registry._ADAPTERS

        # Case 2: Library Present & Adapter Logic
        with patch(f"{top_mod}.utils.compat.HAS_NUMPY", True):
            with patch(f"{top_mod}.utils.compat.numpy") as mock_np:
                mock_np.ndarray = FakeArray
                np_mod._register_numpy_adapters()

                # Trigger Resigtration
                adapter = adapters.get_adapter(FakeArray())
                assert adapter is not None

                # Test Logic: tolist() success
                assert adapter(FakeArray(), None) == [1, 2, 3]

                # Test Logic: tolist() failure -> list() fallback
                bad_arr = FakeArray(fail=True)
                assert adapter(bad_arr, None) == [1, 2, 3]  # fallback to list()

    def test_lazy_pandas(self):
        from src.lattix.adapters import pandas as pd_mod

        # Simulate pandas.Series
        class FakeSeries:
            __module__ = "pandas"
            __qualname__ = "Series"

            def tolist(self):
                return ["s"]

        # Simulate pandas.DataFrame
        class FakeDataFrame:
            __module__ = "pandas"
            __qualname__ = "DataFrame"

            def __init__(self, fail=False):
                self.fail = fail

            def to_dict(self, orient=None):
                if self.fail and orient == "list":
                    raise ValueError("Fail")
                if orient == "list":
                    return {"a": [1]}
                return {"a": 1}  # fallback format

        # Case 1: Missing
        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", False):
            with patch(f"{top_mod}.utils.compat.pandas", None):
                adapters.get_adapter(FakeSeries())
                assert registry.fqname_for_cls(FakeSeries) not in registry._ADAPTERS

                adapters.get_adapter(FakeDataFrame())
                assert registry.fqname_for_cls(FakeDataFrame) not in registry._ADAPTERS

        # Case 2: Present
        with patch(f"{top_mod}.utils.compat.HAS_PANDAS", True):
            with patch(f"{top_mod}.utils.compat.pandas") as mock_pd:
                mock_pd.Series = FakeSeries
                mock_pd.DataFrame = FakeDataFrame
                pd_mod._register_pandas_adapters()

                # --- Test Series ---
                adapters.get_adapter(FakeSeries())

                # Verify it was registered
                key = registry.fqname_for_cls(FakeSeries)
                assert key in registry._ADAPTERS

                # Get registered adapters
                s_adapter = adapters.get_adapter(FakeSeries())
                assert s_adapter(FakeSeries(), None) == ["s"]

                # --- Test DataFrame ---
                adapters.get_adapter(FakeDataFrame())

                key = registry.fqname_for_cls(FakeDataFrame)
                assert key in registry._ADAPTERS

                df_adapter = adapters.get_adapter(FakeDataFrame())
                assert df_adapter(FakeDataFrame(), None) == {"a": [1]}
                assert df_adapter(FakeDataFrame(fail=True), None) == {
                    "a": 1
                }  # fallback

    def test_lazy_torch(self):
        from src.lattix.adapters import torch as torch_md

        class FakeTensor:
            __module__ = "torch"

            def __init__(self, fail=False):
                self.fail = fail
                self.data = self  # simpler for Parameter test

            def tolist(self):
                if self.fail:
                    raise ValueError("Fail")
                return [10, 20]

            def detach(self):
                return self

            def cpu(self):
                return self

            def numpy(self):
                m = MagicMock()
                m.tolist.return_value = [1, 2, 3]
                return m

        class FakeParam:
            __module__ = "torch"

            def __init__(self):
                self.data = FakeTensor()

        with patch(f"{top_mod}.utils.compat.HAS_TORCH", True):
            with patch(f"{top_mod}.utils.compat.torch") as mock_torch:
                mock_torch.Tensor = FakeTensor
                mock_torch.nn.Parameter = FakeParam
                torch_md._register_torch_adapters()

                # --- Test Tensor ---
                # Trigger
                adapters.get_adapter(FakeTensor())

                # Check Tensor Adapter
                t_key = registry.fqname_for_cls(FakeTensor)
                assert t_key in registry._ADAPTERS

                # Get
                t_adapter = adapters.get_adapter(FakeTensor())

                assert t_adapter(FakeTensor(), None) == [10, 20]
                assert t_adapter(FakeTensor(fail=True), None) == [
                    1,
                    2,
                    3,
                ]  # Fallback (detach cpu)

                # -- Test Parameter ---
                # Check Parameter Adapter
                p_key = registry.fqname_for_cls(FakeParam)
                assert p_key in registry._ADAPTERS

                p_adapter = adapters.get_adapter(FakeParam())

                # Param logic just calls tensor logic
                assert p_adapter(FakeParam(), lambda x: x) == [10, 20]

    def test_lazy_torch_missing_components(self):
        from src.lattix.adapters import torch as tm_mod

        class FakeTensor:
            __module__ = "torch"

            def tolist(self):
                return []

        with patch(f"{top_mod}.utils.compat.HAS_TORCH", True):
            with patch(f"{top_mod}.utils.compat.torch") as mock_torch:
                with patch.object(tm_mod, "register_adapter") as mock_register:
                    # Case 1: torch has no "nn" attribute
                    mock_torch.Tensor = FakeTensor
                    if hasattr(mock_torch, "nn"):
                        del mock_torch.nn

                    tm_mod._register_torch_adapters()

                    mock_register.assert_any_call(FakeTensor, ANY)

                    # Assert nothing else was registered (Parameter logic skipped)
                    assert mock_register.call_count == 1

                    # Case 2: torch.nn has no "Parameter" attribute
                    mock_register.reset_mock()
                    mock_nn = MagicMock()
                    if hasattr(mock_nn, "Parameter"):
                        del mock_nn.Parameter
                    mock_torch.nn = mock_nn

                    tm_mod._register_torch_adapters()

                    mock_register.assert_any_call(FakeTensor, ANY)

                    # Assert nothing else was registered (Parameter logic skipped)
                    assert mock_register.call_count == 1

    def test_lazy_xarray(self):
        from src.lattix.adapters import xarray as xr_mod

        # Simulate DataArray
        class FakeDataArray:
            __module__ = "xarray"

            def __init__(self, fail=False):
                self.values = MagicMock()
                if fail:
                    self.values.tolist.side_effect = ValueError
                    self.values.__iter__.return_value = [3, 4]
                else:
                    self.values.tolist.return_value = [1, 2]

        # Simulate Dataset
        class FakeDataset:
            __module__ = "xarray"

            def __init__(self):
                self.data_vars = {"x": FakeDataArray()}

        with patch(f"{top_mod}.utils.compat.HAS_XARRAY", True):
            with patch(f"{top_mod}.utils.compat.xarray") as mock_xr:
                mock_xr.DataArray = FakeDataArray
                mock_xr.Dataset = FakeDataset
                xr_mod._register_xarray_adapters()

                adapters.get_adapter(FakeDataArray())

                # DataArray Logic
                da_adapter = adapters.get_adapter(FakeDataArray())
                assert da_adapter(FakeDataArray(), None) == [1, 2]
                assert da_adapter(FakeDataArray(fail=True), None) == [3, 4]

                # Dataset Logic
                ds_adapter = adapters.get_adapter(FakeDataset())
                res = ds_adapter(FakeDataset(), None)
                assert res["x"] == [1, 2]

    # --- 5. Builtins Adapters ---

    def test_builtin_defaultdict(self):
        # Setup
        dd = defaultdict(int, {"a": 1})
        adapter = adapters.get_adapter(dd)

        # Recurse Mock
        recurse = lambda x: x * 2

        res = adapter(dd, recurse)
        assert res == {"a": 2}
        assert isinstance(res, defaultdict)

    def test_builtin_chainmap(self):
        cm = ChainMap({"a": 1}, {"b": 2})
        adapter = adapters.get_adapter(cm)

        recurse = lambda x: x * 10

        res = adapter(cm, recurse)
        assert res == {"a": 10, "b": 20}
        assert isinstance(res, dict)  # It converts to dict


# ---------- Tests 2: Construction Registry/Logic ----------


class TestConstruction:
    # --- 1. Registry ---
    def test_constructor_defaults_registry(self):
        class MyList(list):
            pass

        # Register
        registry.register_constructor_defaults(MyList, _posargs=[1], _expand=True)
        reg = registry.get_defaults_registry()
        name = registry.fqname_for_cls(MyList)

        assert name in reg
        assert reg[name]["_expand"] is True

        # Unregister
        registry.unregister_constructor_defaults(MyList)
        assert name not in registry.get_defaults_registry()

        # Unregister safe check
        registry.unregister_constructor_defaults(MyList)  # No error

    # --- 2. Construct from Iterable ---

    def test_construct_str_special_cases(self):
        # 1. Normal
        assert registry.construct_from_iterable(str, ["a", "b"]) == "['a', 'b']"
        assert registry.construct_from_iterable(str, [1, 2]) == "[1, 2]"

        # 2. Exception Trigger -> Fallback
        class BadStr:
            def __str__(self):
                raise ValueError("Fail str")

            def __repr__(self):
                return "BadStrObj"

        result = registry.construct_from_iterable(str, [BadStr()])
        assert "BadStrObj" in result

    def test_construct_direct_success(self):
        assert registry.construct_from_iterable(set, [1, 2, 3]) == {1, 2, 3}
        assert registry.construct_from_iterable(set, [1, 2, 3, 3]) == {1, 2, 3}

    def test_construct_with_defaults_expand(self):
        class Container:
            def __init__(self, a, b, **kwargs):
                self.a = a
                self.b = b
                self.kwargs = kwargs

        registry.register_constructor_defaults(Container, _expand=True, other_flag=True)

        # direct: Container([1, 2]) -> TypeError (missing b) -> Caught
        # default: Container(*[1, 2], other_flag=True) -> Container(1, 2, other_flag=True) -> Success

        obj = registry.construct_from_iterable(Container, [1, 2])
        assert obj.a == 1
        assert obj.b == 2
        assert obj.kwargs == {"other_flag": True}

    def test_construct_with_defaults_posargs(self):
        class Wrapper:
            def __init__(self, label, data, extra=None):
                self.label = label
                self.data = data
                self.extra = extra

        registry.register_constructor_defaults(Wrapper, _posargs=["mylabel"], extra=99)

        # direct: Wrapper([1,2]) -> TypeError (missing args) -> Caught
        # default: Wrapper("mylabel", [1,2], extra=99) -> Success

        obj = registry.construct_from_iterable(Wrapper, [1, 2])
        assert obj.label == "mylabel"
        assert list(obj.data) == [1, 2]
        assert obj.extra == 99

    def test_construct_defaults_exception_fallbacks(self):
        # Case: Defaults registered but init fails -> Fallback to list

        class CrashInit:
            def __init__(self, *args, **kwargs):
                raise ValueError("Crasher")

        registry.register_constructor_defaults(CrashInit, _expand=True)

        # Should fallback to list(iterable)
        res = registry.construct_from_iterable(CrashInit, [1, 2])
        assert res == [1, 2]

    def test_construct_direct_init_fail_no_defaults(self):
        # Case: Direct init fails, no defaults registered -> fallback list
        class NoIterInit:
            def __init__(self, x):
                raise TypeError("Not iterable")

        res = registry.construct_from_iterable(NoIterInit, [1, 2])
        assert res == [1, 2]

    # --- 3. Construct from Mapping ---

    def test_str_conversion(self):
        items = [("a", 1), ("b", 2)]
        result = registry.construct_from_mapping(str, items)
        assert result == "{'a': 1, 'b': 2}"

    def test_direct_constructor(self):
        items = [("a", 1)]
        result = registry.construct_from_mapping(dict, items)
        assert result == {"a": 1}
        assert isinstance(result, dict)

    def test_fallback_unregistered(self):
        class NoInitMap(dict):
            def __init__(self):
                pass

        items = [("a", 1)]
        result = registry.construct_from_mapping(NoInitMap, items)
        assert result == {"a": 1}
        assert type(result) is dict  # It fell back to standard dict

    def test_registered_defaults_standard(self):
        class CustomMap:
            def __init__(self, tag, data, limit=10):
                self.tag = tag
                self.data = data
                self.limit = limit

            def __eq__(self, other):
                return (
                    self.tag == other.tag
                    and self.data == other.data
                    and self.limit == other.limit
                )

        registry.register_constructor_defaults(CustomMap, _posargs=["TEST"], limit=99)

        items = [("x", 1)]
        result = registry.construct_from_mapping(CustomMap, items)

        # Expect: CustomMap("TEST", {"x": 1}, limit=99)
        assert isinstance(result, CustomMap)
        assert result.tag == "TEST"
        assert result.data == {"x": 1}
        assert result.limit == 99

    def test_registered_defaults_expand(self):
        # A class where we want (data, **kwargs), skipping posargs logic
        class ExpandMap:
            def __init__(self, data, extra=0):
                if not isinstance(data, dict):
                    raise TypeError("I only accept dicts, not lists!")
                self.data = data
                self.extra = extra

        registry.register_constructor_defaults(ExpandMap, _expand=True, extra=5)

        items = [("y", 2)]
        result = registry.construct_from_mapping(ExpandMap, items)

        assert isinstance(result, ExpandMap)
        assert result.data == {"y": 2}
        assert result.extra == 5

    def test_registered_defaults_exception(self):
        class BrokenMap(dict):
            def __init__(self, *args, **kwargs):
                raise ValueError("I refuse to exist")

        registry.register_constructor_defaults(BrokenMap, some_arg=1)

        items = [("z", 3)]

        # 1. BrokenMap(items) -> crashes (caught Step 1)
        # 2. Registered logic -> calls BrokenMap(..., items, ...) -> crashes (caught Step 2)
        # 3. Fallback -> returns dict
        result = registry.construct_from_mapping(BrokenMap, items)

        assert result == {"z": 3}
        assert type(result) is dict


# ---------- Tests 3: Plugins ----------


class TestPluginLogic:
    def test_plugin_discovery(self):
        # 1. Import Error (package level)
        with patch(
            f"{top_mod}.adapters.registry.import_module", side_effect=ImportError
        ):
            assert registry.discover_and_register_plugins("missing_pkg") == []

        # 2. No __path__ (not a package)
        mock_mod = MagicMock()
        del mock_mod.__path__
        with patch(f"{top_mod}.adapters.registry.import_module", return_value=mock_mod):
            assert registry.discover_and_register_plugins("simple_mod") == []

        # 3. Iter modules (Success & Fail mixed)
        mock_pkg = MagicMock()
        mock_pkg.__path__ = ["/fake/path"]
        mock_pkg.__name__ = "mypkg"

        with patch(f"{top_mod}.adapters.registry.import_module") as mock_import:
            mock_import.return_value = mock_pkg

            # pkgutil returns (finder, name, ispkg)
            with patch(
                "pkgutil.iter_modules",
                return_value=[
                    (None, "good_plugin", False),
                    (None, "bad_plugin", False),
                ],
            ):
                # Define import behavior for plugins
                def import_side_effect(name):
                    if name == "mypkg":
                        return mock_pkg
                    if name == "good_plugin":
                        return MagicMock()
                    if name == "bad_plugin":
                        raise ImportError("Plugin load failed")

                mock_import.side_effect = import_side_effect

                with patch(f"{top_mod}.adapters.registry.logger") as mock_logger:
                    found = registry.discover_and_register_plugins("mypkg")

                    assert "good_plugin" in found
                    assert "bad_plugin" not in found

                    # Ensure warning was logged for bad_plugin
                    mock_logger.error.assert_called()
