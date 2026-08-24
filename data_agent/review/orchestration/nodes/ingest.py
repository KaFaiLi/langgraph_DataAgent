"""Ingest: build the deterministic catalogue. Parse failures fail the run."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.ingestion.catalog import build_catalog as ingest_build_catalog
from data_agent.review.orchestration.state import ParentState


def build_catalog(state: ParentState, config: RunnableConfig) -> dict:
    """Build the manifest and persist it to the output directory.

    Any source with a parse error (corrupt file, unsupported type) fails the
    run explicitly - never silently skipped (spec section 41).
    """
    source_root = Path(state["source_root"])
    try:
        manifest = ingest_build_catalog(source_root)
    except FileNotFoundError as exc:
        return {"status": "failed", "failure_reason": str(exc)}

    broken = [source for source in manifest.sources if source.parse_error]
    if broken:
        details = "; ".join(
            f"{source.source_id} ({source.path}): {source.parse_error}" for source in broken
        )
        return {
            "manifest": manifest.model_dump(mode="json"),
            "status": "failed",
            "failure_reason": f"source parsing failed: {details}",
        }
    if not manifest.sources:
        return {
            "manifest": manifest.model_dump(mode="json"),
            "status": "failed",
            "failure_reason": "no source files found under the source root",
        }

    catalog_path = Path(state["output_dir"]) / "catalog.json"
    catalog_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return {"manifest": manifest.model_dump(mode="json")}
