from contextlib import contextmanager
import ctypes
import logging
import os
import time


LOGGER_NAME = "mug.profile"


def get_profile_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [PROFILE] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger


def get_memory_mb() -> float | None:
    """
    Returns approximate process RSS/private working set in MB.

    On Windows, this uses GetProcessMemoryInfo. On other platforms, it falls
    back to resource.getrusage when available. The value is intentionally
    approximate and meant for profiling logs, not accounting.
    """
    if os.name == "nt":
        return _get_windows_memory_mb()

    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # Linux reports KB; macOS reports bytes. This heuristic keeps the log
        # useful without adding platform dependencies.
        value = float(usage.ru_maxrss)
        if value > 10_000_000:
            return value / (1024 * 1024)
        return value / 1024
    except Exception:
        return None


def _get_windows_memory_mb() -> float | None:
    try:
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)

        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        )

        if not ok:
            return None

        return float(counters.WorkingSetSize) / (1024 * 1024)
    except Exception:
        return None


def _format_memory(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} MB"


def _format_details(details: dict) -> str:
    if not details:
        return ""

    parts = []
    for key, value in details.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")

    if not parts:
        return ""

    return " | " + " ".join(parts)


@contextmanager
def profile_block(name: str, **details):
    logger = get_profile_logger()
    start_time = time.perf_counter()
    start_memory = get_memory_mb()

    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - start_time
        end_memory = get_memory_mb()
        delta = None if start_memory is None or end_memory is None else end_memory - start_memory
        logger.info(
            "%s failed | %.3fs | mem %s -> %s | delta %s%s",
            name,
            elapsed,
            _format_memory(start_memory),
            _format_memory(end_memory),
            _format_memory(delta),
            _format_details(details),
        )
        raise
    else:
        elapsed = time.perf_counter() - start_time
        end_memory = get_memory_mb()
        delta = None if start_memory is None or end_memory is None else end_memory - start_memory
        logger.info(
            "%s | %.3fs | mem %s -> %s | delta %s%s",
            name,
            elapsed,
            _format_memory(start_memory),
            _format_memory(end_memory),
            _format_memory(delta),
            _format_details(details),
        )


def log_profile_event(name: str, **details) -> None:
    get_profile_logger().info("%s%s", name, _format_details(details))
