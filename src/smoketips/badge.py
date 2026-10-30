"""Badge — the last run's grade as an SVG you can commit and show in a README.

A number nobody looks at is not observability. The badge puts the crew's grade
where the pull request already is.
"""
from __future__ import annotations

from .ledger import Event
from .score import grade_of

COLORS = {
    "A": "#2ea043",  # green
    "B": "#7bb33a",
    "C": "#d4a017",  # amber
    "D": "#e0620d",
    "F": "#d1242f",  # red
    "-": "#8b949e",  # no data
}

_LABEL = "smokeTIPs"
_CHAR_PX = 6.6      # avg advance of the 11px DejaVu/Verdana stack below
_PAD_PX = 11.0


def overall(events: list[Event]) -> tuple[str, float, float]:
    """Grade the whole run, not one agent: reliability and safety over every
    recorded action. Returns (grade, reliability, safety)."""
    if not events:
        return "-", 0.0, 0.0
    n = len(events)
    reliability = sum(1 for e in events if e.status != "error") / n
    safety = sum(1 for e in events if not e.flags) / n
    return grade_of(reliability, safety), reliability, safety


def _width(text: str) -> float:
    return len(text) * _CHAR_PX + 2 * _PAD_PX


def render(events: list[Event]) -> str:
    """A flat shields-style badge. No network, no dependency, no build step."""
    grade, reliability, safety = overall(events)
    value = grade if grade == "-" else (
        f"{grade}  rel {reliability:.0%}  safe {safety:.0%}")
    lw, rw = _width(_LABEL), _width(value)
    total = lw + rw
    color = COLORS[grade]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total:.0f}" height="20" \
role="img" aria-label="{_LABEL}: {value}">
  <title>{_LABEL}: {value}</title>
  <g shape-rendering="crispEdges">
    <rect width="{lw:.0f}" height="20" fill="#2f363d"/>
    <rect x="{lw:.0f}" width="{rw:.0f}" height="20" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lw / 2:.0f}" y="14">{_LABEL}</text>
    <text x="{lw + rw / 2:.0f}" y="14">{value}</text>
  </g>
</svg>
'''
