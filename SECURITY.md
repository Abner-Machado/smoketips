# Security

## Reporting

Use [private vulnerability reporting](https://github.com/Abner-Machado/smoketips/security/advisories/new)
on this repository, rather than a public issue. No bounty, and no promised response window:
what you get is an honest answer about whether it is real and what happens next.

## What the attack surface actually is

This decides whether a delegated action is allowed to run. The failure that matters is not
a crash, it is a **wrong allow**.

Worth probing, in rough order of how much it would hurt:

- A destructive command a delegate should be blocked from running that comes back
  `allow`. Obfuscation, quoting, encoding, a command split across pieces, a locale trick:
  if the guard reads it as safe and a shell reads it as destructive, that is the bug.
- A policy file that makes the guard load a weaker policy than the one on disk, or skip the
  check entirely rather than refuse to start. `PolicyError` exists so a broken policy stops
  the run instead of silently permitting it.
- Anything that writes to the ledger in a way that corrupts or truncates the record of past
  decisions, since the ledger is the evidence.

The package declares no runtime dependencies and CI checks that claim on every push. `tomli`
is imported behind a try/except as the 3.10 fallback for `tomllib` and is optional.

## What is out of scope

Disagreeing with a policy decision, or with how a role is scored, is an issue rather than a
vulnerability. So is the guard blocking something you believe is safe: that is the design
erring in the direction it was built to err in.
