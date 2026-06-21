"""Monitor — the live observation side.

Renders the ledger as a per-agent table and can tail it in real time, so the
orchestrator's delegated layers are never running unwatched.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from .ledger import Event, events_file, read_events
from .score import score


def render_table(events: list[Event]) -> str:
    if not events:
        return "no events yet"
    rows = score(events)
    head = f"{'agent':<22}{'tier':<8}{'n':>4}{'rel':>7}{'safe':>7}{'grade':>7}"
    lines = [head, "-" * len(head)]
    for s in rows:
        lines.append(f"{s.agent:<22}{s.tier:<8}{s.events:>4}"
                     f"{s.reliability:>7.2f}{s.safety:>7.2f}{s.grade:>7}")
    blocked = sum(1 for e in events if e.status == "blocked")
    lines.append("")
    lines.append(f"total events: {len(events)}   blocked: {blocked}")
    return "\n".join(lines)


def tail(root: Path, interval: float = 1.0, once: bool = False) -> None:
    """Print the live table, refreshing as new events land."""
    f = events_file(root)
    last_size = -1
    while True:
        size = f.stat().st_size if f.exists() else 0
        if size != last_size:
            last_size = size
            if sys.stdout.isatty():
                print("\033[2J\033[H", end="")  # clear screen for live view
            print(render_table(read_events(root)))
        if once:
            return
        time.sleep(interval)
