---
name: smoketips
description: Observe and govern delegated AI work. Use when an orchestrator delegates a task to a cheaper model or sub-agent and you want the delegation watched, capped, and scored — never run a delegate unwatched. Triggers on "delegate", "sub-agent", "orchestrate", "watch the delegate", "cap output", "block destructive", "score the layers".
license: MIT
metadata:
  author: Abner Machado
  version: "0.1.0"
---

# smokeTIPs — govern what you delegate

You are the orchestrator of a select crew, not a hands-off manager. A delegate
executes; it does not decide what is safe. Watch every delegated layer live,
hold it to the bar, and score it afterward. Where there's smoke, there's a tip.

## Use it on every delegation

1. **Before** the delegate acts, guard the action:
   ```bash
   smoketips check "<the command or output>" --role delegate
   ```
   Exit code 1 ⇒ blocked. Do not run it. A delegate's destructive command, a
   leaked secret, or output over the cap is refused — escalate to the
   orchestrator instead of letting the delegate proceed.

2. **Wrap** the unit of work so it is recorded (traceable, editable):
   ```python
   import smoketips as st
   with st.layer("produtor-haiku", tier="haiku", task="generate tests") as L:
       result = run_delegate(...)
       L.output(result, tokens_out=estimated_tokens)   # measured + guarded
   ```

3. **After** the session, classify the crew:
   ```bash
   smoketips score      # ranked A–F per layer
   smoketips report     # write .smoketips/report.md
   ```

## The bar (assertive by design)

- Delegates may **not** run destructive commands (`rm -rf`, `DROP TABLE`,
  `git push --force`, …). Only the orchestrator, with explicit human OK.
- Output over the cap (default ~8k tokens) is a smell: have the delegate write
  incrementally, not return a wall of text.
- Any secret shape never leaves the boundary.

## What to surface to the human

Flag the things the developer left out — not because they're optional, but
because their absence degrades the tool itself: an uncapped delegate, an
unscored tier, an unguarded destructive path. Report these as a senior reviewer
would, with the fix, not as a linter dumping warnings.

## Companion

Pairs with **Cairn** (records the *why* of decisions) — smokeTIPs records the
*performance* of who executes them. Decisions and execution, both observed.
