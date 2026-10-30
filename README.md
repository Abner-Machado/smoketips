<img src="docs/social-preview.png" alt="smokeTIPs" width="100%">

# smokeTIPs

**Observability and governance for AI orchestration.** Watch, score, and govern
the layers an orchestrator delegates to — never run a delegate unwatched.

[![License: MIT](https://img.shields.io/badge/license-MIT-informational.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational.svg)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#status)

> I'm tired of *unassisted* AI performance. When an orchestrator hands work to a
> cheaper model or a sub-agent, nobody is watching live: the delegate blows the
> output cap, reaches for a destructive command, or burns tokens without
> shipping — and you only find out later, in the damage. smokeTIPs makes that
> layer observed, scored, and governed. Where there's smoke, there's a tip.

This isn't only a defense tool. It's **continuous observation** for AI work, and
everything it records is editable and traceable — plain JSONL plus a markdown
report you can read in a pull request.

---

## What it does

- **Guard (defense).** A delegate executes; it does not decide what is safe.
  Destructive commands, leaked secrets, and oversized output are blocked before
  they propagate — assertively, like directing a select crew.
- **Observe (live).** Every delegated action is recorded and rendered as a
  per-agent table you can tail in real time.
- **Score (classify mutual performance).** The ledger is graded A–F per layer on
  reliability, safety, and efficiency, so you can see which tier actually earns
  its tokens.
- **Surface omissions.** It flags what the developer left out — an uncapped
  delegate, an unscored tier, an unguarded path — not because those are optional,
  but because their absence degrades the tool itself.

## Install

Pure Python, no runtime dependencies. Runs on macOS, Linux, and Windows.

```bash
uv tool install git+https://github.com/Abner-Machado/smoketips
# or: pipx install git+https://github.com/Abner-Machado/smoketips
# or, inside a virtualenv: pip install git+https://github.com/Abner-Machado/smoketips
```

Try it once without installing anything:

```bash
uvx --from git+https://github.com/Abner-Machado/smoketips smoketips --help
```

Not on PyPI yet, so `uv tool install smoketips` will not resolve. That shorter
form starts working the day the first release is published.

## Use it

Guard an action (exit code 1 means blocked):

```bash
smoketips check "rm -rf build" --role delegate
# BLOCKED [destructive]: destructive command from a delegate — delegates execute,
# they do not decide what is safe; escalate to the orchestrator
```

Observe a delegated unit of work from Python:

```python
import smoketips as st

with st.layer("produtor-haiku", tier="haiku", task="generate tests") as L:
    result = run_delegate(...)
    decision = L.output(result, tokens_out=estimated_tokens)  # measured + guarded
    if not decision.allow:
        escalate(decision.reason)
```

Then classify the crew:

```bash
smoketips score      # ranked A–F per layer
smoketips report     # write .smoketips/report.md
smoketips tail       # live observation table
```

## CLI

| Command | Purpose |
|---------|---------|
| `check <text>` | judge an action; exit 1 if blocked |
| `emit <agent>` | record an event (for shell agents / CI) |
| `score` | ranked performance of each layer |
| `policy` | show the rules the guard will actually enforce |
| `session start\|current\|end` | group one execution so it can be replayed |
| `replay` | the run, from verdict to full detail (`--level 0..3`) |
| `badge` | write an SVG grade badge |
| `diff --baseline <file>` | compare with a baseline; exit 1 on regression |
| `report` | write `.smoketips/report.md` |
| `tail` / `watch` | live observation table |

Every command answers through its exit code, so a shell agent can branch on it
without parsing text. `diff` is the one built for CI: store `score --json` as a
baseline, and the build fails the moment an agent regresses.

`replay` answers coarsest first. Level 0 is the verdict and the first thing
that went wrong; the evidence opens only when asked:

```bash
smoketips replay --last              # 4 lines: what happened, who broke it
smoketips replay --last --level 1    # one row per agent, worst last
smoketips replay --last --level 2    # the timeline
smoketips replay --last --deep       # every field behind every action
```

`replay` and `score` take `--session <id>` or `--last` to narrow to one run.
Set `SMOKETIPS_SESSION` and every nested call joins that run without writing a
pointer file, which is what a CI job wants:

```bash
export SMOKETIPS_SESSION="ci-$GITHUB_RUN_ID"
smoketips replay --last        # just this run, once it finishes
```

## On-disk format

The file is the product, so nothing is locked to one tool:

```
.smoketips/
├── events.jsonl     # append-only, one action per line — editable, git-diffable
└── report.md        # generated human-readable summary
```

## Companion software

smokeTIPs is meant to be used *alongside* the instruction (the skill) it ships:

- **[Cairn](https://github.com/BjornBigornaDev/cairn)** — records the *why* of
  architecture decisions; smokeTIPs records the *performance* of who executes
  them. Decisions and execution, both observed.
- **MCP hosts** (Claude, Cursor, Cline) — emit the events the ledger consumes.
- **pre-commit / git hooks** — run `smoketips check` before a commit or push.
- **ripgrep** — fast engine for secret scanning at scale.
- **jq** — slice the ledger JSONL in pipelines and CI gates.

## Design notes

- **Assertive toward the delegate, not the orchestrator.** Roles carry different
  bars on purpose.
- **Record, never silently drop.** A blocked action is still logged — that's the
  audit trail.
- **Files over a daemon.** Portable, diffable, reviewable. No service to run.

## Status

Alpha (`0.1`). The format and CLI are tested and usable but may change before
`1.0`. A Rust core for the guard/scorer hot path is on the roadmap, along with a
per-project `.smoketips.toml` policy, adaptive caps, and a performance-regression
CI gate.

These posts exist to **guide and to classify mutual performance**, not to sell.
**Suggestions are welcome** — open an issue or a PR.

## Development

```bash
uv sync
uv run pytest
```

## License

MIT © BjornBigornaDev
