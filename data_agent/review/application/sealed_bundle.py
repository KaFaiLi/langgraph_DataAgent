"""Integrity seals for atomically published, compatible review bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from data_agent.review.application.run_bundle import RunBundleError, load_completed_run

SEAL_FILE = "bundle_receipt.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_bundle(root: Path, fingerprint: str) -> str:
    files = {
        p.relative_to(root).as_posix(): file_hash(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != SEAL_FILE
    }
    value = {"schema_version": 1, "input_fingerprint": fingerprint, "files": files}
    (root / SEAL_FILE).write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")
    return file_hash(root / SEAL_FILE)


def validate_seal(root: Path, expected: str | None = None) -> dict:
    path = root / SEAL_FILE
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("bundle integrity receipt is missing or a symlink")
        if expected is not None and file_hash(path) != expected:
            raise ValueError("bundle receipt hash changed")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("schema_version") != 1 or not isinstance(receipt.get("files"), dict):
            raise ValueError("invalid bundle integrity receipt")
        if not receipt["files"] or "run_manifest.json" not in receipt["files"]:
            raise ValueError("bundle receipt omits required artifacts")
        for name, digest in receipt["files"].items():
            item = root / name
            if not item.resolve().is_relative_to(root.resolve()) or item.is_symlink():
                raise ValueError("bundle artifact escapes the sealed directory")
            if file_hash(item) != digest:
                raise ValueError(f"bundle artifact hash changed: {name}")
        return receipt
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise RunBundleError("bundle_integrity_invalid", str(exc)) from exc


def load_sealed_bundle(root: Path, expected: str | None = None):
    validate_seal(root, expected)
    return load_completed_run(root)
