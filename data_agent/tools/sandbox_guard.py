"""Best-effort Python-level guards for the shared analysis subprocess.

This is an anti-misuse boundary for generated analysis, not a kernel sandbox.
The parent process still controls the roots and applies a timeout.  The guard
blocks imports and process/network APIs, allows reads from source/interpreter
roots, and allows writes only in the configured workspace.
"""

from __future__ import annotations

import builtins
import importlib.abc
import importlib.util
import io
import os
import pathlib
import sys
from collections.abc import Sequence
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_blocklist() -> frozenset[str]:
    path = Path(__file__).with_name("sandbox_blocklist.txt")
    return frozenset(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


BLOCKED_TOP_LEVELS = _load_blocklist()


class _BlockingLoader(importlib.abc.Loader):
    def __init__(self, fullname: str) -> None:
        self.fullname = fullname

    def create_module(self, spec: ModuleSpec) -> None:
        raise ImportError(f"module {self.fullname!r} is blocked in the analysis sandbox")

    def exec_module(self, module: ModuleType) -> None:
        raise ImportError(f"module {self.fullname!r} is blocked in the analysis sandbox")


class _ImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname.split(".", 1)[0] in BLOCKED_TOP_LEVELS:
            return importlib.util.spec_from_loader(fullname, _BlockingLoader(fullname))
        return None


def install_import_blocker() -> None:
    sys.meta_path.insert(0, _ImportBlocker())
    for name in list(sys.modules):
        if name.split(".", 1)[0] in BLOCKED_TOP_LEVELS:
            del sys.modules[name]


_DENIED_PROCESS_NAMES = (
    "system",
    "popen",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "posix_spawn",
    "posix_spawnp",
    "execl",
    "execle",
    "execlp",
    "execlpe",
    "execv",
    "execve",
    "execvp",
    "execvpe",
    "fork",
    "forkpty",
    "startfile",
    "_exit",
    "abort",
    "kill",
)


def _denied_process(*args: object, **kwargs: object) -> None:
    raise PermissionError("process spawning is blocked in the analysis sandbox")


def _norm(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


class _PathGuard:
    def __init__(self) -> None:
        if len(sys.argv) < 4:
            raise RuntimeError("sandbox bootstrap requires script, source_root, workspace_root")
        self.source_root = _norm(sys.argv[2])
        self.workspace_root = _norm(sys.argv[3])
        self.read_roots = [self.source_root, self.workspace_root, _norm(sys.prefix)]
        if sys.base_prefix != sys.prefix:
            self.read_roots.append(_norm(sys.base_prefix))
        self.write_roots = [self.workspace_root]
        self.original_open = builtins.open
        self.original_io_open = io.open
        self.original_os_open = os.open
        self._normalizing = False

    @staticmethod
    def _within(candidate: str, roots: list[str]) -> bool:
        return any(
            candidate == root or candidate.startswith(root.rstrip(os.sep) + os.sep)
            for root in roots
        )

    def _check(self, file: Any, mode: str = "r", *, write: bool | None = None) -> None:
        # Standard streams are legitimate and do not grant filesystem access.
        if isinstance(file, int):
            if file in (0, 1, 2):
                return
            raise PermissionError("sandbox file descriptor access is blocked")
        try:
            self._normalizing = True
            candidate = _norm(file)
        except (TypeError, ValueError) as exc:
            raise PermissionError("sandbox path must be a filesystem path") from exc
        finally:
            self._normalizing = False
        wants_write = (
            write if write is not None else any(flag in mode for flag in ("w", "a", "x", "+"))
        )
        roots = self.write_roots if wants_write else self.read_roots
        if not self._within(candidate, roots):
            action = "write" if wants_write else "read"
            raise PermissionError(f"sandbox {action} denied for {os.fspath(file)!r}")

    def open(self, file: Any, mode: str = "r", *args: object, **kwargs: object) -> Any:
        self._check(file, mode)
        return self.original_open(file, mode, *args, **kwargs)

    def io_open(self, file: Any, mode: str = "r", *args: object, **kwargs: object) -> Any:
        self._check(file, mode)
        return self.original_io_open(file, mode, *args, **kwargs)

    def os_open(
        self, file: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        wants_write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))
        self._check(file, write=wants_write)
        return self.original_os_open(file, flags, mode, dir_fd=dir_fd)

    def check_read(self, file: Any) -> None:
        self._check(file, write=False)

    def check_write(self, file: Any) -> None:
        self._check(file, write=True)


_ACTIVE_GUARD: _PathGuard | None = None


def install_os_patches() -> None:
    """Disable process functions and filesystem mutations outside workspace."""

    for name in _DENIED_PROCESS_NAMES:
        if hasattr(os, name):
            setattr(os, name, _denied_process)


def install_path_guard() -> None:
    global _ACTIVE_GUARD
    guard = _PathGuard()
    _ACTIVE_GUARD = guard
    builtins.open = guard.open
    io.open = guard.io_open
    os.open = guard.os_open
    pathlib.Path.open = lambda self, *args, **kwargs: guard.open(str(self), *args, **kwargs)

    # Guard common read operations so generated code cannot enumerate an
    # unrelated directory even without opening a file.
    for name in ("listdir", "scandir", "stat", "lstat", "access", "readlink"):
        original = getattr(os, name, None)
        if original is None:
            continue

        def checked_read(
            path: Any, *args: object, _original: Any = original, **kwargs: object
        ) -> Any:
            if guard._normalizing:
                return _original(path, *args, **kwargs)
            guard.check_read(path)
            return _original(path, *args, **kwargs)

        setattr(os, name, checked_read)

    # Mutations are permitted only below workspace_root.  Capture originals
    # before wrapping, because pathlib delegates to these functions.
    for name in (
        "remove",
        "unlink",
        "mkdir",
        "makedirs",
        "rmdir",
        "removedirs",
        "touch",
    ):
        original = getattr(os, name, None)
        if original is None:
            continue

        def checked_write(
            path: Any, *args: object, _original: Any = original, **kwargs: object
        ) -> Any:
            guard.check_write(path)
            return _original(path, *args, **kwargs)

        setattr(os, name, checked_write)

    for name in ("rename", "replace", "link", "symlink"):
        original = getattr(os, name, None)
        if original is None:
            continue

        def checked_move(
            source: Any,
            destination: Any,
            *args: object,
            _original: Any = original,
            **kwargs: object,
        ) -> Any:
            guard.check_write(source)
            guard.check_write(destination)
            return _original(source, destination, *args, **kwargs)

        setattr(os, name, checked_move)

    original_chdir = os.chdir

    def checked_chdir(path: Any) -> None:
        guard.check_read(path)
        original_chdir(path)

    os.chdir = checked_chdir
