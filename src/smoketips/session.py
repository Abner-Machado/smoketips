"""Session identity — the unit a replay can reproduce.

An event without a session is still a valid event; it just cannot be grouped.
That matters for the ledgers written before this existed: they stay readable,
they simply have nothing to group by.

The id sorts by time, so finding the newest run is a `max()` over strings
rather than parsing dates back out of the ledger.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .ledger import SMOKE_DIR, ensure, find_root

ENV_VAR = "SMOKETIPS_SESSION"
CURRENT_FILE = "CURRENT"


def new_id() -> str:
    """Sortable and short enough to retype: 20261030T034500-a1b2.

    Resolution is one second. The random suffix keeps two sessions opened in
    the same second distinct, but their relative order is then arbitrary —
    sessions are a human-scale unit, so that trade buys a readable id.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def current_file(root: Path) -> Path:
    return root / SMOKE_DIR / CURRENT_FILE


def current(root: Optional[Path] = None, *, create: bool = False) -> str:
    """Resolve the active session: the environment first, then disk.

    The environment wins so that a CI job or a wrapper script can pin every
    nested call to one session without writing to the repo at all. Returns ""
    when there is no session and `create` is False — callers treat that as
    "ungrouped", never as an error.
    """
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return env

    root = root or find_root()
    path = current_file(root)
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value

    return start(root) if create else ""


def start(root: Optional[Path] = None, session: str = "") -> str:
    """Open a session and remember it on disk. Passing `session` adopts an id
    chosen elsewhere, which is how a parent process hands one down."""
    root = root or find_root()
    ensure(root)
    value = session.strip() or new_id()
    current_file(root).write_text(value + "\n", encoding="utf-8")
    return value


def end(root: Optional[Path] = None) -> str:
    """Close the session and return the id that was closed.

    Only the pointer is removed. The events stay in the ledger, which is the
    whole point: a finished session is still replayable.

    A session pinned through the environment outlives this call, because this
    process does not own that variable.
    """
    root = root or find_root()
    path = current_file(root)
    value = ""
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        path.unlink()
    return value


def ids(events) -> list[str]:
    """Every session present in a ledger, oldest first."""
    return sorted({e.session for e in events if e.session})


def latest(events) -> str:
    """The newest session in a ledger, or "" when nothing is grouped."""
    found = ids(events)
    return found[-1] if found else ""
