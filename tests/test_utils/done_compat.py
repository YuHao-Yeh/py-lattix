# import sys
# import importlib
# import unittest
# from unittest.mock import patch

# from src.lattix.utils.exceptions import NoPyYAMLError

# # Define the list of modules involved in the conditional import chain
# YAML_TARGET_MODULES = [
#     'src.lattix.utils.compat',
#     'src.lattix.structure.mapping',
#     'src.lattix.serilaization.safe_yaml',
#     'src.lattix._core.mixins'
# ]

# class TestYamlCompatibility(unittest.TestCase):
#     def setUp(self):
#         """
#         Snapshot the current state of the modules.
#         """
#         self._original_modules = {}
        
#         # 1. Ensure the modules are actually loaded so we have something to save
#         for mod_name in YAML_TARGET_MODULES:
#             if mod_name not in sys.modules:
#                 try:
#                     importlib.import_module(mod_name)
#                 except ImportError:
#                     pass # Should not happen in valid env, but safety first

#             # 2. Save the REFERENCE to the existing module object.
#             #    We store the actual object (memory address), not a copy.
#             if mod_name in sys.modules:
#                 self._original_modules[mod_name] = sys.modules[mod_name]

#     def tearDown(self):
#         """
#         RESTORE the original module objects. 
#         This is critical for 'pickle' and 'isinstance' checks in other tests.
#         """
#         # 1. Clean up the temporary modules created during the test
#         for mod_name in YAML_TARGET_MODULES:
#             if mod_name in sys.modules:
#                 del sys.modules[mod_name]

#         # 2. Put the ORIGINAL objects back into sys.modules
#         for mod_name, mod_obj in self._original_modules.items():
#             sys.modules[mod_name] = mod_obj

#     def test_yaml_missing_behavior(self):
#         """Test behavior when 'yaml' is not installed."""
#         # 1. Remove existing modules from sys.modules so we can force a reload
#         #    (We have them saved in self._original_modules for restoration later)
#         for mod_name in YAML_TARGET_MODULES:
#             if mod_name in sys.modules:
#                 del sys.modules[mod_name]

#         # 2. Simulate 'yaml' being missing
#         with patch.dict(sys.modules, {'yaml': None}):
#             mod = "src.lattix"
            
#             # 3. Import modules (Reloading them in the "no-yaml" environment)
#             importlib.import_module(f"{mod}")
#             compat = importlib.import_module(f"{mod}.utils.compat")
#             lattix = importlib.import_module(f"{mod}.structures.mapping")
#             safe_yaml = importlib.import_module(f"{mod}.serialization.safe_yaml")
#             mixins = importlib.import_module(f"{mod}._core.mixins")

#             # 4. Assertions for NO YAML
#             self.assertFalse(compat.HAS_YAML, "compat.HAS_YAML should be False")
#             self.assertIsNone(compat.yaml, "compat.yaml should be None")

#             self.assertFalse(lattix.HAS_YAML)
#             self.assertIsNone(lattix.yaml)
            
#             self.assertFalse(safe_yaml.HAS_YAML)
#             self.assertIsNone(safe_yaml.yaml)
            
#             self.assertFalse(mixins.HAS_YAML)
#             self.assertIsNone(mixins.yaml)

#             # 5. Public API Error Checks
#             # lattix
#             with self.assertRaises(NoPyYAMLError):
#                 lattix.Lattix({"a": 1}).to_yaml()
            
#             # mixins
#             with self.assertRaises(NoPyYAMLError):
#                 mixins.FormatterMixin._pprint_yaml(None)
            
#             # safe_yaml
#             with self.assertRaises(NoPyYAMLError):
#                 safe_yaml.load(b"data")
            
#             with self.assertRaises(NoPyYAMLError):
#                 safe_yaml.dump({"a": 1})
            
#             # 6. EXPLICIT COVERAGE FOR STUBS
#             #    (We manually instantiate the fallback classes and call 
#             #    their methods to satisfy the coverage tool.)
#             # Loader Stub
#             loader = safe_yaml.Loader(stream="dummy_stream")
#             loader.construct_scalar(None)
#             loader.construct_sequence(None)
#             loader.construct_mapping(None)
#             # class method
#             safe_yaml.Loader.add_constructor("!tag", lambda x: x)

#             # Dumper Stub
#             dumper = safe_yaml.Dumper(stream="dummy_stream")
#             dumper.represent_scalar("!tag", "value")
#             dumper.represent_sequence("!tag", [])
#             dumper.represent_mapping("!tag", {})
#             dumper.represent_object({})

#             # class method
#             safe_yaml.Dumper.add_representer(int, lambda x: x)
#             safe_yaml.Dumper.add_multi_representer(int, lambda x: x)

#             # Test Inheritance Stubs (Just ensuring they exist)
#             _ = safe_yaml.SafeLoader("stream")
#             _ = safe_yaml.SafeDumper("stream")

#             # Test Node Stubs
#             _ = safe_yaml.ScalarNode()
#             _ = safe_yaml.SequenceNode()


#     def test_yaml_present_behavior(self):
#         """
#         Test behavior when 'yaml' IS installed (Standard Environment).
#         """
#         # 1. Remove modules to force a fresh load (sanity check)
#         for mod_name in YAML_TARGET_MODULES:
#             if mod_name in sys.modules:
#                 del sys.modules[mod_name]

#         # 2. Standard Import (No mocking of yaml)
#         mod = "src.lattix"
#         compat = importlib.import_module(f"{mod}.utils.compat")
#         lattix = importlib.import_module(f"{mod}.structures.mapping")
#         safe_yaml = importlib.import_module(f"{mod}.serialization.safe_yaml")
#         mixins = importlib.import_module(f"{mod}._core.mixins")

#         # 3. Assertions for YES YAML
#         # (Skipping this if PyYAML isn't actually installed in your CI env)
#         if compat.HAS_YAML:
#             self.assertIsNotNone(compat.yaml)
            
#             # Verify they are sharing the same object
#             self.assertIs(lattix.yaml, compat.yaml)
#             self.assertIs(safe_yaml.yaml, compat.yaml)
#             self.assertIs(mixins.yaml, compat.yaml)


# NP_PD_TARGET_MODULES = [
#     'src.lattix.utils.compat',
#     'src.lattix.adapters.generic',
#     'src.lattix._core.mixins'
# ]

# class TestNumpyPandasCompatibility(unittest.TestCase):
#     def setUp(self):
#         """Snapshot the current state of the modules."""
#         self._original_modules = {}
        
#         # 1. Ensure the modules are actually loaded so we have something to save
#         for mod_name in NP_PD_TARGET_MODULES:
#             if mod_name not in sys.modules:
#                 try:
#                     importlib.import_module(mod_name)
#                 except ImportError:
#                     pass # Should not happen in valid env, but safety first

#             # 2. Save the REFERENCE to the existing module object.
#             #    We store the actual object (memory address), not a copy.
#             if mod_name in sys.modules:
#                 self._original_modules[mod_name] = sys.modules[mod_name]

#     def tearDown(self):
#         """RESTORE the original module objects.

#         This is critical for 'pickle' and 'isinstance' checks in other tests.
#         """
#         # 1. Clean up the temporary modules created during the test
#         for mod_name in NP_PD_TARGET_MODULES:
#             if mod_name in sys.modules:
#                 del sys.modules[mod_name]

#         # 2. Put the ORIGINAL objects back into sys.modules
#         for mod_name, mod_obj in self._original_modules.items():
#             sys.modules[mod_name] = mod_obj

#     # ────────── numpy ──────────
#     def test_numpy_missing_behavior(self):
#         """Test behavior when 'numpy' is not installed."""
#         # 1. Remove existing modules from sys.modules so we can force a reload
#         for mod_name in NP_PD_TARGET_MODULES:
#             if mod_name in sys.modules:
#                 del sys.modules[mod_name]

#         # 2. Simulate 'numpy' being missing
#         with patch.dict(sys.modules, {'numpy': None}):
            
#             # 3. Import modules (Reloading them in the "no-yaml" environment)
#             mod = "src.lattix"
#             compat = importlib.import_module(f"{mod}.utils.compat")
#             adapters = importlib.import_module(f"{mod}.adapters.generic")
#             mixins = importlib.import_module(f"{mod}._core.mixins")

#             # 4. Assertions for NO numpy
#             self.assertFalse(compat.HAS_NUMPY, "compat.HAS_NUMPY should be False")
#             self.assertIsNone(compat.numpy, "compat.numpy should be None")

#             self.assertFalse(adapters.HAS_NUMPY)
#             self.assertIsNone(adapters.np)

#             self.assertFalse(mixins.HAS_NUMPY)
#             self.assertIsNone(mixins.np)

#             # 5. Public API Error Checks
#             self.assertIsNone(adapters.get_adapter("numpy"))

#     # ────────── pandas ──────────
#     def test_pandas_missing_behavior(self):
#         """Test behavior when 'pandas' is not installed."""
#         # 1. Remove existing modules from sys.modules so we can force a reload
#         for mod_name in NP_PD_TARGET_MODULES:
#             if mod_name in sys.modules:
#                 del sys.modules[mod_name]

#         # 2. Simulate 'pandas' being missing
#         with patch.dict(sys.modules, {'pandas': None}):
            
#             # 3. Import modules (Reloading them in the "no-yaml" environment)
#             mod = "src.lattix"
#             compat = importlib.import_module(f"{mod}.utils.compat")
#             adapters = importlib.import_module(f"{mod}.adapters.generic")
#             mixins = importlib.import_module(f"{mod}._core.mixins")

#             # 4. Assertions for NO numpy
#             self.assertFalse(compat.HAS_PANDAS, "compat.HAS_PANDAS should be False")
#             self.assertIsNone(compat.pandas, "compat.pandas should be None")

#             self.assertFalse(adapters.HAS_PANDAS)
#             self.assertIsNone(adapters.pd)

#             self.assertFalse(mixins.HAS_PANDAS)
#             self.assertIsNone(mixins.pd)

#             # 5. Public API Error Checks
#             self.assertIsNone(adapters.get_adapter("pandas"))




# ---------- version 3 ----------
import pytest
import sys
import types
from unittest.mock import patch, MagicMock

from src.lattix.utils import compat


# --- Fixtures ---

@pytest.fixture(autouse=True)
def clean_sys_modules():
    """
    Ensure specific modules are removed from sys.modules before and after tests
    to prevent caching interference.
    """
    targets = ["numpy", "pandas", "yaml", "fake_lib", "broken_lib"]
    saved = {}
    for t in targets:
        if t in sys.modules:
            saved[t] = sys.modules.pop(t)
    
    yield
    
    # cleanup
    for t in targets:
        if t in sys.modules:
            del sys.modules[t]
    sys.modules.update(saved)


# --- Tests 1: get_module ---

class TestGetModule:
    def test_get_module_cached(self):
        """Test branch: if name in sys.modules"""
        mock_obj = "CACHED_OBJECT"
        with patch.dict(sys.modules, {"fake_lib": mock_obj}):
            # Should return the object from cache, not attempt import
            with patch("importlib.import_module") as mock_import:
                assert compat.get_module("fake_lib") == mock_obj
                mock_import.assert_not_called()

    def test_get_module_import_success(self):
        """Test branch: importlib.import_module success"""
        with patch("importlib.import_module", return_value="IMPORTED") as mock_import:
            assert compat.get_module("fake_lib") == "IMPORTED"
            mock_import.assert_called_with("fake_lib")

    def test_get_module_import_error(self):
        """Test branch: except ImportError"""
        with patch("importlib.import_module", side_effect=ImportError):
            assert compat.get_module("fake_lib") is None

    def test_get_module_generic_exception(self):
        """Test branch: except Exception (e.g., SyntaxError in lib)"""
        with patch("importlib.import_module", side_effect=ValueError("Boom")):
            assert compat.get_module("broken_lib") is None


# --- Tests 2: has_module ---

class TestHasModule:
    def test_has_module_str_input(self):
        """Test input type: str"""
        with patch.object(compat, "get_module", return_value=True):
            assert compat.has_module("some_lib") is True

    def test_has_module_module_input(self):
        """Test input type: ModuleType"""
        mod = types.ModuleType("some_lib")
        with patch.object(compat, "get_module", return_value=True) as mock_get:
            assert compat.has_module(mod) is True
            mock_get.assert_called_with("some_lib")

    def test_has_module_class_input(self):
        """Test input type: Class (checks split logic)"""
        class MyClass:
            __module__ = "my_pkg.submodule"
        
        with patch.object(compat, "get_module", return_value=True) as mock_get:
            assert compat.has_module(MyClass) is True
            # Must strip .submodule and look for root package
            mock_get.assert_called_with("my_pkg")

    def test_has_module_cached_true(self):
        """Test branch: sys.modules check returns True"""
        with patch.dict(sys.modules, {"cached_lib": "exists"}):
            # Should not call get_module if in sys.modules
            with patch.object(compat, "get_module") as mock_get:
                assert compat.has_module("cached_lib") is True
                mock_get.assert_not_called()

    def test_has_module_cached_false(self):
        """Test branch: sys.modules check returns False (None)"""
        # This simulates a previously failed import
        with patch.dict(sys.modules, {"cached_lib": None}):
            assert compat.has_module("cached_lib") is False

    def test_has_module_not_cached(self):
        """Test branch: fallback to get_module"""
        # Case 1: Exists
        with patch.object(compat, "get_module", return_value="MOD"):
            assert compat.has_module("new_lib") is True
        
        # Case 2: Does not exist
        with patch.object(compat, "get_module", return_value=None):
            assert compat.has_module("missing_lib") is False


# --- Tests 3: __getattr__ (Lazy Loading) ---

class TestGetAttr:
    @pytest.mark.parametrize("attr, lib_name", [
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("yaml", "yaml"),
    ])
    def test_getattr_libs(self, attr, lib_name):
        """Test accessors: compat.numpy, compat.pandas, compat.yaml"""
        mock_lib = MagicMock()
        # Mock get_module to avoid real imports
        with patch.object(compat, "get_module", return_value=mock_lib) as mock_get:
            # Trigger __getattr__
            val = getattr(compat, attr)
            assert val is mock_lib
            mock_get.assert_called_with(lib_name)

    @pytest.mark.parametrize("attr, lib_name", [
        ("HAS_NUMPY", "numpy"),
        ("HAS_PANDAS", "pandas"),
        ("HAS_YAML", "yaml"),
    ])
    def test_getattr_flags(self, attr, lib_name):
        """Test flags: compat.HAS_NUMPY, etc."""
        with patch.object(compat, "has_module", return_value=True) as mock_has:
            # Trigger __getattr__
            val = getattr(compat, attr)
            assert val is True
            mock_has.assert_called_with(lib_name)

    def test_getattr_invalid(self):
        """Test branch: AttributeError for unknown names"""
        with pytest.raises(AttributeError, match="has no attribute 'invalid_attr'"):
            _ = compat.invalid_attr
