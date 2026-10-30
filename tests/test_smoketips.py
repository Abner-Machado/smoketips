"""Tests map 1:1 to the verifiable criteria in PROJETO.md section 5."""
import json
from pathlib import Path

import pytest

import smoketips as st
from smoketips import ledger, policy, replay, session
# `smoketips.badge` the name is the exported function, so reach for the module.
from smoketips.badge import render as render_badge
from smoketips.cli import main
from smoketips.guard import Config
from smoketips.policy import PolicyError
from smoketips.score import compare, from_dicts, score


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


# --- policy: the repo governs itself --------------------------------------

ALLOW_RM_BUILD = r"""
[guard]
allow = ['\brm\s+-rf\s+build\b']
"""


def _policy(tmp_path: Path, body: str):
    (tmp_path / ".smoketips").mkdir(exist_ok=True)
    (tmp_path / ".smoketips.toml").write_text(body, encoding="utf-8")
    policy.clear_cache()
    return policy.load_policy(tmp_path)


def test_policy_file_tightens_the_cap(tmp_path: Path):
    cfg = _policy(tmp_path, "[guard]\noutput_cap_bytes = 10\n")
    assert cfg.output_cap_bytes == 10


def test_no_policy_file_means_the_defaults_apply(tmp_path: Path):
    (tmp_path / ".smoketips").mkdir(exist_ok=True)
    policy.clear_cache()
    cfg = policy.load_policy(tmp_path)
    assert cfg.output_cap_bytes == Config().output_cap_bytes
    assert cfg.allow_patterns == []


def test_policy_allow_forgives_destructive_but_never_a_secret(tmp_path: Path):
    cfg = _policy(tmp_path, ALLOW_RM_BUILD)
    assert st.guard("rm -rf build", role="delegate", config=cfg).allow
    leak = st.guard("rm -rf build; export KEY=sk-abcdefghijklmnopqrstuvwxyz0123",
                    role="delegate", config=cfg)
    assert not leak.allow and "secret" in leak.flags


def test_policy_extra_destructive_is_enforced(tmp_path: Path):
    cfg = _policy(tmp_path, "[guard]\nextra_destructive = ['\\bmkfs\\b']\n")
    assert not st.guard("mkfs /dev/sda1", role="delegate", config=cfg).allow


def test_broken_policy_names_the_offending_key(tmp_path: Path):
    with pytest.raises(PolicyError) as err:
        _policy(tmp_path, "[guard]\nallow = ['[unclosed']\n")
    assert "guard.allow" in str(err.value)


# --- badge: a grade anyone can see ----------------------------------------

def test_badge_is_svg_carrying_the_grade(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="good", status="ok"))
    svg = render_badge(ledger.read_events(tmp_path))
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "smokeTIPs" in svg


def test_badge_handles_an_empty_ledger():
    assert render_badge([]).startswith("<svg")


# --- replay: the audit transcript -----------------------------------------

def test_replay_filters_and_orders_chronologically(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="a", task="first", status="ok"))
    ledger.append(tmp_path, ledger.Event(agent="b", task="other", status="ok"))
    ledger.append(tmp_path, ledger.Event(agent="a", task="second",
                                         status="blocked",
                                         flags=["destructive"]))
    events = ledger.read_events(tmp_path)
    assert len(replay.select(events, agent="a")) == 2
    assert len(replay.select(events, flag="destructive")) == 1
    assert len(replay.select(events, status="blocked")) == 1
    text = replay.render(replay.select(events, agent="a"))
    assert text.index("first") < text.index("second")


def test_replay_says_so_when_there_is_nothing():
    assert replay.render([]) == "nothing to replay"


# --- diff: the CI gate ----------------------------------------------------

def test_compare_flags_a_dropped_grade_as_regression(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="x", status="ok"))
    base = score(ledger.read_events(tmp_path))
    ledger.append(tmp_path, ledger.Event(agent="x", status="blocked",
                                         flags=["destructive"]))
    deltas = compare(base, score(ledger.read_events(tmp_path)))
    assert deltas[0].agent == "x" and deltas[0].regressed
    assert deltas[0].safety < 0


def test_a_brand_new_agent_is_news_not_a_regression(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="newcomer", status="ok"))
    deltas = compare([], score(ledger.read_events(tmp_path)))
    assert deltas[0].old_grade == "-" and not deltas[0].regressed


def test_from_dicts_round_trips_score_json(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="x", status="ok"))
    rows = score(ledger.read_events(tmp_path))
    rebuilt = from_dicts(json.loads(json.dumps([r.__dict__ for r in rows])))
    assert rebuilt[0].agent == "x" and rebuilt[0].grade == rows[0].grade


# --- cli: the exit code is the contract a shell agent reads ---------------

def _cli_sandbox(tmp_path: Path, monkeypatch):
    (tmp_path / ".smoketips").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)
    policy.clear_cache()


def test_cli_check_exits_1_when_blocked(tmp_path: Path, monkeypatch):
    _cli_sandbox(tmp_path, monkeypatch)
    assert main(["check", "rm -rf /", "--no-policy"]) == 1
    assert main(["check", "pytest -q", "--no-policy"]) == 0


def test_cli_check_obeys_the_project_policy(tmp_path: Path, monkeypatch):
    _cli_sandbox(tmp_path, monkeypatch)
    (tmp_path / ".smoketips.toml").write_text(ALLOW_RM_BUILD, encoding="utf-8")
    policy.clear_cache()
    assert main(["check", "rm -rf build"]) == 0
    assert main(["check", "rm -rf build", "--no-policy"]) == 1


def test_cli_reports_a_broken_policy_instead_of_crashing(tmp_path: Path,
                                                         monkeypatch, capsys):
    _cli_sandbox(tmp_path, monkeypatch)
    (tmp_path / ".smoketips.toml").write_text("[guard]\nallow = ['[bad']\n",
                                              encoding="utf-8")
    policy.clear_cache()
    assert main(["policy"]) == 2
    assert "policy error" in capsys.readouterr().err


def test_cli_diff_gates_on_regression(tmp_path: Path, monkeypatch, capsys):
    _cli_sandbox(tmp_path, monkeypatch)
    ledger.append(tmp_path, ledger.Event(agent="x", status="ok"))
    assert main(["score", "--json"]) == 0
    (tmp_path / "base.json").write_text(capsys.readouterr().out,
                                        encoding="utf-8")

    assert main(["diff", "--baseline", "base.json"]) == 0      # nothing moved
    ledger.append(tmp_path, ledger.Event(agent="x", status="blocked",
                                         flags=["destructive"]))
    assert main(["diff", "--baseline", "base.json"]) == 1      # gate trips


def test_cli_badge_writes_a_file(tmp_path: Path, monkeypatch):
    _cli_sandbox(tmp_path, monkeypatch)
    ledger.append(tmp_path, ledger.Event(agent="x", status="ok"))
    assert main(["badge"]) == 0
    assert (tmp_path / ".smoketips" / "badge.svg").read_text(
        encoding="utf-8").startswith("<svg")


def test_cli_replay_runs_on_an_empty_ledger(tmp_path: Path, monkeypatch,
                                            capsys):
    _cli_sandbox(tmp_path, monkeypatch)
    assert main(["replay"]) == 0
    assert "nothing to replay" in capsys.readouterr().out


# --- session: the unit a replay can reproduce -----------------------------

def test_session_id_sorts_by_time():
    # Resolution is one second; the suffix only breaks ties within a second,
    # so ordering is asserted across distinct timestamps.
    stamp, suffix = session.new_id().split("-")
    assert len(stamp) == 15 and stamp[8] == "T"
    assert len(suffix) == 4
    assert sorted(["20260202T000000-zzzz", "20260101T000000-aaaa"])[0] \
        == "20260101T000000-aaaa"


def test_session_start_current_end(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    (tmp_path / ".smoketips").mkdir()
    assert session.current(tmp_path) == ""        # nothing open yet
    opened = session.start(tmp_path)
    assert session.current(tmp_path) == opened
    assert session.end(tmp_path) == opened
    assert session.current(tmp_path) == ""        # pointer gone


def test_environment_beats_the_file(tmp_path: Path, monkeypatch):
    (tmp_path / ".smoketips").mkdir()
    session.start(tmp_path, "from-disk")
    monkeypatch.setenv(session.ENV_VAR, "from-env")
    assert session.current(tmp_path) == "from-env"


def test_ending_a_session_keeps_its_events(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    (tmp_path / ".smoketips").mkdir()
    opened = session.start(tmp_path)
    st.emit(ledger.Event(agent="x", status="ok"), tmp_path)
    session.end(tmp_path)
    events = ledger.read_events(tmp_path)
    assert events[0].session == opened            # replayable after the fact


def test_emit_inherits_the_active_session(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    (tmp_path / ".smoketips").mkdir()
    opened = session.start(tmp_path)
    st.emit(ledger.Event(agent="x", status="ok"), tmp_path)
    assert ledger.read_events(tmp_path)[0].session == opened


def test_an_explicit_session_is_not_overridden(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    (tmp_path / ".smoketips").mkdir()
    session.start(tmp_path)
    st.emit(ledger.Event(agent="x", status="ok", session="mine"), tmp_path)
    assert ledger.read_events(tmp_path)[0].session == "mine"


def test_layer_stamps_the_session(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    (tmp_path / ".smoketips").mkdir()
    opened = session.start(tmp_path)
    with st.layer("produtor-haiku", root=tmp_path) as L:
        L.output("done")
    assert ledger.read_events(tmp_path)[0].session == opened


def test_replay_and_score_isolate_one_session(tmp_path: Path):
    ledger.append(tmp_path, ledger.Event(agent="a", status="ok", session="s1"))
    ledger.append(tmp_path, ledger.Event(agent="b", status="ok", session="s2"))
    events = ledger.read_events(tmp_path)
    assert len(replay.select(events, session="s1")) == 1
    assert session.latest(events) == "s2"
    assert session.ids(events) == ["s1", "s2"]


# A ledger is a file on disk that outlives any one version of this tool.
def test_a_ledger_without_sessions_still_reads(tmp_path: Path):
    d = tmp_path / ".smoketips"
    d.mkdir()
    (d / "events.jsonl").write_text(
        '{"agent": "old", "status": "ok", "ts": "2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8")
    events = ledger.read_events(tmp_path)
    assert events[0].agent == "old" and events[0].session == ""


def test_an_unknown_field_is_ignored_not_fatal(tmp_path: Path):
    d = tmp_path / ".smoketips"
    d.mkdir()
    (d / "events.jsonl").write_text(
        '{"agent": "future", "status": "ok", "invented_later": 42}\n',
        encoding="utf-8")
    assert ledger.read_events(tmp_path)[0].agent == "future"


def test_cli_session_round_trip(tmp_path: Path, monkeypatch, capsys):
    _cli_sandbox(tmp_path, monkeypatch)
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    assert main(["session"]) == 1                  # nothing open
    assert "no session" in capsys.readouterr().out

    assert main(["session", "start", "--id", "run-7"]) == 0
    capsys.readouterr()
    assert main(["session"]) == 0
    assert capsys.readouterr().out.strip() == "run-7"

    assert main(["emit", "haiku", "--status", "ok"]) == 0
    assert "run-7" in capsys.readouterr().out
    assert ledger.read_events(tmp_path)[0].session == "run-7"


# --- replay levels: verdict first, evidence on request --------------------

def _busy_session(tmp_path: Path) -> list:
    ledger.append(tmp_path, ledger.Event(agent="haiku", task="scaffold",
                                         status="ok", session="s1"))
    ledger.append(tmp_path, ledger.Event(agent="haiku", task="fixtures",
                                         status="ok", session="s1"))
    ledger.append(tmp_path, ledger.Event(agent="sonnet", task="refactor",
                                         action="rm -rf build", status="blocked",
                                         flags=["destructive"], session="s1"))
    ledger.append(tmp_path, ledger.Event(agent="sonnet", task="retry",
                                         status="error", session="s1"))
    return ledger.read_events(tmp_path)


def test_level_zero_names_the_first_failure(tmp_path: Path):
    text = replay.summary(_busy_session(tmp_path))
    assert "blocked 1" in text and "errors 1" in text
    assert "2 agents" in text and "4 actions" in text
    assert "first blocked: sonnet" in text
    assert "destructive" in text


def test_level_zero_is_far_smaller_than_the_full_detail(tmp_path: Path):
    events = _busy_session(tmp_path)
    assert len(replay.summary(events)) * 3 < len(replay.detail(events))


def test_level_one_ranks_the_worst_agent_first(tmp_path: Path):
    text = replay.by_agent(_busy_session(tmp_path))
    rows = [ln for ln in text.splitlines()[2:] if ln.strip()]
    assert rows[-1].startswith("sonnet")       # worst sinks to the bottom
    assert rows[0].startswith("haiku")


def test_every_level_survives_an_empty_ledger():
    for lvl in range(replay.MAX_LEVEL + 1):
        assert replay.render_level([], lvl) == "nothing to replay"


def test_an_out_of_range_level_clamps(tmp_path: Path):
    events = _busy_session(tmp_path)
    assert replay.render_level(events, 99) == replay.detail(events)
    assert replay.render_level(events, -5) == replay.summary(events)


def test_cli_replay_defaults_to_the_verdict(tmp_path: Path, monkeypatch,
                                            capsys):
    _cli_sandbox(tmp_path, monkeypatch)
    _busy_session(tmp_path)
    capsys.readouterr()

    assert main(["replay"]) == 0
    short = capsys.readouterr().out
    assert "first blocked" in short
    assert "scaffold" not in short            # the timeline stays closed

    assert main(["replay", "--level", "2"]) == 0
    assert "scaffold" in capsys.readouterr().out

    assert main(["replay", "--deep"]) == 0
    assert "layer=delegate" in capsys.readouterr().out


def test_cli_last_narrows_to_the_newest_session(tmp_path: Path, monkeypatch,
                                                capsys):
    _cli_sandbox(tmp_path, monkeypatch)
    monkeypatch.delenv(session.ENV_VAR, raising=False)
    ledger.append(tmp_path, ledger.Event(agent="older", status="ok",
                                         session="20260101T000000-aaaa"))
    ledger.append(tmp_path, ledger.Event(agent="newer", status="ok",
                                         session="20260202T000000-bbbb"))
    capsys.readouterr()
    assert main(["replay", "--last"]) == 0
    out = capsys.readouterr().out
    assert "newer" in out and "older" not in out
