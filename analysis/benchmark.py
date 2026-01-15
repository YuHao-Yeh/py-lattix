# type: ignore
import os
import sys
import timeit

sys.path.insert(0, os.path.abspath("src"))

# ======================================================
# Import libraries
# ======================================================
try:
    from lattix import Lattix
except ImportError:
    Lattix = None

try:
    from easydict import EasyDict
except ImportError:
    EasyDict = None

try:
    from addict import Dict as Addict
except ImportError:
    Addict = None

try:
    from box import Box
except ImportError:
    Box = None

try:
    from treedict import TreeDict
except ImportError:
    TreeDict = None

try:
    from dotted_dict import DottedDict
except ImportError:
    DottedDict = None

try:
    from treedict import TreeDict
except ImportError:
    TreeDict = None

try:
    from attrs import define, field

    @define
    class AttrsL3:
        level3: int = 100

    @define
    class AttrsL2:
        level2: AttrsL3 = field(factory=AttrsL3)

    @define
    class AttrsL1:
        level1: AttrsL2 = field(factory=AttrsL2)

except ImportError:
    define = None


# ======================================================
# Define test data
# ======================================================
ITER_N = 100_000
raw_data = {"level1": {"level2": {"level3": 100}}}


# ======================================================
# Performance test function
# ======================================================
def run(stmt, setup="pass", globals=None):
    try:
        # Use globals=globals() to solve the NameError
        t = timeit.Timer(stmt, setup=setup, globals=globals)
        res = t.timeit(number=ITER_N)
        return res
    except Exception:
        return None


def format_res(val):
    return f"{val:.5f}" if val is not None else "N/A"


# ======================================================
# Instances and libraries setup
# ======================================================
instances = {}
if True:
    instances["dict"] = {"level1": {"level2": {"level3": 100}}}
if Lattix:
    instances["Lattix"] = Lattix(raw_data)
if EasyDict:
    instances["EasyDict"] = EasyDict(raw_data)
if Addict:
    instances["Addict"] = Addict(raw_data)
if Box:
    instances["Box"] = Box(raw_data)
if TreeDict:
    instances["TreeDict"] = TreeDict(raw_data)
if AttrsL1:
    instances["Attrs"] = AttrsL1(level1=AttrsL2(level2=AttrsL3(level3=100)))
# if bidict:
#     instances["Bidict"] = bidict(raw_data)
if DottedDict:
    instances["DottedDict"] = DottedDict(raw_data)

libs = [
    # (class name, init statement, support key, support dot)
    ("dict", "dict(raw_data)", True, False),
    ("Lattix", "Lattix(raw_data, lazy_create=True)", True, True),
    ("EasyDict", "EasyDict(raw_data)", True, True),
    ("Addict", "Addict(raw_data)", True, True),
    ("Box", "Box(raw_data)", True, True),
    ("TreeDict", "TreeDict(raw_data)", True, False),
    ("Attrs", "AttrsL1(level1=AttrsL2(level2=AttrsL3(level3=100)))", False, True),
    # ("Bidict", "bidict(raw_data)", True,  False),
    ("DottedDict", "DottedDict(raw_data)", True, True),
]


if __name__ == "__main__":
    # ========== Headers ==========
    print(f"Python Ver.: {sys.version}")
    print(f"Epoch: {ITER_N}")
    print(
        f"{'Library':<12} | {'Init':<8} | {'Read(K)':<8} | {'Read(D)':<8} | {'Write(K)':<8} | {'Write(D)':<8}"
    )
    print("-" * 70)

    for name, init_stmt, support_key, support_dot in libs:
        if (name not in instances) and (name != "dict") and (name != "Attrs"):
            continue

        results = {
            "init": None,
            "read_k": None,
            "read_d": None,
            "write_k": None,
            "write_d": None,
        }

        # 1. Initiate
        results["init"] = run(init_stmt, globals=globals())

        obj = instances.get(name)
        setup_env = {"obj": obj}

        # 2. Nested Read (Key)
        if support_key and obj is not None:
            results["read_k"] = run(
                'obj["level1"]["level2"]["level3"]', globals=setup_env
            )

        # 3. Nested Read (Dot)
        if support_dot and obj is not None:
            results["read_d"] = run("obj.level1.level2.level3", globals=setup_env)

        # 4. Nested Write (Key)
        if support_key and obj is not None:
            results["write_k"] = run(
                'obj["level1"]["level2"]["level3"] = 200', globals=setup_env
            )

        # 5. Nested Write (Dot)
        if support_dot and obj is not None:
            results["write_d"] = run(
                "obj.level1.level2.level3 = 300", globals=setup_env
            )

        print(
            f"{name:<12} | "
            f"{format_res(results['init']):<8} | "
            f"{format_res(results['read_k']):<8} | "
            f"{format_res(results['read_d']):<8} | "
            f"{format_res(results['write_k']):<8} | "
            f"{format_res(results['write_d']):<8}"
        )
