r"""Project policy — `.smoketips.toml`, versioned next to the code it governs.

The guard's defaults are deliberate, but a repo knows things the defaults don't:
its own destructive commands, a tighter cap, a pattern that is safe here and
nowhere else. The policy file is plain TOML so it reviews like any other file.

    [guard]
    output_cap_bytes = 16384
    extra_destructive = ["\bterraform\s+destroy\b"]
    allow = ["\bgit\s+clean\s+-n"]            # dry-run is not destructive
    extra_secrets = [{ pattern = "\bglpat-[A-Za-z0-9_-]{20,}", name = "gitlab-token" }]
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from .guard import Config
from .ledger import find_root

POLICY_FILE = ".smoketips.toml"

try:  # 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    try:
        import tomli as _toml  # type: ignore[no-redef]
    except ModuleNotFoundError:
        _toml = None  # type: ignore[assignment]

_cache: dict[Path, Config] = {}


class PolicyError(ValueError):
    """The policy file exists but cannot be used. Never guess — say why."""


def policy_path(root: Path) -> Path:
    return root / POLICY_FILE


def _compile_or_die(pattern: str, where: str) -> str:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise PolicyError(f"{where}: invalid regex {pattern!r} — {exc}") from exc
    return pattern


def _str_list(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise PolicyError(f"{where} must be a list of strings")
    return [_compile_or_die(v, where) for v in value]


def from_mapping(data: dict[str, Any]) -> Config:
    """Build a Config from parsed TOML. Unknown keys are an error, not a typo
    that silently does nothing."""
    cfg = Config()
    unknown_top = set(data) - {"guard"}
    if unknown_top:
        raise PolicyError(f"unknown section(s): {', '.join(sorted(unknown_top))}")

    guard = data.get("guard", {})
    if not isinstance(guard, dict):
        raise PolicyError("[guard] must be a table")
    known = {"output_cap_bytes", "extra_destructive", "allow", "extra_secrets"}
    unknown = set(guard) - known
    if unknown:
        raise PolicyError(f"unknown key(s) in [guard]: {', '.join(sorted(unknown))}")

    if "output_cap_bytes" in guard:
        cap = guard["output_cap_bytes"]
        if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
            raise PolicyError("guard.output_cap_bytes must be a positive integer")
        cfg.output_cap_bytes = cap

    if "extra_destructive" in guard:
        cfg.destructive_patterns += _str_list(
            guard["extra_destructive"], "guard.extra_destructive")

    if "allow" in guard:
        cfg.allow_patterns += _str_list(guard["allow"], "guard.allow")

    for entry in guard.get("extra_secrets", []):
        if not isinstance(entry, dict) or set(entry) != {"pattern", "name"}:
            raise PolicyError(
                "each guard.extra_secrets entry needs exactly: pattern, name")
        pat = _compile_or_die(entry["pattern"], "guard.extra_secrets.pattern")
        cfg.secret_patterns.append((pat, str(entry["name"])))

    return cfg


def load_policy(root: Optional[Path] = None, *, use_cache: bool = True) -> Config:
    """Read `.smoketips.toml` from `root`. No file means the defaults apply."""
    root = (root or find_root()).resolve()
    if use_cache and root in _cache:
        return _cache[root]

    path = policy_path(root)
    if not path.exists():
        cfg = Config()
    elif _toml is None:
        raise PolicyError(
            f"{path} needs a TOML reader: Python 3.11+ (tomllib) or `pip install tomli`")
    else:
        try:
            data = _toml.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # tomllib raises TOMLDecodeError
            raise PolicyError(f"{path}: {exc}") from exc
        cfg = from_mapping(data)

    if use_cache:
        _cache[root] = cfg
    return cfg


def clear_cache() -> None:
    _cache.clear()


def describe(cfg: Config) -> str:
    """Human-readable effective policy — what the guard will actually enforce."""
    lines = [
        f"output cap        {cfg.output_cap_bytes} bytes",
        f"destructive rules {len(cfg.destructive_patterns)}",
        f"secret rules      {len(cfg.secret_patterns)}",
        f"allow rules       {len(cfg.allow_patterns)}",
    ]
    if cfg.allow_patterns:
        lines.append("")
        lines.append("allowed despite a destructive match:")
        lines += [f"  {p}" for p in cfg.allow_patterns]
    return "\n".join(lines)
