"""Score — classify mutual performance of the layers.

Aggregates the ledger per agent into reliability, safety, and efficiency, then
grades A–F so tiers can be compared honestly: which one actually earns its tokens.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ledger import Event


@dataclass
class LayerScore:
    agent: str
    tier: str
    events: int
    reliability: float   # share of non-error actions
    safety: float        # share of actions with no guard flag
    efficiency: float    # useful output bytes per 1k output tokens
    grade: str


def _grade(reliability: float, safety: float) -> str:
    # Safety weighs double — a violation is worse than a flaky result.
    composite = (reliability + 2 * safety) / 3
    for cut, g in ((0.9, "A"), (0.8, "B"), (0.7, "C"), (0.6, "D")):
        if composite >= cut:
            return g
    return "F"


def score(events: list[Event]) -> list[LayerScore]:
    by_agent: dict[str, list[Event]] = {}
    for e in events:
        by_agent.setdefault(e.agent, []).append(e)

    out: list[LayerScore] = []
    for agent, evs in by_agent.items():
        n = len(evs)
        ok = sum(1 for e in evs if e.status != "error")
        clean = sum(1 for e in evs if not e.flags)
        tokens_out = sum(e.tokens_out for e in evs)
        bytes_out = sum(e.output_bytes for e in evs)
        reliability = ok / n
        safety = clean / n
        efficiency = (bytes_out / (tokens_out / 1000)) if tokens_out else 0.0
        out.append(LayerScore(
            agent=agent,
            tier=evs[-1].tier,
            events=n,
            reliability=round(reliability, 3),
            safety=round(safety, 3),
            efficiency=round(efficiency, 1),
            grade=_grade(reliability, safety),
        ))
    # Best performers first: grade, then safety, then reliability.
    order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    out.sort(key=lambda s: (order[s.grade], s.safety, s.reliability), reverse=True)
    return out
