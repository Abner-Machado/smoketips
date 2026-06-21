"""smokeTIPs CLI — for shell agents, CI, and humans.

    smoketips check "rm -rf build" --role delegate   # exit 1 if blocked
    smoketips emit produtor-haiku --task "tests" --status ok
    smoketips score                                   # ranked table
    smoketips report                                  # write report.md
    smoketips tail                                    # live observation
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone

from . import __version__
from .guard import check
from .ledger import Event, append, find_root, read_events, write_report
from .monitor import render_table, tail
from .score import score


def cmd_check(a: argparse.Namespace) -> int:
    d = check(a.text, role=a.role, output_bytes=a.output_bytes)
    if a.json:
        print(json.dumps(asdict(d), ensure_ascii=False))
    else:
        mark = "ALLOW" if d.allow else "BLOCKED"
        flags = f" [{', '.join(d.flags)}]" if d.flags else ""
        print(f"{mark}{flags}: {d.reason}")
    return 0 if d.allow else 1


def cmd_emit(a: argparse.Namespace) -> int:
    e = Event(agent=a.agent, task=a.task or "", action=a.action or "",
              layer=a.role, tier=a.tier or "", tokens_in=a.tokens_in,
              tokens_out=a.tokens_out, output_bytes=a.output_bytes,
              duration_ms=a.duration_ms, status=a.status, flags=a.flag or [])
    append(find_root(), e)
    print(f"recorded {e.agent} ({e.status})")
    return 0


def cmd_score(a: argparse.Namespace) -> int:
    rows = score(read_events(find_root()))
    if a.json:
        print(json.dumps([asdict(r) for r in rows], ensure_ascii=False))
    elif not rows:
        print("no events yet")
    else:
        for r in rows:
            print(f"{r.grade}  {r.agent:<22} rel={r.reliability:.2f} "
                  f"safe={r.safety:.2f} eff={r.efficiency:.0f} (n={r.events})")
    return 0


def _report_body(events) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (f"# smokeTIPs report\n\n_generated {now}_\n\n```\n"
            f"{render_table(events)}\n```\n")


def cmd_report(a: argparse.Namespace) -> int:
    root = find_root()
    path = write_report(root, _report_body(read_events(root)))
    print(f"wrote {path}")
    return 0


def cmd_tail(a: argparse.Namespace) -> int:
    try:
        tail(find_root(), interval=a.interval, once=a.once)
    except KeyboardInterrupt:
        pass
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smoketips",
        description="Observability + governance for AI orchestration.")
    p.add_argument("--version", action="version", version=f"smoketips {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="judge an action (exit 1 if blocked)")
    c.add_argument("text")
    c.add_argument("--role", default="delegate")
    c.add_argument("--output-bytes", type=int, default=0)
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)

    e = sub.add_parser("emit", help="record an event")
    e.add_argument("agent")
    e.add_argument("--task", default="")
    e.add_argument("--action", default="")
    e.add_argument("--role", default="delegate")
    e.add_argument("--tier", default="")
    e.add_argument("--tokens-in", type=int, default=0)
    e.add_argument("--tokens-out", type=int, default=0)
    e.add_argument("--output-bytes", type=int, default=0)
    e.add_argument("--duration-ms", type=int, default=0)
    e.add_argument("--status", default="ok")
    e.add_argument("--flag", action="append")
    e.set_defaults(func=cmd_emit)

    s = sub.add_parser("score", help="ranked performance of each layer")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_score)

    r = sub.add_parser("report", help="write .smoketips/report.md")
    r.set_defaults(func=cmd_report)

    t = sub.add_parser("tail", help="live observation table")
    t.add_argument("--interval", type=float, default=1.0)
    t.add_argument("--once", action="store_true", help="render once and exit")
    t.set_defaults(func=cmd_tail)
    sub.add_parser("watch", help="alias for tail").set_defaults(
        func=cmd_tail, interval=1.0, once=False)

    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
