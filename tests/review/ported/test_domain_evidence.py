"""Evidence locator parsing/formatting tests."""

from __future__ import annotations

import pytest

from data_agent.review.domain.evidence import (
    EvidenceReference,
    Locator,
    format_locator,
    parse_locator,
)

VALID_CASES = [
    (
        "source://risk.xlsx#sheet=DailyRisk&rows=120:128",
        Locator(path="risk.xlsx", sheet="DailyRisk", rows=(120, 128)),
    ),
    ("source://comments.pdf#page=14", Locator(path="comments.pdf", page=14)),
    (
        "source://validation.csv#rows=94:99",
        Locator(path="validation.csv", rows=(94, 99)),
    ),
    (
        "source://notes/readme.md#lines=10:15",
        Locator(path="notes/readme.md", lines=(10, 15)),
    ),
    ("source://context.txt", Locator(path="context.txt")),
]


@pytest.mark.parametrize(("uri", "expected"), VALID_CASES)
def test_parse_locator(uri: str, expected: Locator) -> None:
    assert parse_locator(uri) == expected


@pytest.mark.parametrize(("uri",), [(case[0],) for case in VALID_CASES])
def test_round_trip(uri: str) -> None:
    assert format_locator(parse_locator(uri)) == uri


INVALID_CASES = [
    "risk.xlsx#sheet=A",  # missing scheme
    "source://",  # missing path
    "source://a.pdf#page=0",  # non-positive page
    "source://a.pdf#page=abc",
    "source://a.csv#rows=9:4",  # reversed range
    "source://a.csv#rows=9:10:11",
    "source://a.csv#unknown=1",
    "source://a.csv#page",  # fragment without value
    "source://../a.csv",  # path escape
    "source:///abs/a.csv",  # absolute path
]


@pytest.mark.parametrize("uri", INVALID_CASES)
def test_invalid_locators_raise(uri: str) -> None:
    with pytest.raises(ValueError):
        parse_locator(uri)


def test_single_row_locator_canonicalizes_to_range() -> None:
    # LLM output often omits the range; rows=N means the single row N.
    assert parse_locator("source://a.csv#rows=9").rows == (9, 9)
    assert format_locator(parse_locator("source://a.csv#rows=9")) == "source://a.csv#rows=9:9"
    assert parse_locator("source://a.md#lines=4").lines == (4, 4)


def test_evidence_reference_canonicalizes() -> None:
    ref = EvidenceReference(locator="source://risk.xlsx#sheet=DailyRisk&rows=120:128")
    assert ref.locator == "source://risk.xlsx#sheet=DailyRisk&rows=120:128"
    assert ref.parsed.rows == (120, 128)
    # Equivalent reference written in the same canonical form compares equal.
    assert ref == EvidenceReference(locator="source://risk.xlsx#sheet=DailyRisk&rows=120:128")


def test_evidence_reference_rejects_invalid_locator() -> None:
    with pytest.raises(ValueError):
        EvidenceReference(locator="not-a-locator")


def test_evidence_reference_optional_quote() -> None:
    ref = EvidenceReference(locator="source://comments.pdf#page=14", quote="within limits")
    assert ref.quote == "within limits"
