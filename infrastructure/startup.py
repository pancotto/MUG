"""Startup infrastructure primitives."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QLockFile

from config.paths import get_user_data_dir
from infrastructure.logging_config import get_logger


ERROR_ALREADY_EXISTS = 183


def _load_kernel32():
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


class SingleInstanceGuard:
    def __init__(self, key: str):
        self._key = key
        self._lock: QLockFile | None = None
        self._mutex_handle = None
        self._owns_lock = False
        self._logger = get_logger(__name__)

        if sys.platform != "win32":
            lock_dir = get_user_data_dir()
            lock_dir.mkdir(parents=True, exist_ok=True)
            self._lock = QLockFile(str(lock_dir / f"{key}.lock"))
            self._lock.setStaleLockTime(30_000)

    def acquire(self) -> bool:
        try:
            if sys.platform == "win32":
                kernel32 = _load_kernel32()
                ctypes.set_last_error(0)
                handle = kernel32.CreateMutexW(None, False, f"Local\\{self._key}")
                last_error = ctypes.get_last_error()
                if not handle:
                    raise ctypes.WinError(last_error)

                self._mutex_handle = handle
                self._owns_lock = last_error != ERROR_ALREADY_EXISTS
                return self._owns_lock

            if self._lock is None:
                return True

            self._owns_lock = self._lock.tryLock(0)
            return self._owns_lock
        except Exception:
            self._logger.exception("Single-instance guard failed; allowing startup")
            return True

    def release(self) -> None:
        try:
            if sys.platform == "win32" and self._mutex_handle:
                _load_kernel32().CloseHandle(self._mutex_handle)
                self._mutex_handle = None
                self._owns_lock = False
                return

            if self._owns_lock and self._lock is not None:
                self._lock.unlock()
                self._owns_lock = False
        except Exception:
            self._logger.exception("Single-instance guard release failed")
