import sys
from unittest.mock import MagicMock, patch

import pytest

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
    def test_has_module_real_builtin(self):
        """Test with a module that definitely exists (json)."""
        assert compat.has_module("json") is True

    def test_has_module_non_existent(self):
        """Test with a module that definitely does not exist."""
        assert compat.has_module("non_existent_package_123") is False

    def test_has_module_cached(self):
        """Test that it correctly identifies modules already in sys.modules."""
        with patch.dict(sys.modules, {"fake_mod": MagicMock()}):
            assert compat.has_module("fake_mod") is True

        with patch.dict(sys.modules, {"cached_lib": None}):
            assert compat.has_module("cached_lib") is False

    @patch("importlib.util.find_spec")
    def test_has_flag_logic(self, mock_find_spec):
        """Test that HAS_XXX triggers the correct check without importing."""
        # Simulate yaml exists
        mock_find_spec.return_value = MagicMock()
        assert compat.HAS_YAML is True

        # Simulate pandas missing
        mock_find_spec.side_effect = lambda name: (
            None if name == "pandas" else MagicMock()
        )
        assert compat.HAS_PANDAS is False

        mock_find_spec.side_effect = ImportError
        assert compat.HAS_non is False

        # Ensure find_spec was called, not import_module
        assert mock_find_spec.called


# --- Tests 3: __getattr__ (Lazy Loading) ---


class TestGetAttr:

    def test_lazy_import_success(self):
        """Test that accessing the attribute actually imports the module."""
        with patch("importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            mock_import.return_value = mock_mod

            # This should trigger importlib.import_module("yaml")
            result = compat.yaml

            mock_import.assert_called_once_with("yaml")
            assert result == mock_mod

    def test_lazy_import_failure(self):
        """Test behavior when an optional module is missing."""
        with patch("importlib.import_module", side_effect=ImportError):
            assert compat.numpy is None

    def test_attribute_error(self):
        """Test that invalid attributes still raise AttributeError."""
        with pytest.raises(AttributeError) as excinfo:
            _ = compat.INVALID_ATTR_NAME
        assert "has no attribute 'INVALID_ATTR_NAME'" in str(excinfo.value)

    def test_sys_modules_cache(self):
        """Test that if a module is already loaded, it returns it from sys.modules."""
        mock_obj = MagicMock()
        with patch.dict(sys.modules, {"yaml": mock_obj}):
            assert compat.yaml == mock_obj

    @pytest.mark.parametrize(
        "mod_name", ["numpy", "pandas", "yaml", "orjson", "msgpack"]
    )
    def test_all_optional_placeholders(self, mod_name):
        """Ensure all declared optional modules respond to HAS_ and lazy loading."""

        with patch("importlib.import_module") as mock_import:
            with patch.dict("sys.modules", {mod_name: None}, clear=False):
                mock_mod = MagicMock()
                mock_import.return_value = mock_mod

                # Access the attribute (e.g., compat.numpy)
                val = getattr(compat, mod_name)

                # Verify the logic
                mock_import.assert_called_with(mod_name)
                assert val == mock_mod

        # Check HAS_ flag
        flag = f"HAS_{mod_name.upper()}"
        with patch("importlib.util.find_spec") as mock_find:
            mock_find.return_value = True
            assert isinstance(getattr(compat, flag), bool)
            assert getattr(compat, flag) is True

    def test_getattr_invalid(self):
        """Test branch: AttributeError for unknown names"""
        with pytest.raises(AttributeError, match="has no attribute 'invalid_attr'"):
            _ = compat.invalid_attr
