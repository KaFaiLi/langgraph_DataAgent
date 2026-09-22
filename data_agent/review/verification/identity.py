"""Stable identities for substantive findings and authoritative role receipts."""

from __future__ import annotations

import hashlib
import json

from data_agent.review.domain.finding import Finding


def content_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def finding_version(finding: Finding | dict) -> str:
    data = finding.model_dump(mode="json") if isinstance(finding, Finding) else dict(finding)
    data.pop("verifier_status", None)
    return content_digest(data)
