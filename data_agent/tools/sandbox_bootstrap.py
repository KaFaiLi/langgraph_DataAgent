"""Entry point used by the shared Python tool inside the isolated interpreter."""

from __future__ import annotations

import contextlib
import importlib.util
import sys
from pathlib import Path


def _load_guard() -> None:
    guard_path = Path(__file__).with_name("sandbox_guard.py")
    spec = importlib.util.spec_from_file_location("data_agent_sandbox_guard", guard_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sandbox guard from {guard_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.install_import_blocker()
    module.install_os_patches()
    module.install_path_guard()


def _preimport_analysis_libraries() -> None:
    """Warm native dataframe libraries before restrictive imports are blocked."""

    for name in ("polars", "duckdb"):
        with contextlib.suppress(Exception):
            __import__(name)


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("usage: sandbox_bootstrap.py <script> <source_root> <workspace_root>")
    script = Path(sys.argv[1]).resolve()
    if not script.is_file():
        raise SystemExit("sandbox script does not exist")
    _preimport_analysis_libraries()
    _load_guard()
    code = compile(script.read_text(encoding="utf-8"), str(script), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(script)})  # noqa: S102


if __name__ == "__main__":
    main()
