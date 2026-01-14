import gc

import pytest

# ---------- Setup ----------
from src.lattix.core.base import LattixNode
from src.lattix.utils.exceptions import (
    DuplicatedKeyError,
    UnattachableError,
    UnexpectedNodeError,
)

# ---------- Tests 1: LattixNode ----------


class TestLattixNode:
    # --- 1. Basic Initialization & Properties ---

    def test_node_init_and_properties(self):
        node = LattixNode("root")
        assert node.key == "root"
        assert node.parent is None
        assert node.children == {}
        assert node.is_root()
        assert repr(node) == "LattixNode(key='root', children={})"

    def test_node_init_with_parent(self):
        parent = LattixNode("parent")
        child = LattixNode("child", parent=parent)

        assert child.parent is parent
        assert parent.children["child"] is child
        assert not child.is_root()

    # --- 2. Dict-like API ---

    def test_dict_api(self):
        root = LattixNode("root")
        root._children["a"] = 1
        root._children["b"] = 2

        assert len(root) == 2
        assert "a" in root
        assert "z" not in root
        assert list(root.keys()) == ["a", "b"]
        assert list(root.values()) == [1, 2]
        assert list(root.items()) == [("a", 1), ("b", 2)]
        assert not root.empty()

        root._children.clear()
        assert root.empty()

    # --- 3. Hierarchy Operations (Attach/Detach/Transplant) ---

    def test_attach_detach(self):
        parent = LattixNode("parent")
        child = LattixNode("child")

        # Attach
        child.attach(parent)
        assert child.parent is parent
        assert "child" in parent

        # Detach
        child.detach()
        assert child.parent is None
        assert "child" not in parent

        # Detach when already detached (no-op)
        child.detach()
        assert child.parent is None

    def test_transplant(self):
        old_p = LattixNode("old")
        new_p = LattixNode("new")
        child = LattixNode("child", parent=old_p)

        # Transplant with rename
        child.transplant(new_p, key="moved_child")

        assert child.parent is new_p
        assert child.key == "moved_child"
        assert "moved_child" in new_p
        assert "child" not in old_p

        # Transplant without rename
        child.transplant(old_p)
        assert child.key == "moved_child"  # Keeps current key
        assert "moved_child" in old_p

    # --- 4. Validations & Exceptions ---

    def test_validate_parent_node(self):
        child = LattixNode("c")
        with pytest.raises(UnexpectedNodeError):
            child.attach("Not a node")

    def test_validate_duplicate_key(self):
        parent = LattixNode("p")
        _ = LattixNode("c", parent=parent)
        c2 = LattixNode("c")

        with pytest.raises(DuplicatedKeyError):
            c2.attach(parent)

    def test_validate_cycle_prevention(self):
        # A -> B -> C
        a = LattixNode("A")
        b = LattixNode("B", parent=a)
        c = LattixNode("C", parent=b)

        # Try to attach A to C (Cycle)
        with pytest.raises(ValueError, match="Cycle detected"):
            a.attach(c)

        # Try to attach A to A
        with pytest.raises(ValueError, match="Cycle detected"):
            a.attach(a)

    def test_validate_unattachable(self):
        p1 = LattixNode("p1")
        p2 = LattixNode("p2")
        c = LattixNode("c", parent=p1)

        # Cannot attach to p2 while still attached to p1
        with pytest.raises(UnattachableError):
            c.attach(p2)

    # --- 5. Tree Utils & Weak References ---

    def test_get_root(self):
        a = LattixNode("A")
        b = LattixNode("B", parent=a)
        c = LattixNode("C", parent=b)

        assert c.get_root() is a
        assert a.get_root() is a
        assert c.get_parent() is b

    def test_weakref_parent(self):
        parent = LattixNode("parent")
        child = LattixNode("child", parent=parent)

        del parent
        gc.collect()

        assert child.parent is None
        # get_root should stop at self if parent is dead/None
        assert child.get_root() is child

    def test_is_cycled_algorithm(self):
        # The standard attach() prevents cycles, so we must manually hack the structure
        # to test the detection algorithm.
        n1 = LattixNode("n1")
        n2 = LattixNode("n2")
        n3 = LattixNode("n3")

        # Link manually
        n1._children["n2"] = n2
        n2._children["n3"] = n3
        n3._children["n1"] = n1  # Cycle

        assert n1.is_cycled() is True

        # Non-cycled check
        clean = LattixNode("clean")
        clean._children["n1"] = "n1"
        assert clean.is_cycled() is False

    # --- 6. Traversal (Pre, Post, Inorder) ---

    def test_traverse_preorder(self):
        # Root -> A -> B
        root = LattixNode("root")
        a = LattixNode("a", parent=root)
        _ = LattixNode("b", parent=a)

        nodes = [n.key for n in root.traverse("preorder")]
        assert nodes == ["root", "a", "b"]

        # Root -> A -> B -> C
        c = LattixNode("c", parent=root)
        c._children["d"] = [1, 2, 3]
        nodes = [n.key for n in root.traverse("preorder")]
        assert nodes == ["root", "a", "b", "c"]

    def test_traverse_postorder(self):
        # Root -> A -> B
        root = LattixNode("root")
        a = LattixNode("a", parent=root)
        _ = LattixNode("b", parent=a)

        nodes = [n.key for n in root.traverse("postorder")]
        assert nodes == ["b", "a", "root"]

        c = LattixNode("c", parent=a)
        c._children["e"] = [1, 2, 3]
        nodes = [n.key for n in root.traverse("postorder")]
        assert nodes == ["b", "c", "a", "root"]

    def test_traverse_inorder_variants(self):
        """Test the specific branches for 0, 1, 2, and >2 children."""

        # Case 0: No children
        root = LattixNode("root")
        assert [n.key for n in root.traverse("inorder")] == ["root"]

        # Case 1: One child (Left -> Root) effectively
        _ = LattixNode("c1", parent=root)
        # inorder logic: child[0], self
        assert [n.key for n in root.traverse("inorder")] == ["c1", "root"]

        # Case 2: Two children (Left -> Root -> Right)
        _ = LattixNode("c2", parent=root)
        # Structure: root has c1, c2
        # Logic: c1 -> root -> c2
        assert [n.key for n in root.traverse("inorder")] == ["c1", "root", "c2"]

        # Case 3: More than 2 children
        _ = LattixNode("c3", parent=root)
        # Logic: c1 -> root -> c2 -> c3 ...
        assert [n.key for n in root.traverse("inorder")] == ["c1", "root", "c2", "c3"]

    def test_traverse_errors(self):
        node = LattixNode("node")
        with pytest.raises(ValueError, match="Unknown traversal order"):
            list(node.traverse("invalid_order"))

        # Cycle detection inside traverse
        # Hack a cycle manually
        node._children["self"] = node
        with pytest.raises(RuntimeError, match="Cycle detected"):
            list(node.traverse("preorder"))

    # --- 7. Leaves, Walking, and Flattening ---

    def test_walk_and_leaves(self):
        # root -> a -> leaf1 (10)
        #      -> b (20)
        root = LattixNode("root")
        a = LattixNode("a", parent=root)
        a._children["leaf1"] = 10
        root._children["b"] = 20

        # Walk
        walk_results = list(root.walk())
        # Expected: (('a',), node_a), (('a', 'leaf1'), 10), (('b',), 20)
        # Note: Order depends on dict insertion, usually stable in modern python
        keys = [path for path, _ in walk_results]
        assert ("a",) in keys
        assert ("a", "leaf1") in keys
        assert ("b",) in keys

        # Leaf Keys (strings)
        l_keys = list(root.leaf_keys())
        assert "a/leaf1" in l_keys
        assert "b" in l_keys
        assert "a" not in l_keys  # 'a' is a node, not a leaf

        # Leaf Values
        l_vals = list(root.leaf_values())
        assert 10 in l_vals
        assert 20 in l_vals

        # To Records
        records = root.to_records()
        assert ("a/leaf1", 10) in records
        assert ("b", 20) in records

    def test_map_leaves(self):
        root = LattixNode("root")
        a = LattixNode("a", parent=root)
        a._children["v1"] = 1
        root._children["v2"] = 2

        root.map_leaves(lambda x: x * 10)

        assert a.children["v1"] == 10
        assert root.children["v2"] == 20

    def test_filter_leaves(self):
        # root -> a -> keep (1)
        #           -> toss (2)
        #      -> b -> toss (2)
        #      -> c -> keep (1)

        root = LattixNode("root")
        a = LattixNode("a", parent=root)
        b = LattixNode("b", parent=root)
        c = LattixNode("c", parent=root)

        a._children["keep"] = 1
        a._children["toss"] = 2
        b._children["toss"] = 2  # b should become empty and thus removed
        c._children["keep"] = 1

        # Filter: keep odd numbers
        root.filter_leaves(lambda x: x % 2 != 0)

        assert "keep" in a
        assert "toss" not in a

        assert "c" in root  # kept
        assert "b" not in root  # removed because it became empty
        assert "a" in root  # kept because it has 'keep'

    def test_purge_mixed_tree(self):
        d = LattixNode()

        # Branch 1: Leads to a value
        configs = LattixNode("configs", parent=d)
        active = LattixNode("active", parent=configs)
        active.children["port"] = 8080
        _ = LattixNode("unused", parent=d)

        # Purge should only remove the 'unused' branch
        is_empty = d.purge()

        assert is_empty is False  # Tree is NOT empty because of port 8080
        assert "configs" in d
        assert "unused" not in d
