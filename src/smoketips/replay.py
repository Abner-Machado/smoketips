"""Replay — walk a past session back, in order, for an audit.

The ledger is append-only, so a session can be reconstructed exactly as it
happened: who acted, when, how long it took, what the guard said. This is the
answer to "what did the delegate actually do at 02:14?".
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from .ledger import Event


def _parsed(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def select(events: Iterable[Event], *, agent: str = "", status: str = "",
           flag: str = "", session: str = "") -> list[Event]:
    """Filter a session down to what is being audited."""
    out = list(events)
    if session:
        out = [e for e in out if e.session == session]
    if agent:
        out = [e for e in out if e.agent == agent]
    if status:
        out = [e for e in out if e.status == status]
    if flag:
        out = [e for e in out if flag in e.flags]
    return sorted(out, key=lambda e: e.ts)


def render(events: list[Event]) -> str:
    """Chronological transcript with the gap between actions made visible —
    a long silence before a blocked action is itself evidence."""
    if not events:
        return "nothing to replay"

    lines = []
    previous: Optional[datetime] = None
    for e in events:
        when = _parsed(e.ts)
        gap = ""
        if when and previous:
            delta = (when - previous).total_seconds()
            if delta >= 1:
                gap = f"  (+{delta:.0f}s)"
        previous = when or previous

        clock = when.strftime("%H:%M:%S") if when else e.ts[:8] or "--:--:--"
        mark = {"ok": " ", "error": "!", "blocked": "x"}.get(e.status, "?")
        head = f"{clock} {mark} {e.agent}"
        if e.tier:
            head += f" [{e.tier}]"
        detail = " · ".join(p for p in (e.task, e.action) if p)
        if detail:
            head += f" — {detail}"
        if e.duration_ms:
            head += f" ({e.duration_ms} ms)"
        lines.append(head + gap)
        if e.flags:
            lines.append(f"{'':>11}flags: {', '.join(e.flags)}")

    blocked = sum(1 for e in events if e.status == "blocked")
    errors = sum(1 for e in events if e.status == "error")
    lines.append("")
    lines.append(f"{len(events)} actions   blocked: {blocked}   errors: {errors}")
    return "\n".join(lines)
