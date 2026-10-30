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


def grade_of(reliability: float, safety: float) -> str:
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
            grade=grade_of(reliability, safety),
        ))
    # Best performers first: grade, then safety, then reliability.
    order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    out.sort(key=lambda s: (order[s.grade], s.safety, s.reliability), reverse=True)
    return out


GRADE_ORDER = {"F": 1, "D": 2, "C": 3, "B": 4, "A": 5}


@dataclass
class Delta:
    """One agent, baseline versus now."""
    agent: str
    old_grade: str          # "-" when the agent is new
    new_grade: str          # "-" when the agent disappeared
    reliability: float      # current minus baseline
    safety: float
    regressed: bool


def from_dicts(rows: list[dict]) -> list[LayerScore]:
    """Rebuild scores from `smoketips score --json` — the baseline a CI gate
    stores next to the code."""
    return [LayerScore(
        agent=r["agent"], tier=r.get("tier", ""), events=int(r.get("events", 0)),
        reliability=float(r.get("reliability", 0.0)),
        safety=float(r.get("safety", 0.0)),
        efficiency=float(r.get("efficiency", 0.0)),
        grade=r.get("grade", "-"),
    ) for r in rows]


def compare(baseline: list[LayerScore], current: list[LayerScore]) -> list[Delta]:
    """Diff two runs per agent. A regression is a dropped grade or less safety —
    an agent that merely appeared is news, not a regression."""
    old = {s.agent: s for s in baseline}
    new = {s.agent: s for s in current}

    out: list[Delta] = []
    for agent in sorted(old | new):
        a, b = old.get(agent), new.get(agent)
        og = a.grade if a else "-"
        ng = b.grade if b else "-"
        d_rel = round((b.reliability if b else 0.0) - (a.reliability if a else 0.0), 3)
        d_safe = round((b.safety if b else 0.0) - (a.safety if a else 0.0), 3)
        regressed = bool(a and b and (
            GRADE_ORDER[ng] < GRADE_ORDER[og] or d_safe < 0))
        out.append(Delta(agent, og, ng, d_rel, d_safe, regressed))
    # Regressions first: a gate should not have to scroll to find the failure.
    out.sort(key=lambda d: (not d.regressed, d.agent))
    return out


def render_diff(deltas: list[Delta]) -> str:
    if not deltas:
        return "nothing to compare"
    head = f"{'agent':<22}{'grade':>12}{'rel':>8}{'safe':>8}"
    lines = [head, "-" * len(head)]
    for d in deltas:
        move = f"{d.old_grade} -> {d.new_grade}"
        mark = "  REGRESSED" if d.regressed else ""
        lines.append(f"{d.agent:<22}{move:>12}{d.reliability:>+8.2f}"
                     f"{d.safety:>+8.2f}{mark}")
    return "\n".join(lines)
