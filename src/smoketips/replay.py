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


# --- coarse to fine -------------------------------------------------------
#
# A reader should get the verdict before the evidence. Level 0 answers "did
# anything go wrong?" in three lines; each level after that is opened on
# purpose, not dumped by default.

LEVELS = {0: "verdict", 1: "per agent", 2: "timeline", 3: "detail"}
MAX_LEVEL = max(LEVELS)


def _window(events: list[Event]) -> str:
    """Clock span of the run, when the timestamps can be read."""
    stamps = [t for t in (_parsed(e.ts) for e in events) if t]
    if not stamps:
        return ""
    first, last = min(stamps), max(stamps)
    span = (last - first).total_seconds()
    shown = f"{first:%H:%M:%S} to {last:%H:%M:%S}"
    return f"{shown} ({span:.0f}s)" if span >= 1 else shown


def summary(events: list[Event]) -> str:
    """Level 0 — the verdict, and the first thing that bit you."""
    if not events:
        return "nothing to replay"

    from .score import score  # local: keeps the import graph shallow

    blocked = [e for e in events if e.status == "blocked"]
    errors = [e for e in events if e.status == "error"]
    agents = {e.agent for e in events}
    rows = score(events)
    worst = min(rows, key=lambda r: "FDCBA".index(r.grade)) if rows else None

    sessions = {e.session for e in events if e.session}
    head = sessions.pop() if len(sessions) == 1 else f"{len(sessions)} sessions"
    window = _window(events)

    lines = [f"{head or 'ungrouped'}   {window}".rstrip()]
    tally = (f"{len(events)} actions · {len(agents)} agents · "
             f"blocked {len(blocked)} · errors {len(errors)}")
    if worst:
        tally += f" · worst {worst.grade} ({worst.agent})"
    lines.append(tally)

    # Surface the first failure, because that is the one that explains the rest.
    first_bad = (blocked + errors)
    if first_bad:
        e = sorted(first_bad, key=lambda x: x.ts)[0]
        why = f" [{', '.join(e.flags)}]" if e.flags else ""
        what = " · ".join(p for p in (e.task, e.action) if p) or e.status
        lines.append(f"first {e.status}: {e.agent} — {what}{why}")

    if len(events) > 1:
        lines.append(f"open with --level 1 of {MAX_LEVEL}")
    return "\n".join(lines)


def by_agent(events: list[Event]) -> str:
    """Level 1 — one row per agent, worst first."""
    if not events:
        return "nothing to replay"

    from .score import score

    head = f"{'agent':<22}{'n':>4}{'ok':>5}{'blocked':>9}{'errors':>8}{'grade':>7}"
    lines = [head, "-" * len(head)]
    for row in score(events):
        mine = [e for e in events if e.agent == row.agent]
        ok = sum(1 for e in mine if e.status == "ok")
        blocked = sum(1 for e in mine if e.status == "blocked")
        errors = sum(1 for e in mine if e.status == "error")
        lines.append(f"{row.agent:<22}{len(mine):>4}{ok:>5}"
                     f"{blocked:>9}{errors:>8}{row.grade:>7}")
    return "\n".join(lines)


def detail(events: list[Event]) -> str:
    """Level 3 — the timeline plus the numbers behind each action."""
    if not events:
        return "nothing to replay"

    lines = []
    for e in events:
        when = _parsed(e.ts)
        clock = when.strftime("%H:%M:%S") if when else e.ts[:8] or "--:--:--"
        mark = {"ok": " ", "error": "!", "blocked": "x"}.get(e.status, "?")
        what = " · ".join(p for p in (e.task, e.action) if p)
        lines.append(f"{clock} {mark} {e.agent}" + (f" — {what}" if what else ""))

        facts = [f"status={e.status}", f"layer={e.layer}"]
        if e.tier:
            facts.append(f"tier={e.tier}")
        if e.tokens_in or e.tokens_out:
            facts.append(f"tokens={e.tokens_in}/{e.tokens_out}")
        if e.output_bytes:
            facts.append(f"bytes={e.output_bytes}")
        if e.duration_ms:
            facts.append(f"{e.duration_ms}ms")
        if e.flags:
            facts.append(f"flags={','.join(e.flags)}")
        if e.session:
            facts.append(f"session={e.session}")
        lines.append(f"{'':>11}{'  '.join(facts)}")
        lines.append(f"{'':>11}ts={e.ts}")
    return "\n".join(lines)


def render_level(events: list[Event], level: int = 0) -> str:
    """Dispatch to one depth. Out-of-range clamps rather than raising: a
    reader asking for more detail than exists wants the most there is."""
    level = max(0, min(int(level), MAX_LEVEL))
    if level == 0:
        return summary(events)
    if level == 1:
        return by_agent(events)
    if level == 2:
        return render(events)
    return detail(events)
