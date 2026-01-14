"""Lattix hierarchical node implementation.

This module provides the :class:`LattixNode` class, which serves as the
fundamental structural component for the Lattix hierarchical mapping system.
It defines the logic for parent-child relationships, tree traversal, and
leaf-level data manipulation.

The implementation focuses on:
    * **Memory Efficiency**: Utilizing ``__slots__`` to reduce memory footprint.
    * **Integrity**: Using weak references (``weakref``) for parent pointers to
      prevent memory leaks caused by circular references in deep trees.
    * **Versatility**: Providing various traversal strategies (preorder, inorder,
      postorder) and recursive "walk" operations.
    * **Hierarchy Management**: Safe attachment, detachment, and transplantation
      of subtrees between parent nodes.

This module is a core internal component and is intended to be inherited by
concrete mapping implementations like :class:`lattix.structures.mapping.Lattix`.

Example:
    >>> root = LattixNode("root")
    >>> child = LattixNode("child", parent=root)
    >>> root.empty()
    False
    >>> list(root.keys())
    ['child']

Classes:
    LattixNode: A generic class representing a node in a hierarchical tree.
"""

from __future__ import annotations

import weakref
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from ..utils.constant import DFLT_SEP
from ..utils.exceptions import (
    DuplicatedKeyError,
    UnattachableError,
    UnexpectedNodeError,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from weakref import ReferenceType

    from ..utils.types import TRAV_ORDER

__all__ = ["LattixNode"]

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class LattixNode(Generic[_KT, _VT]):
    """Hierarchical node supporting parent-child relationships.

    This class serves as the structural backbone for hierarchical data,
    managing weak references to parents and a registry of children. It provides
    utilities for tree traversal, path walking, and leaf manipulation.

    Attributes:
        _parent: A weak reference to the parent node to avoid circular references.
        _children: A dictionary mapping keys to child nodes or leaf values.
        _key: The string identifier for this node within its parent.
    """

    __slots__ = ("_parent", "_children", "_key", "__weakref__")

    # ========== Class-level constants ==========
    _parent: ReferenceType[LattixNode] | None
    _children: dict[str, Any]
    _key: str

    # ========== Init ==========
    def __init__(self, key: str = "", parent: Any = None):
        """Initialize a LattixNode.

        Args:
            key: The identifier for this node. Defaults to "".
            parent: An optional parent node to attach to upon initialization.
        """
        self._key = key
        self._children = {}
        self._parent = None

        if parent is not None:
            self.attach(parent)

    # ========== Parent / Children Properties ==========
    @property
    def key(self):
        """Return the identifier of this node."""
        return self._key

    @property
    def parent(self):
        """Return the parent node or None if this is a root node."""
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, value: LattixNode | None):
        """Set the parent node using a weak reference.

        Args:
            value: The LattixNode instance to set as parent.
        """
        self._parent = weakref.ref(value) if value is not None else None

    @property
    def children(self):
        """Return the internal dictionary of children."""
        return self._children

    # ========== Dict-like API ==========
    def __len__(self):
        """Return the number of direct children."""
        return len(self._children)

    def __contains__(self, key: object, /):
        """Check if a key exists in direct children."""
        return key in self._children

    def keys(self):
        """Return a view of all top-level keys."""
        return self._children.keys()

    def values(self):
        """Return a view of all top-level values (nodes or scalars)."""
        return self._children.values()

    def items(self):
        """Return a view of all top-level (key, value) pairs."""
        return self._children.items()

    def empty(self):
        """Check if the node has no children.

        Returns:
            True if children count is zero, False otherwise.
        """
        return len(self._children) == 0

    # ========== Hierarchy Operations ==========
    def detach(self):
        """Detach this node from its parent.

        Removes the node from the parent's children dictionary and clears
        the internal parent reference.
        """
        p = self.parent
        if p:
            _ = p._children.pop(self._key, None)

        self._parent = None

    def attach(self, parent: LattixNode):
        """Attach this node to a new parent.

        Args:
            parent: The LattixNode instance to attach to.

        Raises:
            UnexpectedNodeError: If parent is not a LattixNode.
            DuplicatedKeyError: If the parent already has a child with this node's key.
            ValueError: If the attachment would create a cycle.
            UnattachableError: If the node is already attached to a different parent.
        """
        self._validate_parent_node(parent)
        self._validate_attachable_node(self, parent)

        self.parent = parent
        parent._children[self._key] = self

    def transplant(self, parent: LattixNode, key: _KT = ""):
        """Move this node to a new parent, optionally renaming it.

        Args:
            parent: The target LattixNode to move to.
            key: Optional new key for the node. If empty, the existing key is used.
        """
        self._validate_parent_node(parent)

        p = self.parent
        if p:
            _ = p._children.pop(self._key, None)

        if key:
            object.__setattr__(self, "_key", key)

        self.parent = parent
        parent._children[self._key] = self

    # ========== Validation ==========
    @staticmethod
    def _validate_parent_node(parent: Any):
        """Validate that an object is a LattixNode.

        Args:
            parent: The object to validate.

        Returns:
            True if valid.

        Raises:
            UnexpectedNodeError: If the object is not a LattixNode.
        """
        if not isinstance(parent, LattixNode):
            raise UnexpectedNodeError(parent, parent)
        return True

    @staticmethod
    def _validate_attachable_node(obj: LattixNode, parent: LattixNode):
        """Validate if a node can be attached to a parent.

        Args:
            obj: The node to be attached.
            parent: The target parent node.

        Returns:
            True if the operation is safe.

        Raises:
            DuplicatedKeyError: If key exists in parent and isn't this node.
            ValueError: If attaching creates a circular reference.
            UnattachableError: If node is already attached elsewhere.
        """
        # Check key duplication in parent's namespace
        if obj._key in parent._children and parent._children[obj._key] is not obj:
            raise DuplicatedKeyError(obj._key)

        # Cycle prevention
        if parent is obj:
            raise ValueError(
                "Cycle detected: cannot attach node as a descendant of itself."
            )

        if obj in parent._ancestors():
            raise ValueError(
                "Cycle detected: cannot attach node as a descendant of itself."
            )

        # If already has a parent
        if obj._parent and obj._parent is not parent:
            raise UnattachableError

        return True

    # ========== Ancestors / Tree utils ==========
    def is_root(self):
        """Check if the node is a root node."""
        return self._parent is None

    def get_parent(self):
        """Helper to retrieve the current parent."""
        return self.parent

    def _ancestors(self):
        """Yield all parent nodes up to the root.

        Yields:
            LattixNode: The next parent in the hierarchy.
        """
        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def get_root(self):
        """Traverse upwards to find the top-level node.

        Returns:
            The root LattixNode of the tree.
        """
        node = self
        while node._parent is not None:
            parent = node.parent
            if parent is None:
                break
            node = parent
        return node

    def is_cycled(self):
        """Check the entire subtree for circular references.

        Returns:
            True if a cycle is detected, False otherwise.
        """
        seen: set[Any] = set()
        stack: list[Any] = [self]
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
    def walk(self, path: tuple[_KT, ...] = ()):
        """Recursively yield every node and leaf in the tree.

        Args:
            path: The accumulated path tuple. Defaults to ().

        Yields:
            A tuple of (full_path_tuple, value).
        """
        for key, value in self._children.items():
            new_path = path + (key,)
            yield new_path, value
            if isinstance(value, LattixNode):
                yield from value.walk(new_path)

    def traverse(self, order: TRAV_ORDER = "preorder", _seen: set[int] | None = None):
        """Traverse the tree nodes using Depth-First Search (DFS).

        Args:
            order: Traversal strategy: 'preorder', 'inorder', or 'postorder'.
                Defaults to "preorder".
            _seen: Internal set to prevent infinite loops in cycled trees.

        Yields:
            LattixNode: The next node in the specified order.

        Raises:
            RuntimeError: If a cycle is detected.
            ValueError: If an unknown order is provided.
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
            child_list = [
                (k, v) for k, v in self._children.items() if isinstance(v, LattixNode)
            ]
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
            for _, cvalue in self._children.items():
                if isinstance(cvalue, LattixNode):
                    yield from cvalue.traverse(order, _seen)
            yield self
        else:
            raise ValueError(f"Unknown traversal order: {order}")

    # ========== Leaf Utilities ==========
    def leaf_keys(self):
        """Recursively yield all leaf keys as full paths joined by '/'.

        Yields:
            str: The full path string (e.g., "a/b/c").

        Example:
            >>> from lattix import Lattix
            >>> d = Lattix({"a": {"b": 1, "c": 2}})
            >>> list(d.leaf_keys())
            ['a/b', 'a/c']
        """
        for path, value in self.walk():
            if not isinstance(value, LattixNode):
                yield DFLT_SEP.join(cast(Iterable, path))

    def leaf_values(self):
        """Recursively yield all leaf values in the tree.

        Yields:
            Any: The stored leaf value.

        Example:
            >>> from lattix import Lattix
            >>> d = Lattix({"a": {"b": 1, "c": 2}})
            >>> list(d.leaf_values())
            [1, 2]
        """
        for _, value in self.walk():
            if not isinstance(value, LattixNode):
                yield value

    def map_leaves(self, func: Callable[[_VT], _VT]):
        """Apply a function to every leaf value in place.

        Args:
            func: A callable that accepts a leaf value and returns a new value.
        """
        for k, v in list(self._children.items()):
            if isinstance(v, LattixNode):
                v.map_leaves(func)
            else:
                self._children[k] = func(v)

    def filter_leaves(self, func: Callable[[_VT], bool]):
        """Remove leaf nodes based on a predicate function.

        Empty branches resulting from the removal are also pruned.

        Args:
            func: A predicate returning True to keep a leaf, False to remove it.
        """
        to_delete: list[Any] = []

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

    def purge(self):
        """Recursively remove all branches that contain no leaf values.

        Returns:
            bool: True if this node is now empty, False otherwise.
        """
        to_delete = []

        for key, child in self._children.items():
            if isinstance(child, LattixNode):
                if child.purge():
                    to_delete.append(key)
            # Not delete actual scalars/primitives

        for key in to_delete:
            del self._children[key]

        return len(self._children) == 0  # True if empty

    # ========== Flatten Records ==========
    def to_records(self):
        """Flatten the LattixNode into a list of (path, value) pairs.

        Returns:
            A list of tuples containing the full path string and the leaf value.
        """
        return [(k, v) for k, v in zip(self.leaf_keys(), self.leaf_values())]

    # ========== Representation ==========
    def __repr__(self):
        """Return a developer-friendly string representation."""
        return f"LattixNode(key={self._key!r}, children={self._children!r})"
