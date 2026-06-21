"""Event ledger — append-only JSONL plus a human-readable markdown report.

The file is the product: editable and traceable. Nothing here knows about AI;
it only records what the other modules observe.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SMOKE_DIR = ".smoketips"
EVENTS_FILE = "events.jsonl"
REPORT_FILE = "report.md"


@dataclass
class Event:
    """One action by one layer. `layer` is 'orchestrator' or 'delegate'."""
    agent: str
    task: str = ""
    action: str = ""
    layer: str = "delegate"
    tier: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    output_bytes: int = 0
    duration_ms: int = 0
    status: str = "ok"            # ok | error | blocked
    flags: list[str] = field(default_factory=list)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def find_root(start: Optional[Path] = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for parent in [start, *start.parents]:
        if (parent / SMOKE_DIR).is_dir():
            return parent
    return start


def smoke_path(root: Path) -> Path:
    return root / SMOKE_DIR


def ensure(root: Path) -> Path:
    d = smoke_path(root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def events_file(root: Path) -> Path:
    return smoke_path(root) / EVENTS_FILE


def append(root: Path, event: Event) -> Event:
    d = ensure(root)
    with open(d / EVENTS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
    return event


def read_events(root: Path) -> list[Event]:
    f = events_file(root)
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(Event(**json.loads(line)))
    return out


def write_report(root: Path, body: str) -> Path:
    d = ensure(root)
    path = d / REPORT_FILE
    path.write_text(body, encoding="utf-8")
    return path
