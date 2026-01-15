# ruff: noqa: F401
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.lattix.utils import inspection, text

top_mod = "src.lattix"
utils_mod = top_mod + ".utils"


# ---------- Tests 1: Scan Class Attributes ----------


class TestScanClassAttrs:
    def test_scan_attrs(self):
        class Base:
            base_attr = 1

        class Child(Base):
            child_attr = 2

        attrs = inspection.scan_class_attrs(Child)
        assert "base_attr" in attrs
        assert "child_attr" in attrs

    def test_scan_excludes_object(self):
        """Ensure `if base is object: continue` is hit."""
        inspection.scan_class_attrs.cache_clear()

        class Simple:
            x = 1

        attrs = inspection.scan_class_attrs(Simple)
        assert "x" in attrs

    def test_scan_cache(self):
        class A:
            pass

        inspection.scan_class_attrs(A)
        inspection.scan_class_attrs(A)


# ---------- Tests 2: Other Helpers ----------


class TestHelpers:
    def test_strip_ansi(self):
        txt = "\x1b[31mRed\x1b[0m Text"
        assert text.strip_ansi(txt) == "Red Text"
        txt = "\x1b[31mHello\x1b[0m"
        assert text.strip_ansi(txt) == "Hello"

    def test_is_primitive(self):
        assert inspection.is_primitive(1) is True
        assert inspection.is_primitive(object()) is False

    def test_is_scalar_primitive(self):
        assert inspection.is_scalar(1) is True

    def test_is_scalar_pandas(self):
        fake_pd = MagicMock()
        fake_pd.DataFrame = type("FakeDataFrame", (), {})
        fake_pd.Series = type("FakeSeries", (), {})

        # Mock global HAS_PANDAS to True
        with patch(f"{utils_mod}.compat.HAS_PANDAS", True):
            with patch(f"{utils_mod}.inspection.pd", fake_pd):
                df = fake_pd.DataFrame()
                assert inspection.is_scalar(df) is True
                assert inspection.is_scalar(object()) is False

    def test_is_scalar_numpy(self):
        fake_np = MagicMock()
        fake_np.ndarray = type("FaleNDArray", (), {})

        # Mock global HAS_NUMPY to True
        with patch(f"{utils_mod}.compat.HAS_NUMPY", True):
            with patch(f"{utils_mod}.compat.numpy", fake_np):
                arr = fake_np.ndarray()
                assert inspection.is_scalar(arr) is True

    def test_is_scalar_torch(self):
        fake_tm = MagicMock()
        fake_tm.Tensor = type("FakeTensor", (), {})

        # Mock global HAS_TORCH to True
        with patch(f"{utils_mod}.compat.HAS_TORCH", True):
            with patch(f"{utils_mod}.inspection.tm", fake_tm):
                tensor = fake_tm.Tensor()
                assert inspection.is_scalar(tensor) is True

    def test_is_scalar_xarray(self):
        fake_xr = MagicMock()
        fake_xr.DataArray = type("FakeDataArray", (), {})
        fake_xr.Dataset = type("FakeDataset", (), {})

        # Mock global HAS_XARRAY to True
        with patch(f"{utils_mod}.compat.HAS_XARRAY", True):
            with patch(f"{utils_mod}.inspection.xr", fake_xr):
                da = fake_xr.DataArray()
                assert inspection.is_scalar(da) is True

    def test_is_scalar_false(self):
        with patch(f"{utils_mod}.compat.HAS_PANDAS", False):
            with patch(f"{utils_mod}.compat.HAS_NUMPY", False):
                assert inspection.is_scalar(object()) is False


# ---------- Tests 3: Python Versions ----------


class TestPyVersionImport:
    def test_python_old_legacy_less_than_39(self):
        # Mock version to 3.8
        with patch.object(sys, "version_info", (3, 8)):
            importlib.reload(inspection)

        importlib.reload(inspection)
