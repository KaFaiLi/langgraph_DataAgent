"""Deterministic text normalization and file reading helpers."""

from __future__ import annotations

from pathlib import Path


def normalize_text(text: str) -> str:
    """Normalize line endings and trailing whitespace deterministically."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def read_text_file(path: Path) -> str:
    """Read a text file with deterministic encoding fallback (utf-8-sig, cp1252)."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


