import sys
import tracemalloc
from time import perf_counter
import threading
from lattix import Lattix, SlimmedLattix


# =====
class Lattix_Normal:
   def __init__(self, lazy=False, safety_level=0):
      self._lazy_create = lazy
      self._store = {}
      self._sep = '/'
      self._ts_level = safety_level
      self._lock = threading.Lock() if safety_level == 1 else None
      self._rlock = threading.RLock() if safety_level == 2 else None


class Lattix_Slotted:
   __slots__ = ("_store", "_lazy_create", "_ts_level", "_lock", "_rlock", "_sep")
   def __init__(self, lazy=False, safety_level=0):
      self._lazy_create = lazy
      self._store = {}
      self._sep = '/'
      self._ts_level = safety_level
      self._lock = threading.Lock() if safety_level == 1 else None
      self._rlock = threading.RLock() if safety_level == 2 else None

def memory_usage(obj):
   """遞迴計算總記憶體（物件 + 子物件）"""
   seen = set()
   def sizeof(o):
      if id(o) in seen:
         return 0
      seen.add(id(o))
      size = sys.getsizeof(o)
      if isinstance(o, dict):
         size += sum(sizeof(k) + sizeof(v) for k, v in o.items())
      elif isinstance(o, (list, tuple, set)):
         size += sum(sizeof(i) for i in o)
      return size
   return sizeof(obj)

def test_mass(cls, count=100_000):
   tracemalloc.start()
   t0 = perf_counter()
   objs = [cls() for _ in range(count)]
   t1 = perf_counter()
   current, peak = tracemalloc.get_traced_memory()
   tracemalloc.stop()
   del objs
   return (peak / 1024 / 1024, t1 - t0)

if __name__ == "__main__":
   # ===== 單一實例測試 =====
   print("=== 單一實例記憶體 ===")
   normal = Lattix_Normal()
   slotted = Lattix_Slotted()
   real = Lattix()
   slimmed = SlimmedLattix()
   real.test_1 = {"key": "value"}
   slimmed.test_1 = {"key": "value"}

   print(real.__slots__)
   print(slimmed.__slots__)

   print(f"Normal base size: {sys.getsizeof(normal)} bytes")
   print(f"Slotted base size: {sys.getsizeof(slotted)} bytes")
   print(f"Real base size: {sys.getsizeof(real)} bytes")
   print(f"Slimmed base size: {sys.getsizeof(slimmed)} bytes")
   print(f"Normal total (with store): {memory_usage(normal)} bytes")
   print(f"Slotted total (with store): {memory_usage(slotted)} bytes")
   print(f"Real total (with store): {memory_usage(real)} bytes")
   print(f"Slimmed total (with store): {memory_usage(slimmed)} bytes")
   print()

   # ===== 大量實例測試 =====
   print("=== 大量實例建立測試 (100,000) ===")
   for name, cls in [("Normal", Lattix_Normal), ("Slotted", Lattix_Slotted), ("Real", Lattix), ("Slimmed", SlimmedLattix)]:
      mem, sec = test_mass(cls)
      print(f"{name:<8} → {mem:.2f} MB, 建立時間 {sec:.3f} 秒")