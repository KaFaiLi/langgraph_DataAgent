from data_agent.context_lab.tokens import estimate_tokens, payload_stats
from data_agent.context_lab.tool_linter import lint_tool


class _FakeTool:
    def __init__(self, name, description, args):
        self.name = name
        self.description = description
        self.args = args


def test_estimate_tokens_and_stats():
    tokens, method = estimate_tokens("hello world this is a test")
    assert tokens >= 1
    assert isinstance(method, str)

    stats = payload_stats("line one\nline two")
    assert stats["lines"] == 2
    assert stats["characters"] == len("line one\nline two")
    assert stats["tokens"] >= 1


def test_linter_flags_bad_tool():
    bad = _FakeTool(name="DoStuff", description="", args={"x": {}})
    report = lint_tool(bad)
    assert not report.ok  # missing description => error
    assert report.score < 100
    assert any("description" in e.lower() for e in report.errors)


def test_linter_passes_good_tool():
    good = _FakeTool(
        name="search_orders",
        description=(
            "Search the orders database by customer and return the most recent "
            "matching orders as a small structured list."
        ),
        args={"customer_id": {"description": "The customer's unique id."}},
    )
    report = lint_tool(good)
    assert report.ok
    assert report.score == 100

