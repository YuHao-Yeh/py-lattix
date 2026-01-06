This is a professional **README.md** tailored specifically to the features and architecture of your **Lattix** library. 

---

# Lattix

[![PyPI version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg)](https://pypi.org/project/py-lattix/)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-)]
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Lattix** is a high-performance, hierarchical, and thread-safe mapping library for Python. It combines the flexibility of a dictionary with the power of tree-like structures, offering dot-access, path-traversal, and seamless integration with the modern Python data stack (NumPy, Pandas, PyTorch).

## Key Features

- **Hierarchical Access**: Use dot-notation (`d.user.profile.id`) or path-strings (`d["user/profile/id"]`) with configurable separators.
- **Lazy Creation**: Automatically build nested structures on the fly with `lazy_create=True`.
- **Thread-Safe Inheritance**: Advanced lock-sharing mechanism where children nodes inherit their parent's `RLock`, ensuring consistent thread safety across subtrees.
- **Set-Like Logic**: Perform deep merges and intersections using standard operators: `&` (intersection), `|` (union/merge), `-` (difference), and `^` (symmetric difference).
- **Data-Science Ready**: Built-in adapters for **NumPy**, **Pandas**, **PyTorch**, and **Xarray**. No hard dependencies required.
- **Enhanced Serialization**: Native support for JSON, YAML (enhanced with custom types), Msgpack, and Orjson.
- **Memory Efficient**: Heavily optimized using `__slots__` to keep memory overhead at a minimum.

---

## Installation

```bash
pip install py-lattix
```

---

## Quick Start

### Basic Usage & Path Access
```python
from lattix import Lattix

# Initialize with data or kwargs
d = Lattix(meta={"version": "1.0"}, lazy_create=True)

# Path-style access
d["app/settings/theme"] = "dark"

# Dot-style access (even for paths created above)
print(d.app.settings.theme)  # Output: "dark"

# Lazy creation
d.database.connection.timeout = 30
print(d.to_dict())
# {'meta': {'version': '1.0'}, 'app': {'settings': {'theme': 'dark'}}, 'database': {'connection': {'timeout': 30}}}
```

### Logical Operations (Deep Merging)
Lattix implements logical operators to make combining configurations effortless.

```python
conf_default = Lattix({"api": {"host": "localhost", "port": 8080}})
conf_user = Lattix({"api": {"port": 9000}, "debug": True})

# Deep Merge (Union)
final_conf = conf_default | conf_user

print(final_conf.api.port) # 9000 (overwritten)
print(final_conf.api.host) # localhost (preserved)
```

### SQL-style Joins
```python
d1 = Lattix({"a": 1, "b": 2})
d2 = Lattix({"b": 20, "c": 30})

# Inner join: keys existing in both
res = d1.join(d2, how="inner")
# Lattix({'b': (2, 20)})
```

---

## Integrations (Adapters)

Lattix is designed to live inside data pipelines. It automatically handles complex objects during serialization:

```python
import numpy as np
import pandas as pd

d = Lattix(lazy_create=True)
d.results = np.array([1, 2, 3])
d.df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})

# Formatted pretty print
print(d.pprint(style="default"))

# Convert entire tree to JSON-serializable dict
# NumPy arrays become lists, Pandas DataFrames become nested dicts
clean_data = d.to_dict()
```

---

## Thread Safety

Lattix solves the "Subtree Locking" problem. When you enable locking on a Lattix node, all children nodes created from it or attached to it share the same recursive lock.

```python
d = Lattix(enable_lock=True)

with d:  # Acquires the lock for the entire tree
    d.a.b.c = 100
    # No other thread can modify d or any of its children during this block
```

---

## Serialization

Lattix supports multiple formats out of the box.

- **JSON**: `d.json(indent=2)`
- **YAML**: `d.yaml(enhanced=True)` (supports `Decimal`, `datetime`, `set`, and `Path` objects natively)
- **Msgpack**: `d.msgpack()`
- **Orjson**: `d.orjson()`

---

## Project Structure

```text
lattix/
├── _core/           # Internal logic (Mixins, Base Nodes, Metaclasses)
├── adapters/        # Third-party integrations (NumPy, Pandas, etc.)
├── structures/      # Primary Lattix mapping implementations
├── serialization/   # YAML/JSON/Msgpack specialized logic
└── utils/           # Shared types, common helpers, and exceptions
```

---

## Testing

We maintain a high test coverage. To run the suite:

```bash
python -m pytest tests/
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an issue on GitHub.