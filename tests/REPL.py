from pprint import pprint
import inspect
import lattix

cls = lattix.Lattix

print("=== Lattix MRO ===")
for c in cls.__mro__:
    slots = getattr(c, "__slots__", None)
    has_dict = False
    # 判斷該類別的 instances 是否會有 __dict__
    if "__dict__" in (slots if isinstance(slots, (list, tuple)) else (slots or ())):
        has_dict = True
    # 也可檢查類別 dict 本身是否保有 __dict__ 屬性
    print(f"{c!r:60} | __slots__ = {slots!r:30} | has '__dict__' in slots? {has_dict}")

print("\n=== Check if any base is builtin heap type (like dict) ===")
for c in cls.__mro__:
    print(c, "is builtin type subclass of dict?", issubclass(c, dict) if inspect.isclass(c) else "n/a")

print("\n=== Show attrs related to __dict__ presence ===")
for c in cls.__mro__:
    print(c.__name__, "->", "has __dict__ attribute?", "__dict__" in c.__dict__)
