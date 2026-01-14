import _thread
import os
import pickle
import tempfile
from unittest.mock import patch

import pytest

from src.lattix.structures import Lattix
from src.lattix.utils import exceptions

top_mod = "src.lattix"

# ---------- Tests 1: Initialization & Construction ----------


class TestInit:
    def test_init_empty(self):
        d = Lattix()
        assert len(d) == 0
        assert d.sep == "/"
        assert not d.lazy_create
        assert not d.locking_enabled

    def test_init_from_dict(self):
        data = {"a": 1, "b": {"c": 2}}
        d = Lattix(data)

        assert d["a"] == 1
        assert isinstance(d["b"], Lattix)
        assert d["b"]["c"] == 2

    def test_init_from_mapping(self):
        class Custom(dict):
            pass

        data = {"a": 1, "b": Custom({"c": 2})}
        d = Lattix(data)

        assert d["a"] == 1
        assert isinstance(d["b"], Lattix)
        assert d["b"]["c"] == 2

    def test_init_from_iterable_pairs(self):
        d = Lattix([("a", 1), ("b", 2)])
        assert d["a"] == 1
        assert d["b"] == 2

        d = Lattix([["x", 10], ["y", 20], ["z", 30]])
        assert d["x"] == 10
        assert d["y"] == 20

        d = Lattix((("x", 1), ("y", 2)))
        assert d["x"] == 1
        assert d["y"] == 2

        d = Lattix([("x", (1, 2)), ("y", 2)])
        assert d["x"] == (1, 2)
        assert d["y"] == 2

    def test_init_kwargs(self):
        d = Lattix(a="foo", b="bar")
        assert d["a"] == "foo"
        assert d["b"] == "bar"

    def test_init_config(self):
        d = Lattix(sep=".", lazy_create=True, enable_lock=True)
        assert d.sep == "."
        assert d.lazy_create is True
        assert d.locking_enabled is True

    def test_custom_separator(self):
        d = Lattix({"a": {"b": 1}}, sep=".")
        assert d.sep == "."
        assert d["a.b"] == 1
        assert d["a"].sep == "."

    def test_init_thread_lock(self):
        d = Lattix(enable_lock=True)
        assert d._lock is not None
        assert isinstance(d._lock, _thread.RLock)

    def test_init_invalid(self):
        with pytest.raises(exceptions.ArgTypeError):
            _ = Lattix([("a", 1, 2), ("b", 3)])

        with pytest.raises(exceptions.ArgTypeError):
            _ = Lattix(123)

        with pytest.raises(exceptions.ArgTypeError):
            _ = Lattix(enable_lock=5)

    # --- Constructort ---

    def test_fromkeys(self):
        keys = ["a", "b", "c"]
        d = Lattix.fromkeys(keys, 0)
        assert d["a"] == 0
        assert d["b"] == 0

    def test_from_dict(self):
        data = {"a": 1, "b": 2}
        d = Lattix.from_dict(data)
        assert d["a"] == 1
        assert d["b"] == 2

    def test_from_env_basic(self):
        # Test with standard prefix and double-underscore
        with patch.dict(
            os.environ,
            {
                "APP__DATABASE__HOST": "127.0.0.1",
                "APP__DATABASE__PORT": "5432",
                "APP__DEBUG": "true",
                "OTHER_VAR": "ignore_me",
            },
        ):
            conf = Lattix.from_env(prefix="APP", sep="__")

            assert conf.database.host == "127.0.0.1"
            assert conf.database.port == "5432"
            assert conf.debug == "true"
            assert "other_var" not in conf

        # Test with custom settings
        with patch.dict(
            os.environ, {"MYAPP_LOG_LEVEL": "DEBUG", "MYAPP_SERVER_IP": "0.0.0.0"}
        ):
            conf = Lattix.from_env(prefix="MYAPP", sep="_", lowercase=False)

            # Prefix is removed, but rest remains uppercase
            assert conf.LOG.LEVEL == "DEBUG"
            assert conf.SERVER.IP == "0.0.0.0"

        # Test with no prefix
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
            conf = Lattix.from_env(prefix="")
            assert conf.database_url == "sqlite:///:memory:"

    def test_unflatten(self):
        data = {"a": 1, "b.c": 2, "b.d": 3}
        d = Lattix.unflatten(data, sep=".")
        assert d.to_dict() == {"a": 1, "b": {"c": 2, "d": 3}}
        assert d == Lattix({"a": 1, "b": {"c": 2, "d": 3}})


# ---------- Tests 2: Get / Set / Del Item ----------


class TestBasicMapping:
    # --- 1. getitem ---

    def test_getitem_path(self):
        d = Lattix({"a": {"b": {"c": 100}}})
        assert d["a/b/c"] == 100
        assert isinstance(d["a/b"], Lattix)

        path = ("a", "b", "c")
        assert d[path] == 100
        assert isinstance(d[["a", "b"]], Lattix)

    def test_getitem_missing(self):
        d = Lattix()
        with pytest.raises(exceptions.KeyNotFoundError):
            _ = d["missing"]
        with pytest.raises(exceptions.PathNotFoundError):
            _ = d["a/b/c"]

    def test_getitem_setitem_simple(self):
        d = Lattix()
        d["a"] = 10
        assert d["a"] == 10
        d["a"] = 20
        assert d["a"] == 20

    def test_getitem_promote(self):
        d = Lattix()
        d._children["a"] = {"b": 10}
        assert isinstance(d["a"], Lattix)

    # --- 2. setitem ---

    def test_setitem_path_creation(self):
        d = Lattix()

        with pytest.raises(exceptions.PathNotFoundError):
            d["a/b/c"] = 1

    def test_setitem_clone_with_different_parent(self):
        root1 = Lattix()
        child = Lattix(key="child")

        root1["new_child"] = child
        assert root1["new_child"] is child
        assert root1["new_child"].parent is root1

        root2 = Lattix()
        root2["new_child"] = child
        assert root2["new_child"] is not child
        assert root2["new_child"].parent is root2
        assert root1["new_child"] is child
        assert root1["new_child"].parent is root1

        child2 = Lattix(key="child2")
        root1["new_child"] = child2
        assert root1["new_child"] is child2
        assert child.parent is None

    def test_setitem_edge_case(self):
        d = Lattix()
        d["list"] = [1, "str", object()]
        assert isinstance(d["list"], list)
        assert isinstance(d["list"][2], object)

    # --- 3. delitem ---

    def test_delitem(self):
        d = Lattix({"a": 1})
        del d["a"]
        assert "a" not in d

        with pytest.raises(exceptions.KeyNotFoundError):
            del d["a"]

        with pytest.raises(exceptions.KeyNotFoundError):
            del d["a/non_existent"]


# ---------- Tests 3: Hierarchical / Path Access ----------


class TestHierarchical:
    def test_path_access_get(self):
        d = Lattix({"a": {"b": {"c": 10}}}, lazy_create=True)
        assert d["a/b/c"] == 10
        assert isinstance(d["a/b"], Lattix)

        d2 = Lattix({"x": {"y": 1}}, lazy_create=False)
        object.__getattribute__(d2, "_children")["z"] = {"k": 1}
        assert isinstance(d2.z, Lattix)
        assert isinstance(d2["z"], Lattix)

    def test_path_access_set(self):
        d = Lattix(lazy_create=True)
        d["a/b/c"] = 100
        assert d["a"]["b"]["c"] == 100

        d["a/b"] = 99
        assert d["a"]["b"] == 99
        assert not isinstance(d["a"]["b"], Lattix)

    def test_path_not_found(self):
        d = Lattix({"a": 1})
        with pytest.raises(exceptions.UnexpectedNodeError):
            _ = d["a/b"]

        with pytest.raises(exceptions.PathNotFoundError):
            _ = d["z/x"]

    def test_lazy_create_path(self):
        d = Lattix(lazy_create=True)
        assert isinstance(d["a/b"], Lattix)
        assert "a" in d

    def test_path_promotion_and_edge_cases(self):
        d = Lattix()
        d["raw_dict"] = {"a": 1}
        assert isinstance(d["raw_dict"], Lattix)

        root1 = Lattix(key="root1")
        root2 = Lattix(key="root2")
        child = Lattix({"val": 1}, key="child", parent=root1)
        root1._children["child"] = child

        root2["new_child"] = child
        assert root2["new_child"] is not child  # Should be a clone
        assert root2["new_child"].parent is root2

        d["scalar"] = 1
        with pytest.raises(exceptions.UnexpectedNodeError):
            _ = d["scalar/too_deep"]

    def test_convert_iterable_deep(self):
        d = Lattix()
        # Nested iterables with mappings inside
        data = [1, {"a": 2}, [3, {"b": 4}]]
        d["list"] = data
        assert isinstance(d["list"][1], Lattix)
        assert isinstance(d["list"][2][1], Lattix)


# ---------- Tests 4: Attribute Access ----------


class TestDotAccess:
    # --- 1. GET/SET attr ---

    def test_dot_access_get_set(self):
        d = Lattix(lazy_create=True)
        d.foo = "bar"
        assert d["foo"] == "bar"
        assert d.foo == "bar"

        d.nested = {"x": 1}
        assert d.nested.x == 1

    def test_dot_access_missing(self):
        d = Lattix(lazy_create=False)
        with pytest.raises(exceptions.AttributeNotFoundError):
            _ = d.non_existent
        with pytest.raises(exceptions.AttributeNotFoundError):
            d.non_existent = False

    def test_dot_access_lazy(self):
        d = Lattix(lazy_create=True)
        assert isinstance(d.missing, Lattix)
        assert "missing" in d

    def test_attr_name_validation(self):
        d = Lattix()
        with pytest.raises(exceptions.InvalidAttributeNameError):
            d.__setattr__("invalid-name!", 1)

    def test_internal_attr_protection(self):
        d = Lattix(key="d")

        with pytest.raises(exceptions.AttributeAccessDeniedError):
            d._lazy_create = False

        d._frozen = True
        with pytest.raises(exceptions.ModificationDeniedError):
            d.lazy_create = True

    # --- 2. DEL attr ---

    def test_delattr(self):
        d = Lattix(a=1)
        del d.a
        assert "a" not in d

        del d._sep
        with pytest.raises(AttributeError):
            _ = d.sep

        with pytest.raises(exceptions.InvalidAttributeNameError):
            del d.__doc__

    def test_delattr_class_attribute_error(self):
        class Protected(Lattix):
            @property
            def cant_touch_this(self):
                return True

        p = Protected()
        with pytest.raises(AttributeError):
            del p.cant_touch_this

    def test_delattr_advanced(self):
        class SubLattix(Lattix):
            class_attr = 10

        s = SubLattix(lazy_create=True)
        s.a = 1
        del s.a
        assert "a" not in s

        with pytest.raises(AttributeError):
            del s.class_attr

        del SubLattix.class_attr
        assert "class_attr" not in SubLattix._get_class_attrs()
        assert not hasattr(SubLattix, "class_attr")

        assert "class_attr" not in s._children

        s.class_attr = "shadow"
        assert "class_attr" in s
        assert "class_attr" in s._children
        assert s.class_attr == "shadow"
        del s.class_attr

    # --- 3. dir ---

    def test_dir(self):
        d = Lattix({"a": 1})
        assert "a" in dir(d)


# ---------- Tests 5: Lazy Creation ----------


class TestLazyCreate:
    def test_lazy_create_getattr(self):
        d = Lattix(lazy_create=True)

        d.a.b.c = 10
        assert d["a"]["b"]["c"] == 10
        assert isinstance(d.a, Lattix)

    def test_lazy_create_path_set(self):
        d = Lattix(lazy_create=True)
        d["x/y/z"] = 99
        assert d.x.y.z == 99


# ---------- Tests 6: Mutation & Update ----------


class TestBasicMappingInterface:
    # --- 1. contains ---

    def test_contains(self):
        d = Lattix({"a": 1})
        assert "a" in d
        assert "b" not in d

        assert "a/b" not in d

    # --- 2. reversed ---

    def test_reversed(self):
        d = Lattix({"a": 1, "b": 2, "c": {"d": 3}})
        rev = list(reversed(d))
        assert rev == ["c", "b", "a"]

    # --- 3. equal ---

    def test_eq(self):
        data = {"a": 1, "b": 2, "c": {"d": 3}}
        d = Lattix(data)
        assert d == data
        assert data == d
        assert d.__eq__("other") is NotImplemented

    # --- 4. iter ---

    def test_iter_len(self):
        d = Lattix({"a": 1, "b": 2})
        assert len(d) == 2
        assert set(iter(d)) == {"a", "b"}

    # --- 5. keys / values / items ---

    def test_keys_values_items(self):
        d = Lattix(a=1)
        assert list(d.keys()) == ["a"]
        assert list(d.values()) == [1]
        assert list(d.items()) == [("a", 1)]

    # --- 6. clear ---

    def test_clear(self):
        d = Lattix({"a": 1})
        d.clear()
        assert len(d) == 0

    # --- 7. get ---

    def test_get(self):
        d = Lattix({"a": 1, "b": {"c": 2}}, lazy_create=False)
        d[123] = "value"
        complex_key = ("x", 10)
        d[complex_key] = "data"

        assert d.get("a") == 1
        assert d.get("null", "missing") == "missing"
        assert d.get("x") is None
        assert d.get(123) == "value"
        assert d.get(complex_key) == "data"
        assert d.get("b/c") == 2
        assert d.get("b/C", 99) == 99

        d._children = {"c": 3}
        assert d.get("c") == 3

    # --- 8. pop ---

    def test_pop(self):
        d = Lattix({"a": 1})
        val = d.pop("a")
        assert val == 1
        assert "a" not in d

        assert d.pop("z", 99) == 99
        with pytest.raises(exceptions.KeyNotFoundError):
            d.pop("z")

    # --- 9. popitem ---

    def test_popitem(self):
        d = Lattix({"a": 1})
        item = d.popitem()
        assert item == ("a", 1)
        assert len(d) == 0
        with pytest.raises(KeyError):
            d.popitem()

    # --- 10. setdefault ---

    def test_setdefault(self):
        d = Lattix()
        val = d.setdefault("a", 100)
        assert val == 100
        assert d["a"] == 100

        val2 = d.setdefault("a", 200)
        assert val2 == 100  # Should no change

    # --- 11. update ---
    def test_update(self):
        d = Lattix({"a": 1}, key="d")
        # dict
        d.update({"b": 2, "a": 3})
        assert d["b"] == 2
        assert d.a == 3

        # Lattix
        d.update(Lattix({"g": 7, "h": 8}, key="test_update"))

        # iterable pairs
        d.update([("c", 3)])
        assert d["c"] == 3

        d.update([{"d": 4}, {"e": 5}])
        assert d["d"] == 4
        assert d["e"] == 5

        f = Lattix(key="f", parent=d)
        d.update([("e2", f)])

        # kwargs
        d.update(g=6)
        assert d["g"] == 6

        # Error cases
        with pytest.raises(exceptions.ArgTypeError):
            d.update(["not_a_pair"])

        with pytest.raises(exceptions.ArgTypeError):
            d.update(123)

        with pytest.raises(exceptions.ModificationDeniedError):
            d.freeze()
            d.update(a=2)


# ---------- Tests 7: Formatting % Representation ----------


class TestRepr:
    def test_repr_str(self):
        d = Lattix(a=1)
        assert "Lattix" in repr(d)
        assert "a" in str(d)

    def test_format_spec(self):
        d = Lattix(a=1)
        assert "Lattix" in format(d, "pretty")
        assert "{" in format(d, "json")
        assert "a" in format(d, "repr")

        with pytest.raises(ValueError):
            format(d, "invalid_fmt")

    def test_pretty_print_styles(self):
        d = Lattix(a=1, b=[1, 2])
        # Just ensure no crash
        d.pprint(style="default")
        d.pprint(style="json")
        d.pprint(style="repr")

    def test_formatting_and_pretty(self):
        d = Lattix(a=1)
        assert "{" in f"{d:json}"
        assert "a: 1" in f"{d:yaml}"
        assert "Lattix" in f"{d:repr}"
        assert "Lattix" in f"{d:debug}"

    def test_pretty(self):
        d = Lattix({"a": 1, "b": {"c": 2}})

        class FakePrinter:
            def __init__(self):
                self.output = ""

            def text(self, val):
                self.output += val

        # 1. Normal pretty printing
        printer = FakePrinter()
        d._repr_pretty_(printer, cycle=False)
        assert "'a': 1" in printer.output
        assert "<Circular" not in printer.output

        # 2. Cycle detection in pretty print
        printer = FakePrinter()
        d["self"] = d
        d._repr_pretty_(printer, cycle=True)
        assert printer.output.startswith("<Circular Lattix at")
        assert "0x" in printer.output

        # 3. Exceptions
        printer = FakePrinter()
        with patch.object(Lattix, "pprint", side_effect=RuntimeError("Test Error")):
            d._repr_pretty_(printer, cycle=False)

        assert "<Lattix formatting error: Test Error>" in printer.output

    def test_pretty_alias_coverage(self):
        d = Lattix()
        assert d.__pretty__ == d._repr_pretty_


# ---------- Tests 8: Logical Operators ----------


class TestLogicalOP:
    # --- 1. and ---

    def test_intersection_and(self):
        # Lattix & Lattix
        d1 = Lattix(a=1, b=2, c={"x": 1})
        d2 = Lattix(b=20, c={"y": 2}, d=4)

        res = d1 & d2
        assert "a" not in res
        assert "d" not in res
        assert res.b == 20
        assert "x" not in res.c
        assert res.c == {}

        # Lattix & Mapping
        test_data = {"a": {"b": {"c": 100}}}
        res2 = d1 & test_data
        assert "a" in res2
        assert "b" not in res2
        assert "a/b" in res2

        # Handle Error
        with pytest.raises(TypeError):
            _ = d1 & object()

        with pytest.raises(exceptions.OperandTypeError):
            d1 &= object()

    # --- 2. or ---

    def test_union_or(self):
        # Lattix | Lattix
        d1 = Lattix(a=1)
        d2 = Lattix(b=2)
        res = d1 | d2
        assert res.a == 1 and res.b == 2

    # --- 3. sub ---

    def test_sub_diff(self):
        d1 = Lattix(a=1, b=2, c={"x": 1}, d=4)
        d2 = Lattix(b=2, c={"x": 2}, e=5)

        res = d1 - d2
        assert "a" in res
        assert "b" not in res
        assert "c" not in res
        assert "d" in res
        assert "e" not in res

        res = d1 - Lattix({"a": 1, "b": 2, "c": {"x": 1}})
        assert "a" not in res

    # --- 4. xor ---

    def test_xor_sym_diff(self):
        d1 = Lattix(a=1, b=2)
        d2 = Lattix(b=3, c=4)
        res = d1 ^ d2
        assert res.a == 1
        assert "b" not in res
        assert res.c == 4

    # --- 5. set operation ---

    def test_logical_mixins_types(self):
        d = Lattix(a=1)
        with pytest.raises(exceptions.OperandTypeError):
            d &= 1  # Invalid type

    def test_set_operation_invalid_op(self):
        d = Lattix()
        with pytest.raises(exceptions.UnsupportedOperatorError):
            d._set_operation({}, op="INVALID")

    def test_set_operation_edge_cases(self):
        # 1. Intersection (AND/OR) overwrite with Lattix
        v2_lattix = Lattix({"inner": 100})
        d1 = Lattix({"collision_key": 1})
        d2 = Lattix({"collision_key": v2_lattix})

        res = d1 | d2
        assert "collision_key" in res
        assert isinstance(res["collision_key"], Lattix)
        assert res["collision_key"] == v2_lattix
        assert res["collision_key"] is not v2_lattix

        res = d1 & d2
        assert res["collision_key"] == v2_lattix
        assert res["collision_key"] is not v2_lattix

        # 2.In other (OR/XOR) with Lattix
        new_node = Lattix({"val": 99})
        d1 = Lattix({"existing": 0})
        d2 = Lattix({"new_node": new_node})

        res_or = d1 | d2
        assert "new_node" in res_or
        assert res_or["new_node"] == new_node
        assert res_or["new_node"] is not new_node

        res_xor = d1 ^ d2
        assert "new_node" in res_xor
        assert res_xor["new_node"] == new_node
        assert res_xor["new_node"] is not new_node

    # --- 6. combination ---
    @pytest.mark.parametrize("op", ["&", "|", "-", "^"])
    def test_set_ops_pruning(self, op):
        d1 = Lattix({"a": {"b": 1, "c": 2}})
        d2 = Lattix({"a": {"b": 1}})

        if op == "-":
            res = d1 - d2
            assert "b" not in res.a
            assert res.a.c == 2
        elif op == "^":
            res = d1 ^ d2
            assert "b" not in res.a
            assert res.a.c == 2
        elif op == "&":
            res = d1 & d2
            assert "c" not in res.a
            assert res.a.b == 1


# ---------- Tests 9: Merge and Join ----------


class TestMergeJoin:
    # --- 1. addition ---

    def test_add_operator(self):
        d1 = Lattix(a=1)
        d2 = {"b": 2}
        d3 = d1 + d2
        assert d3.a == 1 and d3.b == 2
        assert d1.get("b") is None

    def test_iadd_operator(self):
        d1 = Lattix(a=1)
        d1 += {"b": 2}
        assert d1.a == 1 and d1.b == 2

    # --- 2. merge ---

    def test_merge_deep(self):
        d1 = Lattix({"x": {"a": 1}})

        d2 = {"x": {"b": 2}, "y": 3}
        d1.merge(d2)
        assert d1.x.a == 1
        assert d1.x.b == 2
        assert d1.y == 3

        d3 = {"y": {"z": 4}}
        d1.merge(d3, overwrite=False)
        assert d1.y == 3

        d1.merge(d3)
        assert d1.y.z == 4

        d4 = Lattix(Lattix({"z": {"c": 3}}))
        d1.merge(d4)

    # --- 3. join ---

    def test_join_inner(self):
        d1 = Lattix({"id1": "alice", "id2": "bob"})
        d2 = Lattix({"id1": 25, "id3": 30})

        res = d1.join(d2, how="inner", merge="tuple")
        assert "id1" in res
        assert res["id1"] == ("alice", 25)
        assert "id2" not in res

    def test_join_left(self):
        d1 = Lattix(a=1)
        d2 = Lattix(b=2)
        res = d1.join(d2, how="left")
        assert "a" in res
        assert "b" not in res

    def test_join_right(self):
        d1 = Lattix(a=1)
        d2 = Lattix(b=2)
        res = d1.join(d2, how="right")
        assert "b" in res
        assert "a" not in res

    def test_join_outer_merge_strategies(self):
        d1 = Lattix({"a": 1})
        d2 = Lattix({"a": 2, "b": 3})

        # prefer_self
        res = d1.join(d2, how="outer", merge="prefer_self")
        assert res["a"] == 1
        assert res["b"] == 3

        # prefer_other
        res = d1.join(d2, how="outer", merge="prefer_other")
        assert res.a == 2
        assert res.b == 3

    def test_join_invalid_args(self):
        d = Lattix()
        with pytest.raises(exceptions.OperandTypeError):
            d.join(object())
        with pytest.raises(ValueError):
            d.join({}, how="invalid")
        with pytest.raises(ValueError):
            d.join({}, merge="invalid")

    @pytest.mark.parametrize(
        "strategy, expected",
        [
            ("tuple", (1, 2)),
            ("self", 1),
            ("other", 2),
            ("prefer_self", 1),
            ("prefer_other", 2),
        ],
    )
    def test_join_all_strategies(self, strategy, expected):
        d1 = Lattix(a=1)
        d2 = Lattix(a=2)
        res = d1.join(d2, how="inner", merge=strategy)
        assert res["a"] == expected

    def test_join_with_none(self):
        d1 = Lattix(a=1)
        d2 = Lattix(a=None)
        res = d1.join(d2, how="inner", merge="prefer_self")
        assert res["a"] == 1

    def test_join_nested(self):
        d1 = Lattix(a={"b": 1})
        d2 = Lattix(a={"c": 2})

        res = d1.join(d2, "outer", "prefer_self")
        assert res["a"]["b"] == 1
        assert res["a"]["c"] == 2


# ---------- Tests 10: Serialization (JSON / YAML / Pickle) ----------


class TestSerialization:
    # --- 1. dict ---

    def test_to_dict(self):
        d = Lattix({"a": {"b": 1}})
        plain = d.to_dict()
        assert type(plain) is dict
        assert type(plain["a"]) is dict
        assert plain["a"]["b"] == 1

    # --- 2. list ---

    def test_to_list(self):
        d = Lattix({"a": {"b": 1}})
        plain = d.to_list()
        assert type(plain) is list
        assert type(plain[0]) is list
        assert plain[0][0] == "a"
        assert plain[0][1] == ["b", 1]

    # --- 3. tuple ---

    def test_to_tuple(self):
        d = Lattix({"a": {"b": 1}})
        plain = d.to_tuple()
        assert isinstance(plain, tuple)
        assert isinstance(plain[0], tuple)
        assert plain[0][0] == "a"
        assert plain[0][1] == ("b", 1)

    # --- 4. flatten ---

    def test_flatten(self):
        data = {"a": 1, "b": {"c": 2}, "d": {}}
        d = Lattix(data)
        res = d.flatten(sep="/")
        assert res["a"] == 1
        assert res["b/c"] == 2
        assert res["d"] == {}

    # --- 5. JSON ---

    def test_json_roundtrip(self):
        d = Lattix({"a": 1, "b": [1, 2]})

        json_str = d.json()
        assert '"a": 1' in json_str

        d2 = Lattix.from_json(json_str)
        assert d2 == d

        # file I/O
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tf:
            tf.write('{"x": 10}')
            tf.close()
            try:
                d3 = Lattix.from_json(tf.name, from_file=True)
                assert d3.x == 10
            finally:
                os.remove(tf.name)

        # --- Start from data ---
        import json

        data = {"a": 1, "b": {"c": 2}, "d": [3, 5]}
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as f:
            json.dump(data, f)
            f.seek(0)
            path = f.name
        d = Lattix.from_json(path, from_file=True)

        assert d["a"] == 1
        assert d["b"]["c"] == 2
        assert d["d"] == [3, 5]

        data = {"a": "foo", "b": "bar", "c": "baz"}
        s = json.dumps(data).encode("utf-8")
        d = Lattix.from_json(s)

        assert d["a"] == "foo"
        assert d["b"] == "bar"
        assert d["c"] == "baz"

    def test_json_errors(self):
        with pytest.raises(exceptions.InvalidPayloadError):
            Lattix.from_json("{invalid_json")

        with pytest.raises(exceptions.UnsupportedPayloadError):
            Lattix.from_json(123)

    # --- 6. orjson ---

    def test_orjson_roundtrip(self):
        d = Lattix({"a": 1, "nested": {"b": 2}})
        result = d.orjson()
        assert isinstance(result, bytes)

        decoded = Lattix.from_orjson(result)
        assert decoded["a"] == 1
        assert decoded["nested"]["b"] == 2

    def test_orjson_mocked_to_hit_lambda(self):
        orjson_pkg = f"{top_mod}.serialization.json"
        with patch(f"{orjson_pkg}.compat.orjson.dumps") as mock_dumps:
            with patch(f"{orjson_pkg}.transform.serialize") as mock_serialize:
                mock_serialize.return_value = {"mocked": True}

                d = Lattix({"a": 1})
                d.orjson(indent=2)

                # Verify orjson.dumps was called
                args, kwargs = mock_dumps.call_args
                assert args[0] is d
                assert "option" in kwargs

                # Manually trigger the lambda to ensure its line is covered
                default_lambda = kwargs["default"]
                res = default_lambda(d)
                assert res == {"mocked": True}
                mock_serialize.assert_called_once_with(d)

    def test_orjson_error(self):
        with patch(f"{top_mod}.utils.compat.HAS_ORJSON", False):
            with patch(f"{top_mod}.utils.compat.orjson", None):
                with pytest.raises(exceptions.OptionalImportError):
                    _ = Lattix.from_orjson({})

                d = Lattix({"a": 1})
                with pytest.raises(exceptions.OptionalImportError):
                    d.orjson()

    # --- 7. msgpack ---

    def test_msgpack_roundtrip(self):
        d = Lattix({"x": 10, "y": [1, 2]})
        result = d.msgpack()
        assert isinstance(result, bytes)

        decoded = Lattix.from_msgpack(result)
        assert decoded["x"] == 10
        assert decoded["y"] == [1, 2]

        # --- Start from data ---
        import msgpack

        data = {
            "string_key": "hello",
            "int_key": 42,
            "nested": {"inner_key": "inner_val"},
            "list_key": [1, 2, 3],
        }
        packed_data = msgpack.packb(data, use_bin_type=True)
        d = Lattix.from_msgpack(packed_data)

        assert d["string_key"] == "hello"
        assert d["int_key"] == 42

        assert isinstance(d["nested"], Lattix)
        assert d["nested"]["inner_key"] == "inner_val"
        assert d["list_key"] == [1, 2, 3]

    def test_msgpack_mocked(self):
        with patch("msgpack.packb") as mock_pack:
            d = Lattix({"a": 1})
            d.msgpack()

            assert mock_pack.called
            assert mock_pack.call_args[1]["use_bin_type"] is True

    def test_msgpack_error(self):
        with patch(f"{top_mod}.utils.compat.HAS_MSGPACK", False):
            with patch(f"{top_mod}.utils.compat.msgpack", None):
                with pytest.raises(exceptions.OptionalImportError):
                    _ = Lattix.from_msgpack({})

                d = Lattix({"a": 1})
                with pytest.raises(exceptions.OptionalImportError):
                    d.msgpack()

    # --- 8. YAML ---

    def test_yaml_roundtrip(self):
        d = Lattix({"a": 1, "key": "value", "num": 123})

        # 0. yaml output
        y_str = d.yaml()
        assert "a: 1" in y_str

        # 1. string input
        d2 = Lattix.from_yaml(y_str)
        assert d2 == d

        # 2. bytes input
        d2 = Lattix.from_yaml(y_str.encode("utf-8"))
        assert d2["key"] == "value"

        # 3. file input
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write(y_str)
            temp_path = tf.name

        try:
            d2 = Lattix.from_yaml(temp_path, from_file=True)
            assert d2.num == 123
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_from_yaml_enhanced(self):
        yaml_data = "enhanced: true"
        d = Lattix.from_yaml(yaml_data, enhanced=True)
        assert d.enhanced is True

    def test_from_yaml_nested_conversion(self):
        import textwrap

        yaml_data = textwrap.dedent(
            """
            root:
              nested_list:
                - !!python/tuple [a, b]
                - key: val
              nested_set: !!set {x, y}
            nested:
              deep_key: deep_val
            list_of_dicts:
              - item: 1
            sequence:
              - 1
              - 2
            collection_set: !!set
              ? item1
              ? item2
            collection_tuple: !!python/tuple ['top', 'bottom']
        """
        )

        d = Lattix.from_yaml(yaml_data)

        assert isinstance(d.root.nested_list[1], Lattix)
        assert isinstance(d.root.nested_list[0], tuple)
        assert isinstance(d.root.nested_set, set)

        assert isinstance(d.nested, Lattix)
        assert d.nested.deep_key == "deep_val"

        assert isinstance(d.list_of_dicts, list)
        assert isinstance(d.list_of_dicts[0], Lattix)
        assert d.list_of_dicts[0].item == 1

        assert isinstance(d.collection_set, set)
        assert "item1" in d.collection_set

        assert isinstance(d.collection_tuple, tuple)
        assert d.collection_tuple[0] == "top"

    def test_yaml_errors(self):
        try:
            with pytest.raises(exceptions.InvalidPayloadError):
                Lattix.from_yaml("invalid: : yaml")
        except exceptions.OptionalImportError:
            pytest.skip("PyYAML not installed")

        invalid_yaml = "\tinvalid: tab_character_not_allowed"
        with pytest.raises(exceptions.InvalidPayloadError):
            Lattix.from_yaml(invalid_yaml)

        with patch(f"{top_mod}.utils.compat.HAS_YAML", False):
            with patch(f"{top_mod}.utils.compat.yaml", None):
                with pytest.raises(exceptions.OptionalImportError):
                    _ = Lattix().from_yaml("a: 1")

                with pytest.raises(exceptions.OptionalImportError):
                    _ = Lattix(a=1).yaml()

    # --- 9. pickle ---

    def test_pickle(self):
        d = Lattix(a=1, lazy_create=True)
        dumped = pickle.dumps(d)
        loaded = pickle.loads(dumped)
        assert loaded.a == 1
        assert loaded.lazy_create is True
        # Ensure reconstructed as Lattix
        assert isinstance(loaded, Lattix)

    # --- 10. edge cases ---

    def test_serialization_edge_cases(self):
        # from_json with dict input
        d = Lattix.from_json({"a": {"b": 1}})
        assert d.a.b == 1

        # from_yaml with enhanced and complex types
        yaml_data = "!!set {a, b}"
        d_yaml = Lattix.from_yaml(yaml_data, enhanced=True)

        assert isinstance(d_yaml, set)

        # yaml enhanced
        d = Lattix(a=1)
        assert "a: 1" in d.yaml(enhanced=True)

        # __setstate__ manual call (for 100% branch coverage)
        state = {
            "key": "test",
            "data": {"x": 1},
            "lazy": True,
            "sep": ".",
            "enable_lock": False,
            "frozen": False,
        }
        new_d = Lattix.__new__(Lattix)
        new_d.__setstate__(state)
        assert new_d.sep == "."
        assert new_d["x"] == 1


# ---------- Tests 11: Sorting ----------


class TestSorting:
    def test_sort_by_key(self):
        # no recursive
        d = Lattix({"b": 2, "a": 1, "c": {"y": 3, "z": 1}})
        d.sort_by_key()
        keys = list(d.keys())
        assert keys == ["a", "b", "c"]

        # recursive
        d = Lattix(b=2, a=1, c={"y": 2, "x": 1})
        d.sort_by_key(recursive=True)
        keys = list(d.keys())
        assert keys == ["a", "b", "c"]
        nested_keys = list(d.c.keys())
        assert nested_keys == ["x", "y"]

        # reverse
        d.sort_by_key(reverse=True, recursive=True)
        keys = list(d.keys())
        assert keys == ["c", "b", "a"]
        nested_keys = list(d.c.keys())
        assert nested_keys == ["y", "x"]

    def test_sort_by_value(self):
        d = Lattix({"x": 10, "y": 1, "z": 5})
        d.sort_by_value()
        keys = list(d.keys())
        # y(1) -> z(5) -> x(10)
        assert keys == ["y", "z", "x"]

        # reverse
        d = Lattix({"x": "foo", "y": "bar", "z": "baz"})
        d.sort_by_value(reverse=True)
        keys = list(d.keys())
        # x(foo) -> z(baz) -> y(bar)
        assert keys == ["x", "z", "y"]

        # recursive
        d = Lattix({"b": 2, "a": 1, "c": {"y": 3, "z": 1}})
        d.sort_by_value(recursive=True)
        keys = list(d.keys())
        assert keys == ["a", "b", "c"]
        keys = list(d.c.keys())
        assert keys == ["z", "y"]

        # (int, float) < str < others
        d = Lattix({"z": "string", "a": 10, "m": [1, 2]})
        d.sort_by_value()
        keys = list(d.keys())
        assert keys[0] == "a"  # numeric
        assert keys[1] == "z"  # string
        assert keys[2] == "m"  # repr fallback


# ---------- Tests 12: Cloning & Copying ----------


class TestCloning:
    def test_copy_shallow(self):
        d = Lattix(a={"b": 1})
        d2 = d.copy()
        assert d2 == d
        assert d2 is not d
        # Shallow: children objects are same
        assert d.a is d2.a

        d2.a.b = 999
        assert d.a.b == 999

    def test_copy_copy(self):
        from copy import copy

        d = Lattix(a={"b": 1})
        d2 = copy(d)
        assert d2 == d
        assert d2 is not d
        assert d.a is d2.a

        d2.a.b = 999
        assert d.a.b == 999

    def test_clone_deep_basic(self):
        d = Lattix(a={"b": 1}, lazy_create=True)

        # 1. reset state
        d2 = d.clone(deep=True, keep_state=False)
        assert d2 == d
        assert d2.lazy_create is False

        # 2. seperate lock
        d3 = d.clone(deep=True, keep_state=True)
        assert d3 == d
        assert d3.a is not d.a
        assert d3.lazy_create is True

        # 3. share lock
        d4 = d.clone(deep=True, keep_state=True, share_lock=True)
        assert d4 == d
        assert d4.a is not d.a
        assert d4._lock is d._lock

    def test_clone_deep_mapping(self):
        # 1. Mapping
        class UninstantiableMap(dict):
            def __init__(self, required_arg):
                super().__init__()
                self.arg = required_arg

        bad_map = UninstantiableMap("I need this")
        bad_map["key"] = "value"

        d = Lattix()
        d._children["standard_dict"] = {"a": 1}
        d._children["bad_map"] = bad_map

        cloned = d.clone(deep=True)
        assert isinstance(cloned["standard_dict"], Lattix)
        assert cloned["standard_dict"] == {"a": 1}

        assert type(cloned["bad_map"]) is Lattix
        assert cloned["bad_map"]["key"] == "value"

        # 2. Object
        class CustomObject:
            def __init__(self, x):
                self.x = x

            def __eq__(self, other):
                return isinstance(other, CustomObject) and self.x == other.x

        obj = CustomObject(10)
        d = Lattix({"item": obj})

        cloned = d.clone(deep=True)

        assert cloned["item"] == obj
        assert cloned["item"] is not obj

        # 3. Cycled
        root = Lattix({"name": "root"})
        root["self"] = root

        cloned = root.clone(deep=True)
        assert cloned["self"] is cloned
        assert id(cloned) == id(cloned["self"])

    def test_deepcopy_protocol(self):
        from copy import deepcopy

        d = Lattix(a=[1, 2])

        dcopy = deepcopy(d)
        assert dcopy == d
        assert dcopy is not d

        dcopy["a"].append(3)
        assert len(d["a"]) == 2

    def test_deepcopy_memo_trigger(self):
        from copy import deepcopy

        d = Lattix({"x": 1})
        container = [d, d]
        memo = {}

        cloned_container = deepcopy(container, memo)

        assert cloned_container[0] is cloned_container[1]
        assert cloned_container[0] is not d

        c1 = deepcopy(d, memo=memo)
        c2 = deepcopy(d, memo=memo)
        assert c1 is c2

        memo_shallow = {}
        s1 = d.clone(deep=False, memo=memo_shallow)
        s2 = d.clone(deep=False, memo=memo_shallow)
        assert s1 is s2


# ---------- Tests 13: Traversal ----------


class TestTraversals:
    def test_leaf_methods(self):
        d = Lattix(a=1, b={"c": 2})

        assert set(d.leaf_keys()) == {"a", "b/c"}
        assert set(d.leaf_values()) == {1, 2}

        d.map_leaves(lambda x: x * 2)
        assert d.a == 2
        assert d.b.c == 4

        d.filter_leaves(lambda x: x > 3)
        assert "a" not in d  # 2 removed
        assert d.b.c == 4  # Kept

        assert d.get_path("b/c", 99) == 4
        assert d.get_path("a/c", 99) == 99

        assert d.has_path() is False
        assert d.has_path("b/c") is True
        assert d.has_path("a/c") is False

        assert d.is_leaf() is False
        assert d.is_leaf("b/c") is True

    def test_traversal(self):
        d = Lattix(a={"b": 1})
        nodes = list(d.traverse(order="preorder"))
        assert len(nodes) == 2

        # Check cycle detection
        d["self"] = d
        with pytest.raises(ValueError):
            d.attach(d)

        # Ancestor cycle check
        child = d.a
        with pytest.raises(ValueError):
            d.attach(child)

    def test_traversal_order(self):
        #      root
        #     /    \
        #    a      b
        d = Lattix()
        d["a"] = 1
        d["b"] = 2

        # Preorder: root -> a -> b
        nodes = list(d.traverse("preorder"))
        assert nodes[0] is d

        # Postorder: a -> b -> root
        nodes_post = list(d.traverse("postorder"))
        assert nodes_post[-1] is d

        # Inorder: root -> a -> b
        nodes_in = list(d.traverse("inorder"))
        assert nodes_in[0] is d

    def test_records(self):
        d = Lattix(a=1)
        recs = d.to_records()
        assert recs == [("a", 1)]

    def test_purge_mixed_tree(self):
        d = Lattix(lazy_create=True)

        # Branch 1: Leads to a value
        d.configs.active.port = 8080

        # Branch 2: Leads to nowhere (ghost nodes)
        _ = d.unused.temporary.folder

        assert "unused" in d

        # Purge should only remove the 'unused' branch
        is_empty = d.purge()

        assert is_empty is False  # Tree is NOT empty because of port 8080
        assert "configs" in d
        assert "unused" not in d
        assert d.configs.active.port == 8080


# ---------- Tests 14: Lifecycle & Threading ----------


class TestLifeCycle:
    # --- 1. threading ---

    def test_locking_enabled_init(self):
        d = Lattix(enable_lock=True)
        assert d.locking_enabled
        assert d._lock is not None

    def test_lock_propagation(self):
        root = Lattix(enable_lock=True)
        child = Lattix()

        root["child"] = child

        # Child should inherit lock status and the lock object
        assert root.child is child
        assert child.locking_enabled
        assert child._lock is root._lock

    def test_context_manager(self):
        d = Lattix(enable_lock=True)
        with d:  # __enter__ / __exit__
            d["a"] = 1
        assert d["a"] == 1

    def test_attach(self):
        root = Lattix(enable_lock=True)
        child = Lattix(key="child")
        child.attach(root)

        assert child.parent is root
        assert "child" in root
        assert root["child"] is child

    def test_detach_clears_locks(self):
        root = Lattix(enable_lock=True)
        child = Lattix()
        root["child"] = child
        child._children.update(
            {
                "nums": 1,
                "mapping": {"foo": "bar"},
                "iterable": [1, 2, 3],
                "other": object(),
            }
        )

        assert child.parent is root

        # Detach
        child.detach(clear_locks=True)
        assert child.parent is None
        assert "child" not in root
        assert not child.locking_enabled
        assert child._lock is None
        # Root still locked
        assert root.locking_enabled

    def test_transplant(self):
        root = Lattix(a=1)
        child = Lattix(b=2)
        root["child"] = child

        new_parent = Lattix()
        child.transplant(new_parent, key="new_child")
        assert child.parent is new_parent
        assert new_parent["new_child"] is child

    # --- 2. attr propagation ---

    def test_propagation_complex_structures(self):
        root = Lattix(sep="/")
        child = Lattix()
        # Put a Lattix inside a list inside a dict
        root["data"] = {"list": [child]}
        root.sep = "."
        # Check if propagation reached through the list/dict
        assert root.data["list"][0].sep == "."
        assert child.sep == "/"  # no Change
        assert root.data["list"][0] == child
        assert root.data["list"][0] is not child

        root.lazy_create = True
        assert root.data["list"][0].lazy_create
        assert not child.lazy_create  # no Change

        # Cycled propagation
        root.update(
            {
                "nums": 1,
                "iterable": [1, 2, 3],
                "other": object(),
            }
        )
        root._children.update(
            {
                "mapping": {"foo": "bar"},
                "child": child,
            }
        )
        child._children["parent"] = root
        assert root.is_cycled()

        root.sep = "//"
        assert child.sep == "//"
        assert root.mapping.sep == "//"

    # --- 3. freeze / unfreeze ---
    def test_freeze_unfreeze(self):
        # --- freeze ---
        d = Lattix({"a": 1})
        d.freeze()
        assert d._frozen is True

        with pytest.raises(
            exceptions.ModificationDeniedError, match="is frozen and cannot be modified"
        ):
            d["a"] = 2

        with pytest.raises(exceptions.ModificationDeniedError):
            d.b = 3

        # --- unfreeze ---
        d.unfreeze()
        assert d._frozen is False

        d["a"] = 2
        assert d["a"] == 2

        # --- empty ---
        d = Lattix()
        d.freeze()
        assert d._frozen is True

        d.unfreeze()
        assert d._frozen is False

    def test_freeze_unfreeze_recursive(self):
        d = Lattix({"nested": {"key": "value"}})
        child = d.nested

        d.freeze()

        assert d._frozen is True
        assert child._frozen is True

        with pytest.raises(TypeError):
            child["key"] = "new_value"

        # --- unfreeze ---
        d.unfreeze()
        assert child._frozen is False

        child["key"] = "updated"
        assert child["key"] == "updated"

    # --- 4. __del__ ---

    def test_del(self):
        import gc
        import weakref

        parent = Lattix()
        child = Lattix(data={"a": 1}, key="child", parent=parent)
        parent._children["child"] = child
        object.__setattr__(child, "_detached", False)

        child_ref = weakref.ref(child)

        del child
        del parent
        gc.collect()

        assert child_ref() is None

    def test_del_is_finalizing(self):
        d = Lattix(key="shutdown_test")

        with patch("sys.is_finalizing", return_value=True):
            with patch(f"{top_mod}.structures.mapping.logger") as mock_logger:
                d.__del__()
                mock_logger.isEnabledFor.assert_not_called()

    def test_del_safety_sys_none(self):
        node = Lattix(key="dead_sys")

        with patch(f"{top_mod}.structures.mapping.sys", None):
            with patch(f"{top_mod}.structures.mapping.logger") as mock_logger:
                try:
                    node.__del__()
                except Exception as e:
                    pytest.fail(f"__del__ raised {type(e).__name__} when sys was None")
                mock_logger.isEnabledFor.assert_not_called()

    def test_circular_reference_cleanup(self):
        import gc
        import weakref

        root = Lattix()
        child = Lattix()
        child.attach(root)
        root["link"] = child

        assert root.is_cycled()

        root_ref = weakref.ref(root)
        child_ref = weakref.ref(child)

        del root
        del child

        # Since they have circular refs, they won't die until GC runs
        gc.collect()

        assert root_ref() is None
        assert child_ref() is None


# ---------- Tests 15: Edge Cases ----------


class TestEdgeCase:
    def test_construct_type_hint_shim(self):
        # __class_getitem__
        assert Lattix[str, int]

    def test_arg_type_error(self):
        d = Lattix()
        with pytest.raises(exceptions.ArgTypeError):
            d.update(123)

    def test_operand_error(self):
        d = Lattix()
        with pytest.raises(exceptions.ArgTypeError):
            _ = d + 123

    def test_walk_path(self):
        d = Lattix({"a": 1})
        with pytest.raises(exceptions.UnexpectedNodeError):
            d._walk_path("a/b")

        d = Lattix(lazy_create=True)
        with pytest.raises(exceptions.PathNotFoundError):
            d._walk_path("non/existent", force_no_create=True)

        d = Lattix({"a": 1})
        assert d._walk_path("a", stop_before_last=True) == (d, "a")

    def test_walk_path_final_leaf_promotion(self):
        root = Lattix()
        root["sub"] = {"initial": 1}

        sub_node = root["sub"]
        raw_mapping = {"target_key": "target_value"}

        sub_node_children = object.__getattribute__(sub_node, "_children")
        sub_node_children["raw_dict"] = raw_mapping

        result = root._walk_path("sub/raw_dict")

        assert isinstance(result, Lattix), (
            "The raw dict should have been promoted to Lattix"
        )
        assert result["target_key"] == "target_value"
        assert result.parent is sub_node, (
            "The promoted node should be linked to its parent"
        )

        assert isinstance(sub_node_children["raw_dict"], Lattix)

    def test_walk_path_promotion_with_different_mapping_types(self):
        from collections import OrderedDict

        root = Lattix()
        root["sub"] = {}

        sub_node = root["sub"]
        ordered_data = OrderedDict([("first", 1), ("second", 2)])
        object.__getattribute__(sub_node, "_children")["ordered"] = ordered_data

        result = root._walk_path("sub/ordered")

        assert isinstance(result, Lattix)
        assert result["first"] == 1
        assert list(result.keys()) == ["first", "second"]
