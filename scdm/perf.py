"""P354/R71: 性能基线记录 —— 进程内存峰值与交互路径耗时（可复算）。

Two honest measurements, no invented thresholds:

* `peak_memory_mb()` reads the process PEAK working set on Windows through
  ctypes (GetProcessMemoryInfo).  tracemalloc only sees Python objects, and most
  of a CAD workload lives in C++, so the OS counter is the meaningful one; the
  tracemalloc fallback is reported as such.
* `measure(label, fn)` times a callable and records the peak memory around it,
  so a record is (label, seconds, per-call seconds, peak MB, repeat) - everything
  needed to recompute the number on another machine.

This round only RECORDS (the plan says so): the assertions in the tests are
generous regression guards, and the numbers live in `docs/PERF_BASELINE.json`.
"""
from __future__ import annotations

import json
import time
import tracemalloc
from typing import Any, Callable, Dict, List, Optional


def peak_memory_mb() -> float:
    """Process peak working set in MB (Windows); 0.0 when the counter is absent.

    Two ctypes details matter and both were measured: the pseudo-handle is
    (HANDLE)-1 so an explicit restype is needed (otherwise it is truncated to 32
    bits), and the query needs argtypes or it returns 0 without any error.  When
    the counter is unavailable this returns 0.0 - the caller records None - so a
    Python-only number can never masquerade as the process peak.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        handle = kernel32.GetCurrentProcess()
        fn = kernel32.K32GetProcessMemoryInfo
        fn.argtypes = [ctypes.c_void_p,
                       ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        fn.restype = wintypes.BOOL
        if fn(handle, ctypes.byref(counters), counters.cb):
            return float(counters.PeakWorkingSetSize) / (1024.0 * 1024.0)
    except Exception:
        pass
    return 0.0


def current_memory_mb() -> float:
    """Process CURRENT working set in MB (Windows), 0.0 when unavailable (R98).

    peak_memory_mb() answers "how big did this get"; this one answers "how big is
    it now", which is what a RELEASE has to move.  Same ctypes contract, same
    field (WorkingSetSize instead of PeakWorkingSetSize).
    """
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        handle = kernel32.GetCurrentProcess()
        fn = kernel32.K32GetProcessMemoryInfo
        fn.argtypes = [ctypes.c_void_p,
                       ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        fn.restype = wintypes.BOOL
        if fn(handle, ctypes.byref(counters), counters.cb):
            return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
    except Exception:
        pass
    return 0.0

def python_peak_mb() -> float:
    """Python-only allocation peak while tracing is ACTIVE, else 0.0.

    It deliberately does NOT start the tracer: tracemalloc slows every Python
    allocation, and leaving it on made the next test in the same process six
    times slower (measured: the official sample load went from 4 s to 26 s).
    measure() owns the start/stop window instead.
    """
    try:
        if not tracemalloc.is_tracing():
            return 0.0
        _cur, peak = tracemalloc.get_traced_memory()
        return float(peak) / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def _safe(value: Any) -> Any:
    """JSON-safe view of a measurement result (never a raw OCCT object)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    return type(value).__name__


def measure(label: str, fn: Callable[[], Any], repeat: int = 1,
            summary: Optional[Callable[[Any], Any]] = None) -> Dict[str, Any]:
    """Run fn repeat times and record time + peak memory.

    summary turns the last result into a JSON-safe note (counts, sizes); the raw
    result is never stored - it can be a live OCCT shape, and the first draft
    tried to dump one into the baseline and json refused.
    """
    n = max(1, int(repeat))
    tracemalloc.start()          # so the Python peak covers the FIRST record too
    results: List[Any] = []
    t0 = time.perf_counter()
    for _ in range(n):
        results.append(fn())
    dt = time.perf_counter() - t0
    py_peak = python_peak_mb()
    tracemalloc.stop()           # never leave the tracer running (rule 85)
    try:
        note = _safe(summary(results[-1]) if summary is not None
                     else results[-1])
    except Exception as exc:
        note = "summary failed: %s" % type(exc).__name__
    peak = peak_memory_mb()
    return {"label": label, "seconds": dt, "per_call": dt / n, "repeat": n,
            # None means "the OS counter was unavailable" - never a fake 0 MB
            "peak_mb": (peak if peak > 0 else None),
            "python_peak_mb": py_peak, "result": note}


def write_baseline(path: str, records: List[Dict[str, Any]],
                   note: str = "") -> str:
    payload = {"note": note, "machine": _machine(), "records": records}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def read_baseline(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _machine() -> Dict[str, Any]:
    import platform
    import sys
    return {"platform": platform.platform(), "python": sys.version.split()[0],
            "processor": platform.processor() or platform.machine()}


def table(records: List[Dict[str, Any]]) -> str:
    """One line per record, for a terminal or a round record."""
    lines = ["| label | per call (s) | repeat | peak MB | python peak MB |",
             "|---|---|---|---|---|"]
    for r in records or ():
        peak = r.get("peak_mb")
        lines.append("| %s | %.4f | %d | %s | %.1f |"
                     % (r.get("label", ""), float(r.get("per_call", 0.0)),
                        int(r.get("repeat", 0)),
                        ("%.1f" % float(peak)) if peak is not None else "n/a",
                        float(r.get("python_peak_mb") or 0.0)))
    return "\n".join(lines)
