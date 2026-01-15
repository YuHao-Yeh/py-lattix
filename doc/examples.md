# *Lattix* by Example

This guide provides detailed code snippets and common patterns for using Lattix in various scenarios, from configuration management to data science pipelines.

## Table of Contents
- [*Lattix* by Example](#lattix-by-example)
  - [Table of Contents](#table-of-contents)
  - [1. Basics](#1-basics)
    - [Specifying Node Keys](#specifying-node-keys)
    - [Feeding Data](#feeding-data)
    - [Argument Order](#argument-order)
    - [Access Styles](#access-styles)
  - [2. Tree \& Path Logic](#2-tree--path-logic)
    - [Lazy Creation](#lazy-creation)
    - [Custom Path Separators](#custom-path-separators)
  - [3. Deep Merging \& Logic Ops](#3-deep-merging--logic-ops)
    - [SQL-style Joins](#sql-style-joins)
  - [4. Advanced Thread Safety](#4-advanced-thread-safety)
    - [Lock Inheritance](#lock-inheritance)
  - [5. Data Science Integrations](#5-data-science-integrations)
  - [6. Enhanced Serialization](#6-enhanced-serialization)
    - [High-Fidelity YAML](#high-fidelity-yaml)
  - [7. Leaf Manipulation](#7-leaf-manipulation)
  - [8. Hierarchy \& Lifecycle Management](#8-hierarchy--lifecycle-management)
    - [Detaching and Attaching](#detaching-and-attaching)
    - [Transplanting](#transplanting)
    - [Tree Hygiene: `purge()`](#tree-hygiene-purge)
    - [Summary of Hierarchy Methods](#summary-of-hierarchy-methods)
  - [9. Dictionary Compatibility](#9-dictionary-compatibility)
    - [Basic Methods](#basic-methods)
    - [Iteration](#iteration)
    - [Type Hinting Support](#type-hinting-support)
  - [10. Production Patterns](#10-production-patterns)
    - [Load and Freeze](#load-and-freeze)
    - [Flattening](#flattening)
    - [Sorting](#sorting)
    - [Summary of Unique Lattix Functions](#summary-of-unique-lattix-functions)

---

## 1. Basics

### Specifying Node Keys
Every Lattix node has an internal `key`. By default, a root node has an empty string as its key.

``` python
from lattix import Lattix

# A root node with a specific name
ltx = Lattix(key="root_node")
print(ltx)
# Output: Lattix(key='root_node', {})

# A default root node
default_ltx = Lattix()
print(default_ltx)
# Output: Lattix(key='', {})
```

### Feeding Data
Lattix can be initialized using  `dictionaries`, `keyword arguments`, or an `iterable of pairs`

```python
# 1. From a dictionary
# (Nested dicts are automatically promoted to Lattix nodes)
d1 = Lattix({"foo": 1, "bar": {"baz": 2}}, key='d1')
print(d1)
# Output: Lattix(key='d1', {'foo': 1, 'bar': Lattix(key='bar', {'baz': 2})})

# 2. From keyword arguments (kwargs)
d2 = Lattix(user="admin", level=10, key='info')
print(d2)
# Output: Lattix(key='info', {'user': 'admin', 'level': 10})

# 3. From an iterable of pairs
d3 = Lattix([("host", "localhost"), ("port", 5432)], key='config')
print(d3)
# Output: Lattix(key='config', {'host': 'localhost', 'port': 5432})
```

### Argument Order
The positional data (the dictionary or iterables) must come first, the key and other configuratioon flags should be passed as keyword arguments after data.

```python
# ❌ This causes a SyntaxError:
d4 = Lattix(key="my_node", {"foo": "bar"}) 
# SyntaxError: positional argument follows keyword argument

# ✅ This is correct:
d4 = Lattix({"foo": "bar"}, key="my_node")
```


### Access Styles
Lattix supports three ways to get and set data, giving you flexibility for different coding scenarios.

```python
d = Lattix({"database": {"host": "localhost"}}, lazy_create=True)

# 1. Dot Access
# Best for: Readability when the keys are known.
print(d.database.host) 
# Output: 'localhost'

# 2. Key Access
# Best for: Keys that aren't valid identifiers (e.g., "User Name") or variables.
print(d["database"])
# Output: Lattix(key='database', {'host': 'localhost'})

# 3. Path Access
# Best for: Accessing deep values using a single string.
print(d["database/host"]) 
# Output: 'localhost'
```

If the Lattix node contains in an iterable items (like list or tuple), you can still access them through:

```python
d = Lattix({"database": ["host", "timeout", {"port": {80: "HTTP", 443: "HTTPS"}}]})

print(d.database[2])
# Output: Lattix(key='2', {'port': Lattix(key='port', {80: 'HTTP', 443: 'HTTPS'}}

print(d.database[2].port)
# Output: Lattix(key='port', {80: 'HTTP', 443: 'HTTPS'}
```

---

## 2. Tree & Path Logic

### Lazy Creation
If you are tired of building nested structure manually, `Lattix` can automatically build nested structures.You don't need to pre-define parent nodes before assigning values to deeply nested children.

```python
conf = Lattix(lazy_create=True)

# Assigning to a deep path that doesn't exist yet
conf.logs.levels.critical.file = "error.log"

# It works with path-style assignment too
conf["database/settings/port"] = 5432

print(conf.to_dict())
# Output: {'logs': {'levels': {'critical': {'file': 'error.log'}}}, 'database': {'settings': {'port': 5432}}}
```

By default, `lazy_create` is `False`. Attempting to access or assign to a non-existent path will raise a Lattix-specific error.

```python
conf = Lattix(lazy_create=False)

# 1. Attribute-style access error
conf.logs.levels.file = "error.log"
# AttributeNotFoundError: No such attribute: 'logs'. 
# Initialize with `lazy_create=True` to enable dynamic attribute creation.

# 2. Path-style access error
conf["database/port"] = 5432
# PathNotFoundError: Missing key 'database' in path 'database/port'
```

### Custom Path Separators
If your data keys naturally contain slashes (like URLs or file paths), the default `/` separator might cause conflicts. You can change the separator to any string.

```python
# Useful for handling filesystem-like keys or scoped strings
d = Lattix(sep=":", lazy_create=True)

# Accessing using the custom colon separator
d["usr:local:bin"] = "executable"

# Dot-access remains unaffected and is always available
print(d.usr.local.bin)
# Output: 'executable'

print(d.sep)
# Output: ':'
```

---

## 3. Deep Merging & Logic Ops
Lattix treats mapping keys like **Sets**, but applies the logic **recursively** down the entire tree.

```python
default_cfg = Lattix({
    "server": {"port": 80, "timeout": 30},
    "debug": False
})

env_cfg = Lattix({
    "server": {"port": 8080},
    "debug": True,
    "tags": ["prod"]
})

# Union (|): Deep merge (Right-hand values overwrite left-hand values)
merged = default_cfg | env_cfg
# Result: server.port=8080, server.timeout=30, debug=True, tags=['prod']

# Intersection (&): Keeps only keys present in BOTH
common = default_cfg & env_cfg
# Result: server.port=8080, server.timeout=30, debug=True 
# (Note: values are taken from the right-hand side)

# Difference (-): Keys in the first node that are NOT in the second
unique = env_cfg - default_cfg
# Result: tags=['prod']

# Symmetric Difference (^): Keys present in one node or the other, but not both
diff = default_cfg ^ env_cfg
# Result: tags=['prod']
```

### SQL-style Joins
Joins are useful for combining two hierarchical structures based on shared keys, allowing you to choose how to handle missing data.

```python
users = Lattix({"001": {"name": "Alice"}, "002": {"name": "Bob"}})
scores = Lattix({"001": {"score": 95}, "003": {"score": 88}})

# Inner Join: Keeps only keys present in both Lattix instances.
# The 'merge' parameter defines how values are combined (default is a tuple).
result = users.join(scores, how="inner", merge="tuple")

print(result.to_dict())
# Output: {'001': {'name': 'Alice', 'score': 95}}

# Left Join: Keeps all keys from 'users', filling missing 'scores' with None.
left_res = users.join(scores, how="left")
# Output: {'001': {'name': 'Alice', 'score': 95}, '002': {'name': 'Bob', 'score': None}}
```

---

## 4. Advanced Thread Safety

### Lock Inheritance
Lattix allows an entire hierarchy to share a single `RLock`. When you lock any node in the tree, you are effectively locking the entire structure. This prevents race conditions where one thread is modifying `tree.a` while another is reading `tree.a.b.c`.

```python
import threading

# enable_lock=True creates an RLock at the root
root = Lattix(enable_lock=True, lazy_create=True)

def background_worker(node):
    # This acquires the lock shared by the entire tree
    with node:
        print(f"Worker locking subtree at: {node.key}")
        node.status = "busy"
        # ... do thread-safe work ...
        node.status = "idle"

# Even though we pass 'root.service', it uses the same lock as 'root'
thread = threading.Thread(target=background_worker, args=(root.service,))
thread.start()
# Output: 'Worker locking subtree at: service'

# This will block until the worker thread releases the lock
with root:
    print(f"Main thread access status: {root.service.status}")
# Output: 'Main thread access status: idle'
```

---

## 5. Data Science Integrations
Lattix is "Adapter-Aware." It doesn't require these libraries to be installed, but if they are, it provides seamless conversion during serialization.

```python
import numpy as np
import pandas as pd
import torch

d = Lattix(lazy_create=True)
d.metrics.accuracy = np.float32(0.98)
d.metrics.history = np.array([0.1, 0.5, 0.9])
d.data.frame = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
d.model.weights = torch.tensor([1.0, -1.0])

# 1. Standard dictionary conversion (NumPy arrays become lists, DataFrames become dicts)
print(d.to_dict())  # Output: {'metrics': {'accuracy': np.float32(0.98), ...}

# 2. High-performance JSON via orjson
d_json = d.orjson() # Result: b'{"metrics":{"accuracy":"0.98"}, ...}'

# 3. Compact binary storage via Msgpack
binary_blob = d.msgpack()
```

---

## 6. Enhanced Serialization

### High-Fidelity YAML
Preserve types that standard YAML libraries usually lose.

```python
from decimal import Decimal
from pathlib import Path

d = Lattix({
    "settings": {
        "work_dir": Path("/usr/local/bin"),
        "pi_approx": Decimal("3.14159"),
        "tags": {"prod", "aws"}
    }
})

# Use enhanced=True to preserve these types via custom tags
yaml_data = d.yaml(enhanced=True)
print(yaml_data)
# Output:
# settings:
#   work_dir: !path '/usr/local/bin'
#   pi_approx: !decimal '3.14159'
#   tags: !set [aws, prod]

# Load it back perfectly
new_d = Lattix.from_yaml(yaml_data, enhanced=True)
assert isinstance(new_d.settings.work_dir, Path)
```

---

## 7. Leaf Manipulation
Perform operations on the actual data "leaves" without touching the tree structure.

```Python
d = Lattix({"scores": {"math": 90, "science": 85}}, key='root')

# 1. Iterate over all leaf paths
for path in d.leaf_keys():
    print(path) 
# Output:
#   'scores/math'
#   'scores/science'

# 2. Batch transform every leaf value
d.map_leaves(lambda x: x + 5 if isinstance(x, int) else x)
# Now math=95, science=90

# 3. Filter the tree based on values
d.filter_leaves(lambda x: x != "std_01")
# Result: Only {'scores': {'math': 95}} remains
```

---

## 8. Hierarchy & Lifecycle Management

### Detaching and Attaching

```Python
root = Lattix({"a": {"b": 1}})
node_b = root.a

# Remove 'b' from 'root' and make it its own root
node_b.detach()

# Re-attach it to a different tree
new_tree = Lattix(key="new")
node_b.attach(new_tree)
```

### Transplanting

```Python
source = Lattix({"temp": {"data": 100}})
dest = Lattix({"prod": {}})

# Move and rename 'temp' to 'prod.active' in one step
source.temp.transplant(dest.prod, key="active")

print(dest.prod.active.data) # Output: 100
print("temp/data" in source) # Output: False
```

### Tree Hygiene: `purge()`
Remove all branches that lead to no data.

```Python
conf = Lattix(lazy_create=True)

# 1. Accidental creation of an empty branch
_ = conf.temporary.unused.path 

# 2. Assigning actual data
conf.settings.port = 8080

print(conf.to_dict())
# Output: {'temporary': {'unused': {'path': {}}}, 'settings': {'port': 8080}}

# 3. Clean up empty branches
conf.purge()

print(conf.to_dict())
# Output: {'settings': {'port': 8080}}
# The 'temporary' branch was deleted because it had no leaf values.
```


### Summary of Hierarchy Methods

| Method | Structural Effect | Threading Effect |
| :--- | :--- | :--- |
| **`detach()`** | Clears `parent`. Removes from old parent's `children`. | Node gets a new independent lock context. |
| **`attach()`** | Sets `parent`. Adds to new parent's `children`. | Node adopts the parent's lock. |
| **`transplant()`**| Moves node from Parent A to Parent B. Optional rename. | Node migrates from Lock A to Lock B. |
| **`purge`**| Prunes empty branches. | No lock change (cleanup only). |

---

## 9. Dictionary Compatibility

### Basic Methods

```python
d = Lattix(a=1, b=2)

# 1. Length and Membership
print(len(d))               # Output: 2
print("a" in d)             # Output: True 
print(list(d.keys()))       # Output: ['a', 'b']

# 2. Standard Retrieval
print(d.get("missing", 0))  # Output: 0
print(d.setdefault("c", 3)) # Output: 3

# 3. Deletion and Popping
val = d.pop("a")           # val is 1
del d["b"]

# 4. Bulk Updates
d.update({"e": 5, "f": 6})
print(d)                   # Output: {'c': 3, 'e': 5, 'f': 6}
```

### Iteration
Lattix supports all standard iteration patterns.
```Python
d = Lattix({"x": 10, "y": 20})

# Iterate over keys
for key in d:
    print(key)
# Output: 
#   'x'
#   'y'

# Iterate over values
for val in d.values():
    print(val)
# Output:
#   10
#   20

# Iterate over items
for key, val in d.items():
    print(f"{key} -> {val}")
# Output:
#   'x' -> 10
#   'y' -> 30
```

### Type Hinting Support
Lattix supports PEP 585 style generic type hints, making it friendly for static analyzers like Mypy.

```Python
from lattix import Lattix

def process_config(cfg: Lattix[str, int]):
    # Your IDE knows cfg has string keys and integer values
    pass
```
---

## 10. Production Patterns

### Load and Freeze
Load your configuration, then protect it from accidental runtime modification.

```python
conf = Lattix.from_yaml("config.yaml")
conf.freeze() # Now read-only

conf.api_key = "new"  # Raises ModificationDeniedError
```

### Flattening
Convert a deep tree into a flat dictionary for use with `.env` files or system shells.

```python
conf = Lattix({"api": {"v1": {"key": "secret"}}})

flat = conf.flatten(sep="__") # Result: {'api__v1__key': 'secret'}

# Reverse it
reconstructed = Lattix.unflatten(flat, sep="__")
```

### Sorting
Clean up your structure for consistent logging or diffing.

```python
d = Lattix({"z": 1, "a": 2, "m": {"y": 10, "x": 20}})

d.sort_by_key(recursive=True)
# Result: a=2, m={x=20, y=10}, z=1
```

---

### Summary of Unique Lattix Functions

| Function | Description |
| :--- | :--- |
| `get_path()` | Access nested data using a path string. |
| `leaf_keys()` | Generator for all deep leaf paths. |
| `map_leaves()` | Batch transform data values. |
| `filter_leaves()` | Prune tree based on values. |
| `freeze()` | Make the entire structure immutable. |
| `join()` | SQL-style joining of two trees. |
| `purge()` | Clean up empty nodes created by lazy access. |

--- 
