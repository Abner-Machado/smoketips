"""Client — the ergonomic API the orchestrator (or its skill) uses.

    import smoketips as st

    # check before letting a delegate act
    d = st.guard("rm -rf build", role="delegate")
    if not d.allow:
        raise RuntimeError(d.reason)

    # observe a delegated unit of work
    with st.layer("produtor-haiku", tier="haiku", task="gen tests") as L:
        ...                       # do the work
        L.output(some_text)       # measured + guarded automatically
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .guard import Config, Decision, check
from .ledger import Event, append, find_root
from .policy import load_policy
from .session import current as current_session


def guard(text: str = "", *, role: str = "delegate", output_bytes: int = 0,
          config: Config | None = None, root: Optional[Path] = None) -> Decision:
    """Judge an action without recording it.

    With no explicit config the project's `.smoketips.toml` applies, so the repo
    governs itself instead of every caller re-stating the rules.
    """
    return check(text, role=role, output_bytes=output_bytes,
                 config=config or load_policy(root))


def emit(event: Event, root: Optional[Path] = None) -> Event:
    """Append a fully-formed event to the ledger.

    An event that does not name a session inherits the active one, so grouping
    costs the caller nothing.
    """
    where = root or find_root()
    if not event.session:
        event.session = current_session(where)
    return append(where, event)


class layer:
    """Context manager that times a delegated unit of work and records it.

    Output passed to `.output()` is guarded; a violation marks the event blocked
    and surfaces the reason, but never silently drops it (traceable).
    """

    def __init__(self, agent: str, *, tier: str = "", task: str = "",
                 role: str = "delegate", root: Optional[Path] = None,
                 config: Config | None = None, session: str = ""):
        # Resolved on entry, not on exit: the work belongs to the session it
        # started in, even if the pointer moves while it runs.
        self.event = Event(agent=agent, tier=tier, task=task, layer=role,
                           session=session or current_session(root))
        self.role = role
        self.root = root
        self.config = config
        self._start = 0.0

    def __enter__(self) -> "layer":
        self._start = time.perf_counter()
        return self

    def output(self, text: str, tokens_out: int = 0) -> Decision:
        size = len(text.encode("utf-8"))
        self.event.output_bytes += size
        self.event.tokens_out += tokens_out
        cfg = self.config or load_policy(self.root)
        d = check(text, role=self.role, output_bytes=size, config=cfg)
        for f in d.flags:
            if f not in self.event.flags:
                self.event.flags.append(f)
        if not d.allow:
            self.event.status = "blocked"
        return d

    def action(self, name: str) -> None:
        self.event.action = name

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.event.duration_ms = int((time.perf_counter() - self._start) * 1000)
        if exc_type is not None and self.event.status != "blocked":
            self.event.status = "error"
        emit(self.event, self.root)
        return False  # never swallow exceptions
