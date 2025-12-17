#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Benchmark script for Lattix vs dict / defaultdict / JSON

測試內容：
1. 單層 key set/get
2. 多層巢狀 key set/get (dict["a"]["b"]["c"])
3. Lattix 路徑式 key ("a/b/c") set/get
4. 大量 insert/search 更新速度比較
5. JSON serialization/deserialization 測試
6. cProfile + pstats 分析 hot functions

結果以 Markdown 格式輸出，方便貼到 README / docs。
"""

import json
import random
import string
from collections import defaultdict
from timeit import timeit
from time import perf_counter
import cProfile
import pstats

# ✅ Import Lattix
try:
   from lattix import Lattix
except ImportError:
   # 若沒有 in-package，允許跑 repository 外部
   from lattix import Lattix


N = 100_000  # 測試資料量
PRINT_TOP = 15  # cProfile 印出 top N slowest


# ---------------------------------------------------------------------------
# 工具函數
# ---------------------------------------------------------------------------
def random_key(size=6):
    return ''.join(random.choices(string.ascii_lowercase, k=size))


def build_nested_dict(depth=5):
    """快速生成 nested dict，像 {'a': {'b': {...}}}"""
    root = {}
    d = root
    for i in range(depth):
        d[random_key()] = {}
        d = d[list(d.keys())[0]]
    return root


# ---------------------------------------------------------------------------
# 測試案例
# ---------------------------------------------------------------------------

def bench_single_layer():
   print("🔹 Benchmark: Single Layer Insert & Access")

   t_dict = timeit(
      "d['x'] = 1; _ = d['x']",
      setup="d={}",
      number=N,
   )

   t_dyna = timeit(
      "d['x'] = 1; _ = d['x']",
      setup="from lattix import Lattix; d=Lattix()",
      number=N,
   )

   print(f"dict:      {t_dict:.4f}s")
   print(f"Lattix:  {t_dyna:.4f}s")
   print()


def bench_nested_depth_access():
    print("🔹 Benchmark: Nested Access Depth (5)")

    # 建 dict
    nested = {"a": {"b": {"c": {"d": {"e": 123}}}}}
    dyna = Lattix({"a": {"b": {"c": {"d": {"e": 123}}}}})

    t_dict = timeit("_ = nested['a']['b']['c']['d']['e']", number=N, globals=locals())
    t_dyna = timeit("_ = dyna['a/b/c/d/e']", number=N, globals=locals())

    print(f"dict:      {t_dict:.4f}s")
    print(f"Lattix:  {t_dyna:.4f}s")
    print()


def bench_large_insert_and_get():
    print("🔹 Benchmark: Massive Insert + Get")

    # dict 測試
    plain = {}
    t0 = perf_counter()
    for i in range(N):
        plain[i] = i
        _ = plain[i]
    t_dict = perf_counter() - t0

    # Lattix 測試
    dyna = Lattix(lazy_create=True)
    t0 = perf_counter()
    for i in range(N):
        dyna[f"root/{i}"] = i
        _ = dyna[f"root/{i}"]
    t_dyna = perf_counter() - t0

    print(f"dict:       {t_dict:.4f}s")
    print(f"Lattix:   {t_dyna:.4f}s")
    print()


def bench_defaultdict():
    print("🔹 Benchmark: defaultdict")

    t_defaultdict = timeit(
        "d['x'].append(1); _ = d['x']",
        setup="from collections import defaultdict; d=defaultdict(list)",
        number=N,
    )

    t_dyna = timeit(
        "d['x'].append(1); _ = d['x']",
        setup="from lattix import Lattix; d=Lattix({'x': []}, lazy_create=True)",
        number=N,
    )

    print(f"defaultdict: {t_defaultdict:.4f}s")
    print(f"Lattix:    {t_dyna:.4f}s")
    print()


def bench_json_compare():
    print("🔹 Benchmark: JSON <-> Python 序列化 / 還原")

    data = {f"key{i}": random_key() for i in range(10_000)}

    t_dump = timeit("import json; json.dumps(data)", number=100, globals=locals())
    t_load = timeit("import json; json.loads(json.dumps(data))", number=100, globals=locals())

    print(f"json.dumps:  {t_dump:.4f}s")
    print(f"json.loads:  {t_load:.4f}s")
    print()


def profile_dyna():
    print("🔹 Profiling Lattix with cProfile")

    d = Lattix(lazy_create=True)

    def workload():
        for i in range(30_000):
            d[f"a/b/c/{i}"] = i
            _ = d[f"a/b/c/{i}"]

    profile = cProfile.Profile()
    profile.enable()
    workload()
    profile.disable()

    stats = pstats.Stats(profile).sort_stats("tottime")
    # stats.print_stats(PRINT_TOP)
    stats.print_stats()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n===== Lattix Benchmark =====\n")
    bench_single_layer()
    bench_nested_depth_access()
    bench_large_insert_and_get()
    bench_defaultdict()
    bench_json_compare()
    profile_dyna()
