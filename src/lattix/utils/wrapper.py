from functools import wraps
import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable
    from .types import DictType, ListType, TypeType


class _ThreadSafetyManager:
    """
    Thread-safe decorator (inline lock binding version)
    - level = 0 → no lock
    - level = 1 → use _lock (threading.Lock)
    - level = 2 → use _rlock (threading.RLock)
    """
    @staticmethod
    def level(level: int = 1):
        def decorator(method: Callable[..., Any]) -> Any:
            @wraps(method)
            def wrapper(self: TypeType[Any], *args: Any, **kwargs: Any):
                if level == 0:
                    return method(self, *args, **kwargs)
                lock_attr = "_rlock" if level == 2 else "_lock"
                # lock = getattr(self, lock_attr, None)
                lock = object.__getattribute__(self, lock_attr)
                if lock is None:
                    return method(self, *args, **kwargs)
                with lock:
                    return method(self, *args, **kwargs)
            wrapper._thread_safe_level = level  # type: ignore[attr-defined]
            return wrapper
        return decorator

    @staticmethod
    def apply(levels: DictType[int, ListType[str]]):
        def decorator(cls: TypeType[Any]):
            for level, names in levels.items():
                if level == 0:
                    continue
                for name in names:
                    if hasattr(cls, name):
                        func = getattr(cls, name)
                        # func = object.__getattribute__(cls, name)
                        if func and (inspect.isfunction(func) or inspect.ismethod(func)):
                            type.__setattr__(cls, name, _ThreadSafetyManager.level(level)(func))
            return cls
        return decorator