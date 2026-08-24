"""Offline runtime adapter for the pinned PPT Master SVG core.

The public functions in this module are trusted entrypoints loaded from the
validated risk-ppt skill. They deliberately expose only the project's flat,
editable, reviewed-output presentation path.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import re
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any
from xml.etree import ElementTree as ET

import pymupdf

UPSTREAM_COMMIT = "10ec12e518615dde0b303d60c140a330f0a92703"
QUALITY_SCHEMA_VERSION = 1
CONVERSION_SCHEMA_VERSION = 1
EXPECTED_VIEWBOX = "0 0 1280 720"

_ALLOWED_TAGS = {
    "svg",
    "g",
    "defs",
    "linearGradient",
    "radialGradient",
    "stop",
    "clipPath",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "path",
    "text",
    "tspan",
}
_ALLOWED_PPTX_ATTRIBUTES = {
    "data-pptx-bounds",
    "data-pptx-page-role",
    "data-pptx-role",
}
_EXTERNAL_VALUE = re.compile(r"(?:https?|ftp|file|data):|(?:^|[\s(])//", re.IGNORECASE)
_RAW_PATH = re.compile(r"(?:(?:^|[\s\"'(])[A-Za-z]:[\\/]|/(?:Users|home|var|tmp)/|\\\\)")
_UNRESOLVED = re.compile(r"\{\{[^{}]+\}\}|\b(?:TODO|TBD)\b", re.IGNORECASE)
_GROUP_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _vendor_scripts_root() -> Path:
    return Path(__file__).resolve().parents[1] / "vendor" / "ppt-master" / "scripts"


def _install_curated_distribution_shims() -> None:
    """Provide the CLI-only globals omitted from this curated distribution."""
    if "console_encoding" not in sys.modules:
        console_module = ModuleType("console_encoding")
        console_module.configure_utf8_stdio = lambda: None
        sys.modules["console_encoding"] = console_module
    if "config" not in sys.modules:
        config_module = ModuleType("config")
        config_module.CANVAS_FORMATS = {
            "ppt169": {
                "name": "PPT 16:9",
                "dimensions": "1280x720",
                "viewbox": EXPECTED_VIEWBOX,
            }
        }
        sys.modules["config"] = config_module


def _load_upstream(module_name: str) -> Any:
    scripts_root = _vendor_scripts_root()
    scripts_text = str(scripts_root)
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)
    _install_curated_distribution_shims()
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        return importlib.import_module(module_name)
    finally:
        sys.dont_write_bytecode = previous


def _within(root: Path, candidate: Path, label: str) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"{label} escapes controlled root {resolved_root}: {resolved}")
    return resolved


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprint(svg_files: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(svg_files, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _normalize_bounds(value: str) -> tuple[float, float, float, float] | None:
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        values = [float(part) for part in parts]
    except ValueError:
        return None
    return values[0], values[1], values[2], values[3]


def _project_svg_errors(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"cannot parse SVG: {exc}"]

    if _local_name(root.tag) != "svg":
        errors.append("root element must be svg")
    if root.get("viewBox") != EXPECTED_VIEWBOX:
        errors.append(f"viewBox must be {EXPECTED_VIEWBOX!r}")
    if not root.get("data-pptx-page-role"):
        errors.append("root requires data-pptx-page-role")

    direct_visuals = [child for child in root if _local_name(child.tag) != "defs"]
    if not direct_visuals:
        errors.append("SVG must contain at least one top-level visual group")
    if any(_local_name(child.tag) != "g" for child in direct_visuals):
        errors.append("all top-level visual content must be wrapped in semantic g elements")

    group_ids: set[str] = set()
    for group in direct_visuals:
        if _local_name(group.tag) != "g":
            continue
        group_id = group.get("id", "")
        if not _GROUP_ID.fullmatch(group_id):
            errors.append("every top-level group requires a stable semantic id")
        elif group_id in group_ids:
            errors.append(f"duplicate top-level group id: {group_id}")
        group_ids.add(group_id)
        bounds = _normalize_bounds(group.get("data-pptx-bounds", ""))
        if bounds is None:
            errors.append(f"top-level group {group_id or '<unnamed>'} requires data-pptx-bounds")
        elif (
            bounds[0] < 0
            or bounds[1] < 0
            or bounds[2] <= 0
            or bounds[3] <= 0
            or bounds[0] + bounds[2] > 1280
            or bounds[1] + bounds[3] > 720
        ):
            errors.append(f"top-level group {group_id or '<unnamed>'} has invalid bounds")

    for element in root.iter():
        tag = _local_name(element.tag)
        if tag not in _ALLOWED_TAGS:
            errors.append(f"unsupported SVG element: {tag}")
        for raw_name, raw_value in element.attrib.items():
            name = _local_name(raw_name)
            value = str(raw_value)
            if name.lower().startswith("on"):
                errors.append(f"event-handler attribute is forbidden: {name}")
            if name in {"href", "src"}:
                errors.append(f"linked assets are forbidden: {name}")
            if name.startswith("data-pptx-") and name not in _ALLOWED_PPTX_ATTRIBUTES:
                errors.append(f"unsupported PowerPoint marker: {name}")
            if _EXTERNAL_VALUE.search(value) or _RAW_PATH.search(value):
                errors.append(f"external or raw path value is forbidden in {name}")
            for match in re.findall(r"url\(([^)]+)\)", value, flags=re.IGNORECASE):
                if not match.strip(" \t\r\n'\"").startswith("#"):
                    errors.append(f"external CSS reference is forbidden in {name}")
            if "@import" in value.lower():
                errors.append(f"CSS imports are forbidden in {name}")
        text = element.text or ""
        if _EXTERNAL_VALUE.search(text):
            errors.append("external references are forbidden in SVG text")
        if _RAW_PATH.search(text):
            errors.append("raw filesystem paths are forbidden in SVG text")
        if _UNRESOLVED.search(text):
            errors.append("unresolved placeholder text is forbidden")

    return list(dict.fromkeys(errors))


def _sanitized_checker_result(result: Mapping[str, Any], path: Path) -> dict[str, object]:
    return {
        "file": path.name,
        "sha256": _file_sha256(path),
        "passed": bool(result.get("passed", False)),
        "errors": [str(item) for item in result.get("errors", [])],
        "warnings": [str(item) for item in result.get("warnings", [])],
        "info": result.get("info", {}),
    }


def check_svg_deck(
    workspace_root: Path,
    svg_files: Sequence[Path],
    report_path: Path,
) -> dict[str, object]:
    """Run the project guard and pinned upstream checker over an SVG deck."""
    workspace = workspace_root.resolve()
    checked_files = [_within(workspace, Path(path), "SVG") for path in svg_files]
    if not checked_files:
        raise ValueError("at least one SVG is required")
    if len({path.name for path in checked_files}) != len(checked_files):
        raise ValueError("SVG filenames must be unique")
    parent_dirs = {path.parent for path in checked_files}
    if len(parent_dirs) != 1:
        raise ValueError("all SVG files must share one controlled deck directory")
    svg_dir = next(iter(parent_dirs))
    discovered = {path.resolve() for path in svg_dir.glob("*.svg")}
    if discovered != set(checked_files):
        raise ValueError("SVG deck directory contains files outside the declared deck roster")
    report_target = _within(workspace, report_path, "quality report")
    report_target.parent.mkdir(parents=True, exist_ok=True)

    checker_module = _load_upstream("svg_quality.checker")
    checker = checker_module.SVGQualityChecker(quick_generate=True)
    file_results: list[dict[str, object]] = []
    blocking: list[str] = []
    warnings: list[str] = []

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        upstream_results = checker.check_directory(str(svg_dir), expected_format="ppt169")
    upstream_by_name = {
        str(result.get("file", "")): result
        for result in upstream_results
        if isinstance(result, dict)
    }

    for path in sorted(checked_files, key=lambda item: item.name):
        project_errors = _project_svg_errors(path)
        upstream = upstream_by_name.get(
            path.name,
            {
                "passed": False,
                "errors": ["upstream deck checker did not return this rostered slide"],
                "warnings": [],
                "info": {},
            },
        )
        normalized = _sanitized_checker_result(upstream, path)
        upstream_errors = [str(item) for item in normalized["errors"]]
        upstream_warnings = [str(item) for item in normalized["warnings"]]
        errors = [*project_errors, *upstream_errors]
        normalized["errors"] = errors
        normalized["passed"] = not errors
        file_results.append(normalized)
        blocking.extend(f"{path.name}: {item}" for item in errors)
        warnings.extend(f"{path.name}: {item}" for item in upstream_warnings)

    aggregate_errors = int(checker.summary.get("errors", 0))
    per_file_errors = sum(len(result["errors"]) for result in file_results)
    if aggregate_errors > per_file_errors:
        blocking.append(
            "upstream deck checker reported "
            f"{aggregate_errors - per_file_errors} aggregate blocking issue(s)"
        )

    report: dict[str, object] = {
        "schema_version": QUALITY_SCHEMA_VERSION,
        "upstream_commit": UPSTREAM_COMMIT,
        "canvas": EXPECTED_VIEWBOX,
        "source_fingerprint": _source_fingerprint(checked_files),
        "passed": not blocking,
        "files": file_results,
        "blocking_issues": blocking,
        "warnings": warnings,
        "upstream_summary": dict(checker.summary),
        "upstream_output": "\n".join(
            part.strip() for part in (stdout.getvalue(), stderr.getvalue()) if part.strip()
        )[-20_000:],
    }
    report_target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def render_svg_previews(
    workspace_root: Path,
    svg_files: Sequence[Path],
    preview_dir: Path,
) -> dict[str, object]:
    """Render the validated SVGs to exact 1280x720 offline PNG previews."""
    workspace = workspace_root.resolve()
    checked_files = [_within(workspace, Path(path), "SVG") for path in svg_files]
    target_dir = _within(workspace, preview_dir, "preview directory")
    target_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, str]] = []
    for svg_path in sorted(checked_files, key=lambda item: item.name):
        document = pymupdf.open(stream=svg_path.read_bytes(), filetype="svg")
        try:
            page = document[0]
            matrix = pymupdf.Matrix(1280 / page.rect.width, 720 / page.rect.height)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            if (pixmap.width, pixmap.height) != (1280, 720):
                raise RuntimeError(
                    f"preview size mismatch for {svg_path.name}: {pixmap.width}x{pixmap.height}"
                )
            target = target_dir / f"{svg_path.stem}.png"
            pixmap.save(target)
        finally:
            document.close()
        rendered.append({"file": target.name, "sha256": _file_sha256(target)})
    return {"width": 1280, "height": 720, "files": rendered}


def _read_current_quality_report(
    workspace: Path,
    svg_files: Sequence[Path],
    report_path: Path,
) -> dict[str, Any]:
    target = _within(workspace, report_path, "quality report")
    try:
        report = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid SVG quality report: {exc}") from exc
    if report.get("schema_version") != QUALITY_SCHEMA_VERSION:
        raise ValueError("unsupported SVG quality report schema")
    if report.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ValueError("SVG quality report uses a different upstream commit")
    if not report.get("passed"):
        raise ValueError("SVG quality report contains blocking failures")
    if report.get("source_fingerprint") != _source_fingerprint(svg_files):
        raise ValueError("SVG quality report is stale for the authored sources")
    return report


def convert_svg_deck(
    run_root: Path,
    workspace_root: Path,
    svg_files: Sequence[Path],
    output_path: Path,
    quality_report_path: Path,
    receipt_path: Path,
    *,
    deck_title: str,
    notes: Mapping[str, str],
) -> dict[str, object]:
    """Convert the exact validated SVGs into editable flat DrawingML slides."""
    run = run_root.resolve()
    workspace = _within(run, workspace_root, "PPT workspace")
    checked_files = [_within(workspace, Path(path), "SVG") for path in svg_files]
    target = _within(run, output_path, "PPTX output")
    receipt_target = _within(workspace, receipt_path, "conversion receipt")
    target.parent.mkdir(parents=True, exist_ok=True)
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    quality = _read_current_quality_report(workspace, checked_files, quality_report_path)

    builder = _load_upstream("svg_to_pptx.pptx_package.builder")
    trace_path = receipt_target.with_name("upstream_conversion_trace.json")
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        converted = builder.create_pptx_with_native_svg(
            svg_files=list(checked_files),
            output_path=target,
            canvas_format="ppt169",
            verbose=False,
            transition=None,
            auto_advance=None,
            notes=dict(notes),
            enable_notes=True,
            use_native_shapes=True,
            animation=None,
            narration_audio=None,
            use_narration_timings=False,
            cache_dir=workspace / "conversion_cache",
            workers=1,
            image_optimize=False,
            native_objects=False,
            conversion_trace_path=trace_path,
            doc_metadata={"title": deck_title, "subject": "Independent risk review"},
            structure_name="Risk Review",
            pptx_structure="flat",
            expected_viewbox=EXPECTED_VIEWBOX,
            transition_sound=None,
            text_flow="preserve",
        )
    if not converted or not target.is_file():
        raise RuntimeError("upstream SVG-to-DrawingML conversion did not produce a deck")

    with zipfile.ZipFile(target) as package:
        package_names = set(package.namelist())
    forbidden_parts = sorted(
        name
        for name in package_names
        if name.startswith(("ppt/media/", "ppt/embeddings/"))
        or "audio" in name.lower()
        or "video" in name.lower()
    )
    if forbidden_parts:
        raise RuntimeError(f"disabled media/native payload parts were exported: {forbidden_parts}")

    receipt: dict[str, object] = {
        "schema_version": CONVERSION_SCHEMA_VERSION,
        "upstream_commit": UPSTREAM_COMMIT,
        "quality_fingerprint": quality["source_fingerprint"],
        "pptx_sha256": _file_sha256(target),
        "slide_count": len(checked_files),
        "mode": "flat-editable-drawingml",
        "features": {
            "animations": False,
            "transitions": False,
            "audio": False,
            "narration": False,
            "images": False,
            "native_objects": False,
            "external_assets": False,
        },
    }
    receipt_target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt
