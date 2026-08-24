"""Pretty, theme-friendly HTML widgets for the playground notebook.

Each function returns an ``IPython.display.HTML`` object, so notebook cells stay
one-liners (``display(tool_catalog(tools))``) while the output looks polished.
Styling uses semi-transparent neutrals + solid accent badges so it reads well in
both light and dark Jupyter themes. Import is lazy: this module has no hard
dependency on IPython unless you actually call a widget.
"""

from __future__ import annotations

import html as _html
import json
from typing import Any

# --- palette ----------------------------------------------------------------
_INDIGO = "#6366f1"
_VIOLET = "#8b5cf6"
_GREEN = "#16a34a"
_AMBER = "#d97706"
_RED = "#dc2626"
_SLATE = "#64748b"

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
_CARD = (
    "border:1px solid rgba(127,127,127,.25);border-radius:12px;"
    "background:rgba(127,127,127,.06);padding:14px 16px;margin:6px 0;"
    f"font-family:{_FONT};line-height:1.45;"
)


def _esc(x: Any) -> str:
    return _html.escape(str(x))


def _html_obj(markup: str):
    from IPython.display import HTML

    return HTML(markup)


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:9999px;'
        f"background:{color};color:#fff;font-size:11px;font-weight:600;"
        f'white-space:nowrap;">{_esc(text)}</span>'
    )


def _chip(text: str) -> str:
    return (
        f'<code style="font-family:{_MONO};font-size:11.5px;padding:1px 6px;'
        f'border-radius:6px;background:rgba(127,127,127,.16);">{_esc(text)}</code>'
    )


# --- widgets -----------------------------------------------------------------
def banner(title: str, subtitle: str = ""):
    """A gradient hero banner for the top of the notebook."""
    sub = (
        f'<div style="opacity:.92;font-size:13.5px;margin-top:6px;">{_esc(subtitle)}</div>'
        if subtitle
        else ""
    )
    return _html_obj(
        f'<div style="background:linear-gradient(135deg,{_INDIGO},{_VIOLET});'
        f"color:#fff;border-radius:14px;padding:20px 22px;font-family:{_FONT};"
        f'box-shadow:0 6px 20px rgba(99,102,241,.25);">'
        f'<div style="font-size:20px;font-weight:700;letter-spacing:.2px;">{_esc(title)}</div>'
        f"{sub}</div>"
    )


def status_panel(mapping: dict[str, Any], title: str = "Environment"):
    """A compact key/value panel (great for showing config / a run summary)."""
    rows = "".join(
        f'<div style="display:flex;gap:10px;padding:3px 0;">'
        f'<div style="color:{_SLATE};min-width:130px;font-size:12.5px;">{_esc(k)}</div>'
        f'<div style="font-family:{_MONO};font-size:12.5px;">{_esc(v)}</div></div>'
        for k, v in mapping.items()
    )
    return _html_obj(
        f'<div style="{_CARD}">'
        f'<div style="font-weight:700;margin-bottom:6px;color:{_INDIGO};">{_esc(title)}</div>'
        f"{rows}</div>"
    )


def _score_color(score: int, ok: bool) -> str:
    if not ok:
        return _RED
    if score >= 90:
        return _GREEN
    if score >= 70:
        return _AMBER
    return _RED


def tool_catalog(tools: list[Any], title: str = "Tool catalog"):
    """Render tools as a table: name, description, params, and a lint badge.

    Merges "inspect" and "lint" into one glanceable view.
    """
    from data_agent.context_lab.tool_linter import lint_tool

    head = (
        f'<tr style="text-align:left;color:{_SLATE};font-size:11.5px;'
        'text-transform:uppercase;letter-spacing:.4px;">'
        '<th style="padding:6px 10px;">Tool</th>'
        '<th style="padding:6px 10px;">Description</th>'
        '<th style="padding:6px 10px;">Params</th>'
        '<th style="padding:6px 10px;">Lint</th></tr>'
    )
    body = []
    for t in tools:
        r = lint_tool(t)
        desc = (getattr(t, "description", "") or "").strip().splitlines()
        desc = desc[0] if desc else ""
        params = list(getattr(t, "args", {}) or {})
        params_html = " ".join(_chip(p) for p in params) or (
            f'<span style="color:{_SLATE};font-size:12px;">—</span>'
        )
        badge = _badge(f"{r.score}/100", _score_color(r.score, r.ok))
        tip = "; ".join(r.errors + r.warnings)
        tip_html = (
            f'<div style="color:{_SLATE};font-size:11px;margin-top:3px;">{_esc(tip)}</div>'
            if tip
            else ""
        )
        body.append(
            '<tr style="border-top:1px solid rgba(127,127,127,.18);">'
            f'<td style="padding:8px 10px;font-family:{_MONO};font-weight:600;'
            f'color:{_INDIGO};vertical-align:top;">{_esc(t.name)}</td>'
            f'<td style="padding:8px 10px;font-size:13px;vertical-align:top;">{_esc(desc)}</td>'
            f'<td style="padding:8px 10px;vertical-align:top;">{params_html}</td>'
            f'<td style="padding:8px 10px;vertical-align:top;">{badge}{tip_html}</td></tr>'
        )
    return _html_obj(
        f'<div style="{_CARD}">'
        f'<div style="font-weight:700;margin-bottom:8px;color:{_INDIGO};">'
        f'{_esc(title)} <span style="color:{_SLATE};font-weight:400;">'
        f"({len(tools)})</span></div>"
        '<table style="border-collapse:collapse;width:100%;">'
        f"{head}{''.join(body)}</table></div>"
    )


def skills_cards(skills: list[Any], title: str = "Skills"):
    """Render discovered skills as small cards."""
    if not skills:
        inner = f'<div style="color:{_SLATE};">No skills found.</div>'
    else:
        cards = "".join(
            '<div style="border:1px solid rgba(127,127,127,.22);border-radius:10px;'
            'padding:10px 12px;background:rgba(127,127,127,.04);">'
            f'<div style="font-family:{_MONO};font-weight:700;color:{_VIOLET};">'
            f"{_esc(s.name)}</div>"
            f'<div style="font-size:12.5px;margin-top:3px;">{_esc(s.description)}</div></div>'
            for s in skills
        )
        inner = (
            '<div style="display:grid;grid-template-columns:repeat(auto-fill,'
            f'minmax(230px,1fr));gap:10px;">{cards}</div>'
        )
    return _html_obj(
        f'<div style="{_CARD}"><div style="font-weight:700;margin-bottom:8px;'
        f'color:{_INDIGO};">{_esc(title)} <span style="color:{_SLATE};'
        f'font-weight:400;">({len(skills)})</span></div>{inner}</div>'
    )


def token_meter(label: str, tokens: int, soft_limit: int = 500):
    """A horizontal bar showing a token count against a 'keep it small' budget."""
    pct = min(100, tokens / soft_limit * 100) if soft_limit else 0
    if tokens < soft_limit * 0.4:
        color = _GREEN
    elif tokens < soft_limit:
        color = _AMBER
    else:
        color = _RED
    return _html_obj(
        f'<div style="{_CARD}">'
        f'<div style="display:flex;justify-content:space-between;font-size:13px;'
        f'margin-bottom:6px;"><span>{_esc(label)}</span>'
        f'<span style="font-family:{_MONO};color:{color};font-weight:700;">'
        f"{tokens} tokens</span></div>"
        '<div style="height:10px;border-radius:9999px;background:rgba(127,127,127,.18);'
        'overflow:hidden;">'
        f'<div style="height:100%;width:{pct:.0f}%;background:{color};"></div></div>'
        f'<div style="color:{_SLATE};font-size:11px;margin-top:5px;">'
        f"soft budget: {soft_limit} tokens</div></div>"
    )


def json_view(obj: Any, title: str = "Result"):
    """Pretty-print a JSON-able object in a monospace card."""
    try:
        text = json.dumps(obj, indent=2, ensure_ascii=False)
    except TypeError:
        text = str(obj)
    return _html_obj(
        f'<div style="{_CARD}"><div style="font-weight:700;margin-bottom:6px;'
        f'color:{_INDIGO};">{_esc(title)}</div>'
        f'<pre style="margin:0;font-family:{_MONO};font-size:12.5px;'
        f'white-space:pre-wrap;">{_esc(text)}</pre></div>'
    )


def command_box(command: str, note: str = ""):
    """A copy-friendly command block (run in a real terminal)."""
    note_html = (
        f'<div style="color:{_SLATE};font-size:12px;margin-bottom:6px;">{_esc(note)}</div>'
        if note
        else ""
    )
    return _html_obj(
        f'<div style="{_CARD}">{note_html}'
        f'<pre style="margin:0;font-family:{_MONO};font-size:12.5px;'
        "background:rgba(127,127,127,.14);padding:10px 12px;border-radius:8px;"
        f'white-space:pre-wrap;">{_esc(command)}</pre></div>'
    )
