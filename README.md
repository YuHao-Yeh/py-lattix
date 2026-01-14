# Lattix

<!-- GitHub & CI Status -->
[![Tests](https://github.com/YuHao-Yeh/py-lattix/actions/workflows/test.yml/badge.svg)](https://github.com/YuHao-Yeh/py-lattix/actions)
[![Coverage Status](https://coveralls.io/repos/github/YuHao-Yeh/py-lattix/badge.svg)](https://coveralls.io/github/YuHao-Yeh/py-lattix)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<!-- PyPI Metadata -->
[![PyPI Version](https://img.shields.io/pypi/v/py-lattix.svg)](https://pypi.org/project/py-lattix/)
[![PyPI Python Versions](https://img.shields.io/pypi/pyversions/py-lattix.svg)](https://pypi.org/project/py-lattix/)

<!-- Quality & Tooling -->
![mypy](https://img.shields.io/badge/mypy-strict-blue)
![ruff](https://img.shields.io/badge/lint-ruff-red)
![black](https://img.shields.io/badge/code%20style-black-000000)


**Lattix** is a high-performance, hierarchical mapping library designed for complex data pipelines and multi-threaded environments. It combines the flexibility of a dictionary with the power of tree-like structures, offering dot-access, path-traversal, and a unique **inherited locking mechanism** for atomic subtree operations.

```python
from lattix import Lattix

conf = Lattix(lazy_create=True)

conf.database.credentials.user = "admin"
conf["database/credentials/port"] = 5432

conf.database.credentials.to_dict()
# {'user': 'admin', 'port': 5432}
```
---

## Key Features

- **Hierarchical Access**: Use dot-notation (`d.user.profile.id`) or path-strings (`d["user/profile/id"]`) with configurable separators.
- **Lazy Creation**: Automatically build nested structures on the fly with `lazy_create=True`.
- **Thread-Safe Inheritance**: Advanced lock-sharing where children nodes inherit their parent's `RLock`, ensuring consistent synchronization across entire subtrees.
- **Immutability (Freeze)**: Protect your data from accidental changes in production using `d.freeze()`.
- **Set-Like Logic**: Perform deep merges, intersections, and differences using standard operators: `&`, `|`, `-`, and `^`.
- **Data-Science Ready**: Built-in, lazy-loading adapters for **NumPy**, **Pandas**, **PyTorch**, and **Xarray**. No hard dependencies required.
- **Enhanced Serialization**: Native support for high-fidelity YAML (preserving `Path`, `Decimal`, `datetime`), JSON, Msgpack, and Orjson.
- **First-class Typing**: Fully typed with Python generics and `.pyi` stubs for perfect autocompletion in VS Code and PyCharm.

---

## Installation

### 1. Install via PyPI (Recommended)
```bash
# Basic
pip install py-lattix

# With all adapters (NumPy, Pandas, etc.)
pip install "py-lattix[full]"
```
### 2. Install via Github:

```bash
# Basic
pip install git+https://github.com/YuHao-Yeh/py-lattix.git

# With all adapters (NumPy, Pandas, YAML support, etc.)
pip install "py-lattix[full] @ git+https://github.com/YuHao-Yeh/py-lattix.git"
```

### 3. Install from Source

```bash
# 1. Clone the repository
$ git clone https://github.com/YuHao-Yeh/py-lattix
$ cd py-lattix

# 2. Install in editable mode
pip install -e

# 3. (Optional) Install testing dependencies
pip install -e ".[test,full]"
```

---

## Quick Start

### Basic Usage & Path Access
```python
from lattix import Lattix

# Initialize with data or kwargs
conf = Lattix(meta={"version": "1.0"}, lazy_create=True, sep=":")

# Path-style access
conf["app:settings:theme"] = "dark"

# Dot-style access (even for paths created above)
print(conf.app.settings.theme)  # Output: "dark"

# Lazy creation
conf.database.connection.timeout = 30

# Convert entire tree back to a plain serializable dict
conf.to_dict()
# {'meta': {'version': '1.0'}, 'app': {'settings': {'theme': 'dark'}}, 'database': {'connection': {'timeout': 30}}}
```

## Inherited Thread Safety

Lattix solves the "Subtree Locking" problem. When a node is locked, all its children (present or future) share the same lock instance.

```python
import threading

tree = Lattix(enable_lock=True, lazy_create=True)

def update_config():
    with tree: # Acquires global lock for the whole tree
        tree.server.status = "upgrading"
        tree.server.port = 9000
        tree.server.last_check = "2026-01-10"
        # No other thread can modify 'tree' or any of its children 
        # until this block finishes.

threading.Thread(target=update_config).start()
```

### Production Safety: Freezing
Prevent accidental modifications to your configuration once it is loaded.

```python
conf = Lattix({"api": {"key": "secret"}})
conf.freeze()

conf.api.key = "new-key" 
# Raises: ModificationDeniedError
```

---

## Advanced Operations

### Logical Operations (Deep Merging)
```python
base = Lattix({"api": {"host": "localhost", "port": 8080}})
user = Lattix({"api": {"port": 9000}, "debug": True})

# Deep Union (Merge)
final = base | user
# Result: api.host=localhost (preserved), api.port=9000 (overwritten), debug=True

# Intersection (Common Keys)
common = base & user
# Result: api.port=9000 (overwritten)
```

### SQL-style Joins
```python
d1 = Lattix({"a": 1, "b": 2})
d2 = Lattix({"b": 20, "c": 30})

# Inner join: keys existing in both
res = d1.join(d2, how="inner")
# Result: Lattix({'b': (2, 20)})
```

### Data Science Integrations
Lattix recognizes complex types and handles them automatically during serialization.

```python
import numpy as np
import pandas as pd
import torch

d = Lattix(lazy_create=True)
d.array = np.array([1, 2, 3])
d.df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
d.tensor = torch.randn(3, 3)

# Serialization handles NumPy/Pandas/Torch -> Python conversion automatically
print(d.json())
```

### Enhanced YAML
Lattix preserves complex Python types in YAML that standard loaders usually break.

```python
from decimal import Decimal
from pathlib import Path

d = Lattix({"price": Decimal("19.99"), "path": Path("/usr/bin")})

# Export with custom YAML tags
yaml_out = d.yaml(enhanced=True)
# Output:
# price: !decimal '19.99'
# path: !path '/usr/bin'
```

---

## Diagnostics & Testing

Verify your environment and adapter availability via the CLI:

```bash
python -m lattix
```

Run internal doctests to verify library integrity:

```bash
python -m lattix --test
```

---

## Similar Projects

- [addict](https://github.com/mewwts/addict): Lightweight recursive dictionary with dot-access.
- [Easydict](https://github.com/XuehaiPan/TreeDict): A fast and full-featured dict-like tree container.
- [python-box](https://github.com/cdgriffith/Box): Robust dictionary wrapper with path and dot-access support.

## License

Lattix is released under the **BSD License**. See the [LICENSE](LICENSE) for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request or open an issue on GitHub.

We maintain a high test coverage. To run the suite:
1. Clone the repo: `git clone https://github.com/YuHao-Yeh/py-lattix`
2. Install dev dependencies: `pip install -e ".[test]"`
3. Run tests: `pytest`
4. Ensure typing is correct: `mypy src/lattix`
