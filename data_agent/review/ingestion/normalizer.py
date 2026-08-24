"""Deterministic text file reading."""

from __future__ import annotations

from pathlib import Path


def read_text_file(path: Path) -> str:
    """Read a text file with deterministic encoding fallback (utf-8-sig, cp1252)."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")

