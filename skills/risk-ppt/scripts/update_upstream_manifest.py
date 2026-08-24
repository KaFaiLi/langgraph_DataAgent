"""Regenerate the pinned PPT Master copied-file checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

UPSTREAM_COMMIT = "10ec12e518615dde0b303d60c140a330f0a92703"

_DIRECT_MAPPINGS = {
    "LICENSE": "LICENSE",
    "references/canvas-formats.md": "references/canvas-formats.md",
    "references/preset-shape-vocabulary.md": "references/preset-shape-vocabulary.md",
    "references/semantic-svg.md": "references/semantic-svg.md",
    "references/shared-standards-core.md": "references/shared-standards-core.md",
    "references/svg-effects.md": "references/svg-effects.md",
    "references/visual-review.md": "references/visual-review.md",
    "references/visual-styles/data-journalism.md": "references/data-journalism.md",
    "references/modes/briefing.md": "references/modes/briefing.md",
    "references/modes/pyramid.md": "references/modes/pyramid.md",
    "templates/styles/operating-review/templates/design_spec.md": (
        "references/operating-review.md"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory(skill_root: Path, upstream_root: Path) -> list[dict[str, str]]:
    mappings = dict(_DIRECT_MAPPINGS)

    vendor_root = skill_root / "vendor" / "ppt-master"
    for local in sorted(vendor_root.rglob("*")):
        if (
            not local.is_file()
            or local.name == "UPSTREAM_MANIFEST.json"
            or local.suffix == ".pyc"
            or "__pycache__" in local.parts
        ):
            continue
        relative = local.relative_to(vendor_root).as_posix()
        mappings[relative] = f"vendor/ppt-master/{relative}"

    entries: list[dict[str, str]] = []
    for source_rel, local_rel in sorted(mappings.items()):
        source = upstream_root / Path(source_rel)
        local = skill_root / Path(local_rel)
        if not source.is_file() or not local.is_file():
            raise FileNotFoundError(f"missing copied file: {source_rel} -> {local_rel}")
        source_hash = _sha256(source)
        local_hash = _sha256(local)
        if source_hash != local_hash:
            raise ValueError(f"copied file differs from upstream: {local_rel}")
        entries.append(
            {
                "source_path": source_rel,
                "local_path": local_rel,
                "sha256": local_hash,
            }
        )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "upstream_root",
        type=Path,
        help="Pinned upstream skills/ppt-master directory",
    )
    args = parser.parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    entries = _inventory(skill_root, args.upstream_root.resolve())
    manifest = {
        "schema_version": 1,
        "upstream": "https://github.com/hugohe3/ppt-master",
        "upstream_version": "4.8.0",
        "upstream_commit": UPSTREAM_COMMIT,
        "file_count": len(entries),
        "files": entries,
    }
    target = skill_root / "vendor" / "ppt-master" / "UPSTREAM_MANIFEST.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
