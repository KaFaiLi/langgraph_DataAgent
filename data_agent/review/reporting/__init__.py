"""Reporting: deterministic Markdown rendering of the internal contracts.

Markdown is the external contract (spec section 24): every specialist
report is rendered from its Pydantic object by pure code, so the template
is stable and testable.
"""

from data_agent.review.reporting.markdown import render_specialist_report

__all__ = ["render_specialist_report"]


