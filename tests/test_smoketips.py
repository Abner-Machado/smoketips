"""Tests map 1:1 to the verifiable criteria in PROJETO.md section 5."""
from pathlib import Path

import smoketips as st
from smoketips import ledger
from smoketips.guard import Config
from smoketips.score import score


# 2. Defense: a delegate's destructive command is blocked.
def test_delegate_destructive_blocked():
    d = st.guard("rm -rf build", role="delegate")
    assert not d.allow and d.status == "blocked"
    assert "destructive" in d.flags


def test_orchestrator_destructive_flagged_not_silent():
    d = st.guard("git push --force origin main", role="orchestrator")
    assert "destructive" in d.flags  # still surfaced, never silent


# 3. Cap: oversized output is flagged.
def test_output_cap():
    cfg = Config(output_cap_bytes=10)
    d = st.guard("x" * 50, role="delegate", config=cfg)
    assert "over_cap" in d.flags and not d.allow


# 4. Secret: a key shape is detected and blocked.
def test_secret_detected():
    d = st.guard("export KEY=sk-abcdefghijklmnopqrstuvwxyz0123", role="delegate")
    assert "secret" in d.flags and not d.allow


def test_clean_action_allowed():
    d = st.guard("pytest -q", role="delegate")
    assert d.allow and d.status == "allow"


# 1 & 7. Traceable + editable: layer() records one JSONL line.
def test_layer_records_event(tmp_path: Path):
    with st.layer("produtor-haiku", tier="haiku", task="gen tests",
                  root=tmp_path) as L:
        L.output("done", tokens_out=10)
    events = ledger.read_events(tmp_path)
    assert len(events) == 1
    assert events[0].agent == "produtor-haiku"
    assert (tmp_path / ".smoketips" / "events.jsonl").exists()


def test_layer_blocks_bad_output_but_still_records(tmp_path: Path):
    with st.layer("rogue", root=tmp_path) as L:
        d = L.output("rm -rf /")
        assert not d.allow
    events = ledger.read_events(tmp_path)
    assert events[0].status == "blocked"  # recorded, not dropped


# 6. Classification: grades and ranks layers.
def test_score_grades_and_ranks(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="good", tier="opus",
                  status="ok", tokens_out=100, output_bytes=500))
    ledger.append(tmp_path, ledger.Event(agent="bad", tier="haiku",
                  status="error", flags=["destructive"]))
    rows = score(ledger.read_events(tmp_path))
    assert rows[0].agent == "good"      # best ranked first
    assert rows[0].grade == "A"
    assert rows[-1].agent == "bad"
    assert rows[-1].grade == "F"
