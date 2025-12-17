import sys
import decimal
import importlib
import pytest
import typing_extensions    # <--- Forces load with REAL sys.version_info
from unittest.mock import patch
import uuid

import src.lattix.utils.types as types_module

top_mod = "src.lattix"

# ---------- Fixtures ----------
@pytest.fixture(autouse=True)
def cleanup_module():
    yield
    importlib.reload(types_module)


# ---------- Tests 1: Typing in Different Python Version ----------
class TestTypes:
    def test_python_old_legacy_less_than_39(self):
        """
        Simulate Python 3.8
        """
        # Mock version to 3.8
        with patch.object(sys, "version_info", (3, 8)):
            importlib.reload(types_module)

            # 1. Verify < 3.9 logic (ListType should be typing.List, not list)
            from typing import List, Dict, Set, Tuple, Type
            assert types_module.ListType is List
            assert types_module.DictType is Dict
            assert types_module.SetType is Set
            assert types_module.TupleType is Tuple
            assert types_module.TypeType is Type
            
            # 2. Verify GenericAlias fallback
            assert types_module.GenericAlias == type(List[int])

            # 3. Verify ModuleRegistry legacy definition logic
            assert hasattr(types_module, "ModuleRegistry")

    def test_python_intermediate_39(self):
        """
        Simulate Python 3.9. 
        """
        with patch.object(sys, "version_info", (3, 9)):
            importlib.reload(types_module)

            # 1. Verify >= 3.9 logic
            assert types_module.ListType is list
            assert types_module.DictType is dict
            
            # 2. Verify < 3.10 (use typing_extensions)
            assert hasattr(types_module, "BuiltinAtoms")
            
            # 3. Verify ModuleRegistry legacy definition logic
            assert hasattr(types_module, "ModuleRegistry")

    def test_python_modern_310_plus(self):
        """
        Simulate Python 3.10+.
        """
        with patch.object(sys, "version_info", (3, 11)):
            importlib.reload(types_module)
            # 1. Verify >= 3.9
            assert types_module.ListType is list
            # 2. Verify >= 3.10 logic (Native TypeAlias)
            assert hasattr(types_module, "TypeAlias")
            
            # 3. Verify ModuleRegistry modern definition
            assert hasattr(types_module, "ModuleRegistry")

    @pytest.mark.parametrize("py_version", [(3, 9), (3, 11)])
    @pytest.mark.parametrize("has_pandas, has_numpy", [
        (True, True),
        (True, False),
        (False, True),
        (False, False)
    ])
    def test_scalar_types_matrix(self, py_version, has_pandas, has_numpy):
        """
        Test the combinations of Pandas/Numpy availability.
        """
        
        with patch.object(sys, "version_info", py_version), \
            patch(f"{top_mod}.utils.compat.HAS_PANDAS", has_pandas), \
            patch(f"{top_mod}.utils.compat.HAS_NUMPY", has_numpy):
            
            importlib.reload(types_module)
            
            # Ensure ScalarTypes was created
            assert types_module.ScalarTypes is not None
            
            # If both false, ScalarTypes should just be AtomicTypes
            if not has_pandas and not has_numpy:
                assert types_module.ScalarTypes == types_module.AtomicTypes
            
    def test_runtime_constants_and_literals(self):
        """
        Test the standard static definitions.
        """

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
        assert hasattr(types_module.AdapterRegistry, "__args__") or hasattr(types_module.AdapterRegistry, "__origin__")
        # assert isinstance(types_module.AdapterRegistry, dict) # or types_module.AdapterRegistry is dict
        
        # Check Exports
        assert "JOIN_METHOD" in types_module.__all__
        assert "_ATOMIC_BASE_TYPES" in types_module.__all__
