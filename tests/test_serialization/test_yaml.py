import datetime
import decimal
import importlib
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from src.lattix.serialization import yaml as safe_yaml
from src.lattix.utils import exceptions

top_mod = "src.lattix"


# ---------- Tests 1: YAML Serialization/Deserialization ----------


class TestYAMLSerialization:
    # --- 1. Basic RoundTrip ---

    def test_roundtrip_all_types(self):
        """Test that all registered types dump and load back correctly."""
        data = {
            "simple_tuple": (1, 2, 3),
            "simple_set": {10, 20},
            "simple_frozenset": frozenset([99, 100]),
            "simple_complex": 3 + 4j,
            "simple_decimal": decimal.Decimal("12.345"),
            "simple_datetime": datetime.datetime(2025, 10, 27, 12, 30, 45),
            "simple_path": Path("/tmp/example.txt"),
            "list": [1, 2],
            "dict": {"x": 1},
        }

        # Dump to string
        yaml_str = safe_yaml.dump(data)

        # Verify string contains expected tags
        assert "!tuple" in yaml_str
        assert "!set" in yaml_str
        assert "!frozenset" in yaml_str
        assert "!complex" in yaml_str
        assert "!decimal" in yaml_str
        assert "!datetime" in yaml_str
        assert "!path" in yaml_str

        # Load back
        loaded = safe_yaml.load(yaml_str)

        # Verify Types and Values
        assert loaded["simple_tuple"] == (1, 2, 3)
        assert isinstance(loaded["simple_set"], set) and loaded["simple_set"] == {
            10,
            20,
        }
        assert isinstance(loaded["simple_frozenset"], frozenset)
        assert loaded["simple_complex"] == 3 + 4j
        assert isinstance(loaded["simple_decimal"], decimal.Decimal)
        assert loaded["simple_decimal"] == decimal.Decimal("12.345")
        assert isinstance(loaded["simple_datetime"], datetime.datetime)
        assert loaded["simple_path"] == Path("/tmp/example.txt")

    # --- 2. Load ---

    def test_load_bytes(self):
        """Test loading from bytes object."""
        yaml_bytes = b"key: !tuple [1, 2]"
        data = safe_yaml.load(yaml_bytes)
        assert data["key"] == (1, 2)

    # --- 3. Dump ---

    def test_dump_stream_and_kwargs(self):
        """Test dumping to a file-like stream and ignoring 'Dumper' kwarg."""
        data = {"a": 1}
        stream = io.StringIO()

        # Call with Dumper arg (should be ignored/popped) and indent arg
        result = safe_yaml.dump(data, stream=stream, Dumper="Ignored", indent=4)

        # Result should be None when stream is provided
        assert result is None

        # Stream should contain content
        output = stream.getvalue()
        assert "a: 1" in output
        assert output.endswith("\n")

    def test_dump_defaults(self):
        """Test dump without stream returns string."""
        data = {"b": 2}
        result = safe_yaml.dump(data)
        assert isinstance(result, str)
        assert "b: 2" in result

    def test_hybrid_representers(self):
        """
        Test the custom logic for dict/list that switches between
        flow style (inline) and block style based on nesting.
        """
        data = {
            "nested_flat": [1, 2, 3],  # Should be flow: [1, 2, 3]
            "nested_deep": [{"a": 1}],  # Should be block list, but inner dict is flow
            "nested_map_flat": {"x": 1},  # Should be flow: {x: 1}
            "nested_map_deep": {"x": [1]},  # Should be block: x: [1]
            "nested_long": list(range(11)),  # Should be block
            "map_flat": {  # Should be flow
                "a": 1,
                "b": 2,
                "c": 3,
                "d": 4,
                "e": 5,
                "f": 6,
                "g": 7,
                "h": 8,
                "i": 9,
                "j": 10,
                "k": 11,
            },
            "map_deep": {  # Should be block
                "a": {
                    "b": {
                        "c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": 1}}}}}}}}
                    }
                }
            },
        }

        yaml_str = safe_yaml.dump(data)

        # Check for Flow style indicators in the specific lines
        assert "[1, 2, 3]" in yaml_str
        assert "{x: 1}" in yaml_str

        # Check that block style is used for the list,
        # but the inner item {"a": 1} is a flow style bacause it is simple.
        assert "- {a: 1}" in yaml_str

    # --- 4. Register Representer/Constructor ---

    def test_register_custom_type(self):
        """Test the public register_type API."""

        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y

            def __eq__(self, other):
                return self.x == other.x and self.y == other.y

        def represent_point(dumper, data):
            return dumper.represent_scalar("!point", f"{data.x},{data.y}")

        def construct_point(loader, node):
            value = loader.construct_scalar(node)
            x, y = map(int, value.split(","))
            return Point(x, y)

        # Register
        safe_yaml.register_type("!point", Point, represent_point, construct_point)

        # Roundtrip
        data = {"p": Point(10, 20)}
        yaml_str = safe_yaml.dump(data)
        assert "!point '10,20'" in yaml_str

        loaded = safe_yaml.load(yaml_str)
        assert loaded["p"] == Point(10, 20)

    def test_register_path_subclass(self):
        """Test code path for issubclass(typ, Path) in register_type."""

        class MyPath(type(Path())):  # Create a dynamic subclass of the system's Path
            pass

        # We just want to ensure register_type calls add_multi_representer
        # We can mock EnhancedSafeDumper to verify the call, or just run it.
        with patch.object(
            safe_yaml.EnhancedSafeDumper, "add_multi_representer"
        ) as mock_multi:
            safe_yaml.register_type(
                "!mypath", MyPath, lambda d, x: None, lambda _, n: None
            )
            mock_multi.assert_called_once()

    def test_register_type_typeerror_fallback(self):
        """
        Test that if 'typ' is not a class (causing issubclass to raise TypeError),
        the code falls back to add_representer.
        """

        # 1. Dummy functions
        def dummy_rep(dumper, data):
            return None

        def dummy_cons(loader, node):
            return None

        # 2. Use an instance (e.g., an integer 123) instead of a class (int).
        #    issubclass(123, Path) raises TypeError.
        not_a_class = 123

        # 3. Patch the Dumper methods to verify which one gets called
        with patch.object(
            safe_yaml.EnhancedSafeDumper, "add_representer"
        ) as mock_add_rep:
            with patch.object(
                safe_yaml.EnhancedSafeDumper, "add_multi_representer"
            ) as mock_multi_rep:
                with patch.object(
                    safe_yaml.EnhancedSafeLoader, "add_constructor"
                ) as mock_add_cons:

                    safe_yaml.register_type(
                        "!dummy", not_a_class, dummy_rep, dummy_cons
                    )

                    # 4. Assertions

                    # issubclass() crashed, didn't reach reach add_multi_representer
                    mock_multi_rep.assert_not_called()

                    # Except TypeError block was entered and executed
                    mock_add_rep.assert_called_once_with(not_a_class, dummy_rep)

                    # Loader registration was executed
                    mock_add_cons.assert_called_once()

    # --- 5. Inspect Registry ---

    def test_inspect_registry(self, capsys):
        """Test inspect_registry prints output."""
        # Case 1: verbose=True
        res = safe_yaml.inspect_registry(verbose=True)
        assert isinstance(res, dict)
        assert "Representer keys" in res

        captured = capsys.readouterr()
        assert "Representer keys" in captured.out

        # Case 2: verbose=False
        res = safe_yaml.inspect_registry(verbose=False)
        assert isinstance(res, dict)
        assert "Multi-Representer keys" in res

        captured = capsys.readouterr()
        assert captured.out == ""

    # --- 6. EnhancedSafeDumper/Loader Modify ---

    def test_increase_indent(self):
        """Directly test the EnhancedSafeDumper increase_indent method."""
        dumper = safe_yaml.EnhancedSafeDumper(io.StringIO())
        # Just ensure it runs without error and returns expectation
        dumper.increase_indent(flow=True, indentless=True)

        def raise_attr_error(*args, **kwargs):
            raise AttributeError("no such method")

        with patch.object(safe_yaml.SafeDumper, "increase_indent", raise_attr_error):
            assert dumper.increase_indent() is None

    def test_ensure_enhanced_registered_exit(self):
        safe_yaml._ensure_enhanced_registered(force=True)
        assert getattr(safe_yaml.EnhancedSafeLoader, "_enhanced_registered", False)

        safe_yaml._ensure_enhanced_registered(force=False)
        assert getattr(safe_yaml.EnhancedSafeLoader, "_enhanced_registered", False)

    # --- 7. PyYAML Missing ---

    def test_missing_pyyaml_environment(self):
        """
        Simulate an environment where PyYAML is not installed.
        """

        # 1. Patch HAS_YAML in the compat module to be False
        with patch(f"{top_mod}.utils.compat.HAS_YAML", False):

            # 2. Reload safe_yaml
            importlib.reload(safe_yaml)

            # --- Assertion Phase ---

            # Verify public functions raise Error
            with pytest.raises(exceptions.OptionalImportError):
                safe_yaml.load("a: 1")

            with pytest.raises(exceptions.OptionalImportError):
                safe_yaml.dump({"a": 1})

            # Verify register_type does nothing safely
            safe_yaml.register_type("!foo", int, lambda x, y: x, lambda x, y: x)

            # Verify inspect_registry returns empty
            assert safe_yaml.inspect_registry()["Constructor keys"] == []
            assert safe_yaml.inspect_registry()["Multi-Representer keys"] == []
            assert safe_yaml.inspect_registry()["Representer keys"] == []

            # Verify Dummy Classes exist and methods don't crash
            assert issubclass(safe_yaml.ScalarNode, safe_yaml.Node)

            # Test Dummy Loader methods
            loader = safe_yaml.EnhancedSafeLoader()
            assert loader.construct_scalar(None) == ""
            assert loader.construct_sequence(None) == []
            assert loader.construct_mapping(None) == {}
            loader.add_constructor("!tag", None)  # Should pass

            # Test Dummy Dumper methods
            dumper = safe_yaml.EnhancedSafeDumper()
            assert isinstance(dumper.represent_scalar(None, None), safe_yaml.ScalarNode)
            assert isinstance(
                dumper.represent_sequence(None, None), safe_yaml.SequenceNode
            )
            assert isinstance(dumper.represent_mapping(None, None), safe_yaml.Node)
            dumper.add_representer(int, None)  # Should pass
            dumper.add_multi_representer(int, None)  # Should pass

        # 3. Cleanup: Reload with True
        importlib.reload(safe_yaml)
