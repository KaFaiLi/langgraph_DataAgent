"""Deterministic evidence validation for source-backed and reviewed evidence.

The validator is the single trust boundary for ``source://`` citations.  A
locator is useful only when it identifies a manifest source whose bytes have
not changed and whose cited region can still be reopened.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from data_agent.review.domain.evidence import EvidenceReference, parse_locator
from data_agent.review.domain.source import Source, SourceManifest
from data_agent.tools.source_tools import file_digest


class EvidenceDisposition(StrEnum):
    """Stable outcome class for deterministic evidence checks."""

    VALID = "valid"
    REVISE = "revise"
    UNRESOLVED = "unresolved"
    FATAL = "fatal"


class EvidenceFailureCode(StrEnum):
    """Machine-readable reason a cited reference cannot be trusted."""

    MALFORMED = "malformed"
    ESCAPES_SOURCE_ROOT = "escapes_source_root"
    NOT_IN_MANIFEST = "not_in_manifest"
    SOURCE_MISSING = "source_missing"
    SOURCE_CHANGED = "source_changed"
    REGION_UNAVAILABLE = "region_unavailable"
    REVIEWED_OUTPUT_UNAPPROVED = "reviewed_output_unapproved"
    INTERNAL_ERROR = "internal_error"


class EvidenceValidationResult(BaseModel):
    """One evidence result, including a reopened snippet when valid."""

    locator: str
    disposition: EvidenceDisposition
    valid: bool
    code: EvidenceFailureCode | None = None
    reason: str | None = None
    source_id: str | None = None
    snippet: str | None = None


class EvidenceValidationSummary(BaseModel):
    """Aggregate result for a named evidence collection."""

    results: list[EvidenceValidationResult] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return all(result.valid for result in self.results)

    @property
    def failures(self) -> list[EvidenceValidationResult]:
        return [result for result in self.results if not result.valid]


class EvidenceValidator:
    """Reopen and validate manifest-pinned evidence without model involvement."""

    def __init__(self, source_root: str | Path, manifest: SourceManifest) -> None:
        self._source_root: Path | None = Path(source_root)
        self._manifest: SourceManifest | None = manifest
        self._approved_locators: set[str] | None = None
        self._integrity_cache: dict[str, str | None] = {}

    @classmethod
    def source_backed(cls, source_root: str | Path, manifest: SourceManifest) -> EvidenceValidator:
        """Create the adapter that reopens current manifest-backed source evidence."""
        return cls(source_root, manifest)

    @classmethod
    def reviewed_output(cls, approved_locators: set[str]) -> EvidenceValidator:
        """Create the adapter for sealed reviewed output; it never reads raw sources."""
        validator = cls.__new__(cls)
        validator._source_root = None
        validator._manifest = None
        validator._approved_locators = set(approved_locators)
        validator._integrity_cache = {}
        return validator

    def reopen(self, locator_uri: str) -> tuple[str, Source]:
        """Return the cited text and source, raising the legacy locator error on failure."""
        # Imported lazily to retain the public evidence_reader facade without a cycle.
        from data_agent.review.ingestion.evidence_reader import (
            LocatorValidationError,
            _read_region,
            _resolve_source,
            _truncate,
        )

        if self._source_root is None or self._manifest is None:
            raise LocatorValidationError("reviewed-output evidence cannot reopen raw sources")
        locator = parse_locator(locator_uri)
        path, source = _resolve_source(locator, self._source_root, self._manifest)
        integrity_failure = self._source_integrity_failure(path, source)
        if integrity_failure is not None:
            raise LocatorValidationError(integrity_failure)
        return _truncate(_read_region(path, source, locator)), source

    def validate(self, locator_uri: str) -> EvidenceValidationResult:
        """Validate one source locator without raising for normal bad citations."""
        if self._approved_locators is not None:
            return self._validate_approved(locator_uri)
        try:
            snippet, source = self.reopen(locator_uri)
        except Exception as exc:  # translated to a stable caller-facing evidence result
            code, disposition = self._classify_failure(exc)
            return EvidenceValidationResult(
                locator=locator_uri,
                disposition=disposition,
                valid=False,
                code=code,
                reason=str(exc),
            )
        return EvidenceValidationResult(
            locator=locator_uri,
            disposition=EvidenceDisposition.VALID,
            valid=True,
            source_id=source.source_id,
            snippet=snippet,
        )

    def validate_references(
        self, references: Sequence[EvidenceReference]
    ) -> EvidenceValidationSummary:
        return EvidenceValidationSummary(
            results=[self.validate(reference.locator) for reference in references]
        )

    def _validate_approved(self, locator_uri: str) -> EvidenceValidationResult:
        approved_locators = self._approved_locators
        if approved_locators is None:
            raise RuntimeError("reviewed-output adapter has no approved locator set")
        if locator_uri in approved_locators:
            return EvidenceValidationResult(
                locator=locator_uri,
                disposition=EvidenceDisposition.VALID,
                valid=True,
            )
        return EvidenceValidationResult(
            locator=locator_uri,
            disposition=EvidenceDisposition.REVISE,
            valid=False,
            code=EvidenceFailureCode.REVIEWED_OUTPUT_UNAPPROVED,
            reason="locator is not in the approved reviewed-output evidence set",
        )

    @staticmethod
    def validate_approved_references(
        references: Sequence[EvidenceReference], approved_locators: set[str]
    ) -> EvidenceValidationSummary:
        """Validate reviewed-output references without reopening raw source material."""
        return EvidenceValidator.reviewed_output(approved_locators).validate_references(references)

    def _source_integrity_failure(self, path: Path, source: Source) -> str | None:
        cached = self._integrity_cache.get(source.path)
        if source.path in self._integrity_cache:
            return cached
        failure: str | None
        try:
            size = path.stat().st_size
            digest, _ = file_digest(path)
        except OSError as exc:
            failure = f"source file cannot be read: {source.path}: {exc}"
        else:
            failure = None
            if size != source.size_bytes or digest != source.sha256:
                failure = f"source file changed since manifest was created: {source.path}"
        self._integrity_cache[source.path] = failure
        return failure

    @staticmethod
    def _classify_failure(exc: Exception) -> tuple[EvidenceFailureCode, EvidenceDisposition]:
        text = str(exc).lower()
        if "changed since manifest" in text:
            return EvidenceFailureCode.SOURCE_CHANGED, EvidenceDisposition.FATAL
        if "file not found" in text or "cannot be read" in text:
            return EvidenceFailureCode.SOURCE_MISSING, EvidenceDisposition.UNRESOLVED
        if "escapes the source root" in text:
            return EvidenceFailureCode.ESCAPES_SOURCE_ROOT, EvidenceDisposition.REVISE
        if "not in the review manifest" in text:
            return EvidenceFailureCode.NOT_IN_MANIFEST, EvidenceDisposition.REVISE
        if "locator" in text and ("must" in text or "invalid" in text or "unknown locator" in text):
            return EvidenceFailureCode.MALFORMED, EvidenceDisposition.REVISE
        if "out of range" in text or "sheet" in text or "require" in text:
            return EvidenceFailureCode.REGION_UNAVAILABLE, EvidenceDisposition.REVISE
        return EvidenceFailureCode.INTERNAL_ERROR, EvidenceDisposition.FATAL
