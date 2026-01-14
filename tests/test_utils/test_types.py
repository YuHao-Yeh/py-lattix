import builtins
import decimal
import importlib
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.lattix.utils import _typing
from src.lattix.utils import types as types_module

REAL_PY_VERSION = sys.version_info
top_mod = "src.lattix"


# ---------- Fixtures ----------
@pytest.fixture(autouse=True)
def cleanup_module():
    yield
    importlib.reload(_typing)
    importlib.reload(types_module)


# ---------- Tests 1: Typing in Different Python Version ----------
class TestTypes:

    # def test_typing_extensions_import_success(self):
    #     if sys.version_info <= (3, 10):
    #         with patch.object(sys, "version_info", (3, 8)):
    #             with patch.dict(sys.modules, {"typing_extensions": None}):

    #                 importlib.reload(_typing)

    #                 assert hasattr(_typing, "TypeAlias")
    #                 assert hasattr(_typing, "TypeGuard")

    @pytest.mark.parametrize(
        "version",
        [
            (3, 8),
            pytest.param(
                (3, 9),
                marks=pytest.mark.skipif(
                    REAL_PY_VERSION < (3, 9), reason="Requires Py3.9+"
                ),
            ),
            pytest.param(
                (3, 11),
                marks=pytest.mark.skipif(
                    REAL_PY_VERSION < (3, 10), reason="Requires Py3.10+"
                ),
            ),
        ],
    )
    def test_version_branches(self, version):
        """Test different python versions."""
        with patch.object(sys, "version_info", version):
            importlib.reload(_typing)
            importlib.reload(types_module)

            assert hasattr(types_module, "AtomicTypes")
            assert hasattr(types_module, "ScalarTypes")
            assert hasattr(types_module, "Dict")

    def test_genericalias_fallback(self):
        real_import = builtins.__import__

        def mocked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "types" and fromlist and "GenericAlias" in fromlist:
                raise ImportError("Simulated GenericAlias absence")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=mocked_import):
            importlib.reload(types_module)
            assert types_module.GenericAlias is not None

    @pytest.mark.parametrize(
        "py_version",
        [
            pytest.param(
                (3, 11),
                marks=pytest.mark.skipif(
                    REAL_PY_VERSION < (3, 10), reason="Requires Py3.10+"
                ),
            ),
            pytest.param(
                (3, 8),
                marks=pytest.mark.skipif(
                    REAL_PY_VERSION < (3, 9), reason="Requires Py3.9+"
                ),
            ),
        ],
    )
    @pytest.mark.parametrize("has_pandas, has_numpy", [(True, True), (False, False)])
    def test_scalar_types_matrix(self, py_version, has_pandas, has_numpy):
        """
        Test the combinations of Pandas/Numpy availability.
        """
        fake_pd = SimpleNamespace(
            DataFrame=type("DF", (), {}), Series=type("SR", (), {})
        )
        fake_np = SimpleNamespace(ndarray=type("ND", (), {}))

        with patch.object(sys, "version_info", py_version):
            with patch(f"{top_mod}.utils.compat.HAS_PANDAS", has_pandas):
                with patch(f"{top_mod}.utils.compat.HAS_NUMPY", has_numpy):
                    with patch(f"{top_mod}.utils.compat.pandas", fake_pd):
                        with patch(f"{top_mod}.utils.compat.numpy", fake_np):

                            importlib.reload(_typing)
                            importlib.reload(types_module)

                            # Ensure ScalarTypes was created
                            assert types_module.ScalarTypes is not None

                            # If both false, ScalarTypes should just be AtomicTypes
                            if not has_pandas and not has_numpy:
                                assert (
                                    types_module.ScalarTypes == types_module.AtomicTypes
                                )
                            else:
                                assert hasattr(types_module.ScalarTypes, "__origin__")

    def test_registry_types_compatibility(self):
        """Test registry types."""
        if REAL_PY_VERSION < (3, 9):
            test_versions = [(3, 7), (3, 8)]
        elif REAL_PY_VERSION > (3, 10):
            test_versions = [(3, 7), (3, 8), (3, 9), (3, 10), (3, 11)]
        else:
            test_versions = [(3, 7), (3, 8), (3, 9)]

        for version in test_versions:
            with patch.object(sys, "version_info", version):
                importlib.reload(_typing)
                importlib.reload(types_module)
                assert types_module.StyleRegistry is not None
                assert types_module.ArgsRegistry is not None

    def test_runtime_constants_and_literals(self):
        """Test the standard static definitions."""

        importlib.reload(_typing)
        importlib.reload(types_module)

        # Check Literals
        assert types_module.JOIN_METHOD
        assert types_module.MERGE_METHOD
        assert types_module.TRAV_ORDER

        # Check Atomic base types
        assert isinstance(types_module._ATOMIC_BASE_TYPES, tuple)
        assert str in types_module._ATOMIC_BASE_TYPES
        assert int in types_module._ATOMIC_BASE_TYPES

        # Verify it contains the runtime classes (imported before 'del')
        assert str in types_module._ATOMIC_BASE_TYPES
        assert int in types_module._ATOMIC_BASE_TYPES
        assert uuid.UUID in types_module._ATOMIC_BASE_TYPES
        assert decimal.Decimal in types_module._ATOMIC_BASE_TYPES

        # Check Registries
        assert types_module.AdapterRegistry is not None
        assert hasattr(types_module.AdapterRegistry, "__args__") or hasattr(
            types_module.AdapterRegistry, "__origin__"
        )
        # assert isinstance(types_module.AdapterRegistry, dict) # or types_module.AdapterRegistry is dict

        # Check Exports
        assert "JOIN_METHOD" in types_module.__all__
        assert "_ATOMIC_BASE_TYPES" in types_module.__all__
