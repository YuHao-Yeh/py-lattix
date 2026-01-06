from __future__ import annotations

__all__ = ["LattixNode"]

from typing import TYPE_CHECKING, Any
import weakref

from ..utils.exceptions import (
    DuplicatedKeyError, UnattachableError, UnexpectedNodeError
)

if TYPE_CHECKING:   # pragma: no cover
    from collections.abc import Callable, Iterable
    from weakref import ReferenceType
    from ..utils.types import (
        TRAV_ORDER, DictType, ListType, SetType, TupleType
    )


class LattixNode:
    """Hierarchical node supporting parent-child relationships."""
    
    __slots__ = ("_parent", "_children", "_key", "__weakref__")
    _parent: ReferenceType[LattixNode] | None
    _children: DictType[str, Any]
    _key: str | None

    def __init__(self, key: str = "", parent: Any = None):
        self._key = key
        self._children = {}
        self._parent = None

        if parent is not None:
            LattixNode.attach(self, parent)

    # ========== Parent / Children Properties ==========
    @property
    def key(self) -> str:
        return self._key

    @property
    def parent(self) -> LattixNode | None:
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, value: LattixNode | None):
        self._parent = weakref.ref(value) if value is not None else None

    @property
    def children(self) -> DictType[str, Any]:
        return self._children

    # ========== Dict-like API ==========
    def __len__(self):
        return len(self._children)
    
    def __contains__(self, key: str):
        return key in self._children
    
    def keys(self):
        """Return all top-level keys (equivalent to dict.keys())."""
        return self._children.keys()
    
    def values(self):
        """Return all top-level values (equivalent to dict.values())."""
        return self._children.values()

    def items(self):
        """Return all top-level (key, value) pairs (equivalent to dict.items())."""
        return self._children.items()
    
    def empty(self):
        return len(self._children) == 0
    
    # ========== Hierarchy Operations ==========
    def detach(self):
        """Detach from parent (if any)."""
        p = self.parent
        if p:
            _ = p._children.pop(self._key, None)
           
        self._parent = None
        return self

    def attach(self, parent: Any):
        """Attach to a new parent."""
        self._validate_parent_node(parent)
        self._validate_attachable_node(self, parent)

        self.parent = parent
        parent._children[self._key] = self
        return self
    
    def transplant(self, parent: Any, key: str = ""):
        """Transplant to a new parent."""
        self._validate_parent_node(parent)

        p = self.parent
        if p:
            _ = p._children.pop(self._key, None)
        
        if key:
            object.__setattr__(self, "_key", key)

        self.parent = parent
        parent._children[self._key] = self

        return self

    # ========== Validation ==========
    @staticmethod
    def _validate_parent_node(parent: Any):
        if not isinstance(parent, LattixNode):
            raise UnexpectedNodeError(parent, parent)
        return True

    @staticmethod
    def _validate_attachable_node(obj: Any, parent: Any):
        # Check key duplication in parent's namespace
        if (obj._key in parent._children
            and parent._children[obj._key] is not obj):
            raise DuplicatedKeyError(obj._key)

        # Cycle prevention
        if parent is obj:
            raise ValueError("Cycle detected: cannot attach node as a descendant of itself.")

        if obj in parent._ancestors():
            raise ValueError("Cycle detected: cannot attach node as a descendant of itself.")

        # If already has a parent
        if obj._parent and obj._parent is not parent:
            raise UnattachableError
        
        return True

    # ========== Ancestors / Tree utils ==========
    def is_root(self):
        """Return True if this node has no parent."""
        return self._parent is None
    
    def get_parent(self):
        """Return the parent node, if any."""
        return self.parent

    def _ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent
    
    def get_root(self):
        node = self
        while node._parent is not None:
            parent = node.parent
            if parent is None:
                break
            node = parent
        return node

    def is_cycled(self):
        seen: SetType[Any] = set()
        stack: ListType[Any] = [self]
        while stack:
            node = stack.pop()
            if id(node) in seen:
                return True
            seen.add(id(node))
            for child in getattr(node, "_children", {}).values():
                if isinstance(child, LattixNode):
                    stack.append(child)
        return False

    # ========== Walk / Traverse ==========
    def walk(
        self, 
        path: TupleType[Any, ...] = ()
    ) -> Iterable[tuple[tuple[str, ...], Any]]:
        """Yield (path_tuple, node_or_leaf_value)."""
        for key, value in self._children.items():
            new_path = path + (key,)
            yield new_path, value
            if isinstance(value, LattixNode):
                yield from value.walk(new_path)

    def traverse(
        self, 
        order: TRAV_ORDER = "preorder", 
        _seen: SetType[int] | None = None
    ) -> Iterable[LattixNode]:
        """
        DFS traverse of LattixNodes in given order.
        
        - preorder: root → children
        - inorder: left → root → right (only if exactly 2 children)
        - postorder: children → root
        """
        _seen = _seen or set()
        if id(self) in _seen:
            raise RuntimeError(f"Cycle detected at LattixNode {self._key}")
        _seen.add(id(self))
    
        if order == "preorder":
            yield self
            for _, cvalue in self._children.items():
                if isinstance(cvalue, LattixNode):
                    yield from cvalue.traverse(order, _seen)
        
        elif order == "inorder":
            child_list = [(k, v) for k, v in self._children.items() if isinstance(v, LattixNode)]
            n = len(child_list)
            if n == 0:
                yield self
            elif n == 1:
                yield from child_list[0][1].traverse(order, _seen)
                yield self
            elif n == 2:
                yield from child_list[0][1].traverse(order, _seen)
                yield self
                yield from child_list[1][1].traverse(order, _seen)
            else:
                # More than 2 children
                yield from child_list[0][1].traverse(order, _seen)
                yield self
                for _, child in child_list[1:]:
                    yield from child.traverse(order, _seen)

        elif order == "postorder":
            for child, cvalue in self._children.items():
                if isinstance(cvalue, LattixNode):
                    yield from cvalue.traverse(order, _seen)
            yield self
        else:
            raise ValueError(f"Unknown traversal order: {order}")
    
    # ========== Leaf Utilities ==========
    def leaf_keys(self):
        """
        Recursively yield all leaf keys as full paths.

        Each leaf key is represented as a string showing the full path
        from the top-level Lattix, joined by the path separator (default '/').

        Returns:
            An iterator of full leaf key strings.

        Example:
            >>> d = Lattix({"a": {"b": 1, "c": 2}})
            >>> list(d.leaf_keys())
            ['a/b', 'a/c']
        """
        for path, value in self.walk():
            if not isinstance(value, LattixNode):
                yield "/".join(path)

    def leaf_values(self):
        """
        Recursively yield all leaf values.

        Leaf values are all non-Lattix values stored in the Lattix tree.
        To get a full list, wrap with `list()`, e.g., `list(d.leaf_values())`.

        Returns:
            An iterator of leaf values.
        
        Example:
            >>> d = Lattix({"a": {"b": 1, "c": 2}})
            >>> list(d.leaf_values())
            [1, 2]
        """
        for _, value in self.walk():
            if not isinstance(value, LattixNode):
                yield value

    def map_leaves(self, func: Callable[..., Any]):
        """
        Apply a function to every leaf value (in place).

        Args:
            func: A callable that takes a leaf value and returns a new value.
        """
        for k, v in list(self._children.items()):
            if isinstance(v, LattixNode):
                v.map_leaves(func)
            else:
                self._children[k] = func(v)

    def filter_leaves(self, func: Callable[..., bool]):
        """
        Filter out leaf nodes where func(value) is False.

        Args:
            func: Predicate returning True to keep, False to remove.
        """
        to_delete: ListType[Any] = []

        for k, v in list(self._children.items()):
            if isinstance(v, LattixNode):
                v.filter_leaves(func)
                if len(v) == 0:
                    to_delete.append(k)
            else:
                if not func(v):
                    to_delete.append(k)

        for k in to_delete:
            del self._children[k]

    # ========== Flatten Records ==========
    def to_records(self) -> ListType[TupleType[str, Any]]:
        """Flatten all leaf paths/values into a list of (path, value) tuples."""
        return [(k, v) for k, v in zip(self.leaf_keys(), self.leaf_values())]

    # ========== Representation ==========
    def __repr__(self):
        return f"LattixNode(key={self._key!r}, children={self._children!r})"


if __name__ == "__main__":
    import inspect
    for base in [LattixNode]:
        for c in base.__mro__:
            slots = getattr(c, "__slots__", None)
            has_dict = False
            if "__dict__" in (slots if isinstance(slots, (list, tuple)) else (slots or ())):
                has_dict = True
            print(f"{c!r:60} | __slots__ = {slots!r:30} | has '__dict__' in slots? {has_dict}")

        print("\n=== Check if any base is builtin heap type (like dict) ===")
        for c in base.__mro__:
            print(c, "is builtin type subclass of dict?", issubclass(c, dict) if inspect.isclass(c) else "n/a")

        print("\n=== Show attrs related to __dict__ presence ===")
        for c in base.__mro__:
            print(c.__name__, "->", "has __dict__ attribute?", "__dict__" in c.__dict__)

        print()
