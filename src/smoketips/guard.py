"""Guard — the defense side. Assertive toward the delegate by design.

A delegate executes; it does not get to decide what is dangerous. Destructive
commands, oversized output, and leaked secrets are blocked before they propagate.
Rules are plain data so a project can edit them (`.smoketips.toml` is a future
update; for now override `Config` in code).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Default output cap. ~8k tokens of text; the delegate must not return a wall
# of output that blows the orchestrator's context window.
DEFAULT_OUTPUT_CAP_BYTES = 32_768

# Commands a delegate may never run on its own.
DESTRUCTIVE_PATTERNS = [
    r"\brm\s+-[a-z]*r[a-z]*f", r"\brm\s+-[a-z]*f[a-z]*r",
    r"\brmdir\s+/s", r"\bdel\s+/[a-z]", r"\bformat\s+[a-z]:",
    r"\bmkfs\b", r"\bdd\s+if=", r">\s*/dev/sd",
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", r"\bTRUNCATE\s+TABLE\b",
    r"\bgit\s+push\s+.*(--force|-f)\b", r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-z]*f", r"\bshutdown\b", r"\breboot\b",
    r":\(\)\s*\{",  # fork bomb
]

# Secret shapes that must never pass through.
SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "aws-access-key"),
    (r"\bsk-[A-Za-z0-9]{20,}", "openai-key"),
    (r"\bgh[oprsu]_[A-Za-z0-9]{30,}", "github-token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private-key"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "slack-token"),
]


@dataclass
class Config:
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES
    destructive_patterns: list[str] = field(
        default_factory=lambda: list(DESTRUCTIVE_PATTERNS))
    secret_patterns: list[tuple[str, str]] = field(
        default_factory=lambda: list(SECRET_PATTERNS))
    # Escape hatch for a repo whose own commands look destructive but aren't
    # (a dry run, a scratch path). Checked before the destructive rules; it
    # never excuses a secret or an oversized output.
    allow_patterns: list[str] = field(default_factory=list)


@dataclass
class Decision:
    allow: bool
    status: str          # allow | blocked
    flags: list[str]
    reason: str


def _is_delegate(role: str) -> bool:
    return role.lower() == "delegate"


def check(text: str = "", *, role: str = "delegate", output_bytes: int = 0,
          config: Config | None = None) -> Decision:
    """Judge an action. `text` is the command or the output to inspect.

    A delegate is held to a stricter bar than an orchestrator: it may not run
    destructive commands at all. Anyone leaking a secret or busting the cap is
    blocked regardless of role.
    """
    cfg = config or Config()
    flags: list[str] = []
    reasons: list[str] = []

    allowed = any(re.search(p, text, re.IGNORECASE) for p in cfg.allow_patterns)

    for pat in (() if allowed else cfg.destructive_patterns):
        if re.search(pat, text, re.IGNORECASE):
            flags.append("destructive")
            if _is_delegate(role):
                reasons.append(
                    "destructive command from a delegate — delegates execute, "
                    "they do not decide what is safe; escalate to the orchestrator")
            else:
                reasons.append("destructive command — requires explicit confirmation")
            break

    for pat, name in cfg.secret_patterns:
        if re.search(pat, text):
            flags.append("secret")
            reasons.append(f"secret detected ({name}) — must not leave the boundary")
            break

    size = output_bytes or len(text.encode("utf-8"))
    if size > cfg.output_cap_bytes:
        flags.append("over_cap")
        reasons.append(
            f"output {size} bytes exceeds cap {cfg.output_cap_bytes} — write "
            "incrementally instead of returning one wall of text")

    blocked = bool(flags)
    return Decision(
        allow=not blocked,
        status="blocked" if blocked else "allow",
        flags=flags,
        reason="; ".join(reasons) if reasons else "ok",
    )
