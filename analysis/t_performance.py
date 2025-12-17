from collections.abc import Iterable
from lattix import Lattix

# d = Lattix({
#    "a": {
#       "b": {
#          # "c": {
#          #    "d": list(range(1000))
#          # }, 
#       # "e": list(range(10000))
#          "c": {
#             "d": {
#                "e": "e"
#             }
#          }
#       }
#    }
# }, lazy=True)
d1 = Lattix({'foo': [{'bar': 'baz'}, {'qux': 'quxx'}]})


import time
from copy import deepcopy
def time_performance():
   
   start = time.perf_counter()
   for _ in range(10):
      d.clone(deep=True)
   end = time.perf_counter()
   print(f"clone: {end - start:.6f}s")
   
   start = time.perf_counter()
   for _ in range(10):
      deepcopy(d)
   end = time.perf_counter()
   print(f"deepcopy: {end - start:.6f}s")

import cProfile
def code_perfornamce():
   # d = Lattix({f"k{i}": {"v": i} for i in range(1000)})
   cProfile.run("d.clone(deep=True)", sort="tottime")
   cProfile.run("deepcopy(d)", sort="tottime")

if __name__ == "__main__":
   # time_performance()
   # code_perfornamce()

   print(d1)

   # d._new_store = {}
   # print(d.__dict__)
   # d.new_store.test1 = 3
   # d._new_store.test1 = 3
   # print(d.__dict__)
   # print(d.__dir__())
   # print(hasattr(d, "_new_store"))
   # d["_new_store"] = 3
   # print(type(d))
   # import inspect
   # for name, value in inspect.getmembers(d):
   #    print(f"{name}: {value}")
   # print("---------")
   # print(d.__dict__)
   # print(d["_new_store"])
   # print(d._new_store)
   # p = Lattix()
   # p["x"] = {"y": {"z": 1}}
   # print(p.x.y)
   # print(p)
   # import sys
   # print(sys.getsizeof(Lattix()))
   # print(sys.getsizeof(dict()))

   # d1 = Lattix({"a": 0, "b": 1, "c": 2})
   # d2 = Lattix({"c": 20, "d": 30})
   # dd1 = d1.to_dict()
   # dd2 = d2.to_dict()
   # def op(a, b):
   #    try:
   #       print(f"&: {a & b}")
   #    except:
   #       pass
   #    try:
   #       print(f"|: {a | b}")
   #    except:
   #       pass
   #    try:
   #       print(f"-: {a - b}")
   #    except:
   #       pass
   #    try:
   #       print(f"^: {a ^ b}")
   #    except:
   #       pass
   # # op(dd1, dd2)
   # # op(d1, d2)

   # # print({**d1, **d2}, type({**d1, **d2}))
   # # print(Lattix({**d1, **d2}))
   # a = Lattix({"x": {"y": {"z": 1}}})
   # b = {"x": {"y": {"w": 2}}}
   # # print(a)
   # # print(b)
   # # a.merge(b)
   # # print(a)
   # # d1 = Lattix({"a": 1, "b": 2, "c": 3})
   # # d2 = Lattix({"b": 20, "c": 30, "d": 40})
   # # print(d1.join(d2, how="inner"))
   # # print(d1.join(d2, how="left"))
   # # print(d1.join(d2, how="right"))
   # # print(d1.join(d2, how="outer"))
   # # print(d1.or_(d2))
   # # print(d.to_records())

   # # print(d1)
   # # d1 |= d2
   # # print(d1)
   # # new = Lattix(d1)
   # # print(d1, id(d1))
   # # print(new, id(new))

   pass