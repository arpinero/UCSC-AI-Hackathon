"""Command-line interface for the coding-agent coordination bus.

Usage: python -m coordination.cli [--db PATH] [--json] <command> [options]

Database: FORENSICS_COORD_DB (absolute path) or --db. Non-interactive; never
prompts. Exit codes: 0 ok, 2 validation, 3 database unavailable, 4 not found,
5 permission, 6 idempotency conflict, 10 `watch` timed out with no messages.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from typing import Any

from coordination.database import init_database, resolve_db_path
from coordination.models import (
    AGENT_ROLES,
    CoordinationError,
    CoordValidationError,
    Message,
    MessageType,
    Priority,
)
from coordination.service import CoordinationService

EXIT_WATCH_TIMEOUT = 10


def _fmt(msg: Message) -> str:
    branch = f" branch={msg.related_branch}" if msg.related_branch else ""
    commit = f" commit={msg.related_commit}" if msg.related_commit else ""
    return (
        f"[{msg.seq}] {msg.created_at} {msg.message_type} {msg.priority} "
        f"{msg.sender} -> {msg.recipient} status={msg.status}\n"
        f"    id={msg.message_id} corr={msg.correlation_id}{branch}{commit}\n"
        f"    subject: {msg.subject}"
    )


def _fmt_full(msg: Message) -> str:
    return f"{_fmt(msg)}\n    body:\n" + "\n".join("      " + ln for ln in msg.body.splitlines())


def _emit(args: argparse.Namespace, data: Any, text: str) -> None:
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(text)


def _emit_messages(args: argparse.Namespace, msgs: list[Message], full: bool = False) -> None:
    if args.json:
        print(json.dumps([m.to_dict() for m in msgs], indent=2))
    elif not msgs:
        print("(no messages)")
    else:
        print("\n".join((_fmt_full if full else _fmt)(m) for m in msgs))


def _read_body(args: argparse.Namespace) -> str:
    if getattr(args, "body_file", None):
        try:
            with open(args.body_file, encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            raise CoordValidationError(f"cannot read --body-file: {exc}") from exc
    if args.body is None:
        raise CoordValidationError("provide --body or --body-file")
    return str(args.body)


def _service(args: argparse.Namespace) -> CoordinationService:
    return CoordinationService(resolve_db_path(args.db))


# ---- command handlers ------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    info = init_database(resolve_db_path(args.db))
    warn = ""
    if info["network_filesystem"]:
        warn = "\nWARNING: database is on a network filesystem; SQLite locking may be unreliable."
    if info["journal_mode"] != "wal":
        warn += f"\nWARNING: WAL not enabled (journal_mode={info['journal_mode']})."
    _emit(args, info, "\n".join(f"{k}: {v}" for k, v in info.items()) + warn)
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    row = _service(args).register(args.agent, args.role)
    _emit(args, row, f"registered {row['agent_id']} ({row['role']})")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    msg, created = _service(args).send(
        sender=args.sender, recipient=args.recipient, message_type=args.type,
        subject=args.subject, body=_read_body(args), priority=args.priority,
        correlation_id=args.correlation_id, related_branch=args.branch,
        related_commit=args.commit, message_id=args.message_id,
    )
    note = "sent" if created else "duplicate message_id: already stored (no new message)"
    _emit(args, {"created": created, "message": msg.to_dict()}, f"{note}\n{_fmt(msg)}")
    return 0


def cmd_reply(args: argparse.Namespace) -> int:
    msg, created = _service(args).reply(
        to_message_id=args.to, sender=args.sender, body=_read_body(args),
        subject=args.subject, message_type=args.type, priority=args.priority,
        related_branch=args.branch, related_commit=args.commit, message_id=args.message_id,
    )
    note = "replied" if created else "duplicate message_id: already stored (no new message)"
    _emit(args, {"created": created, "message": msg.to_dict()}, f"{note}\n{_fmt(msg)}")
    return 0


def cmd_broadcast(args: argparse.Namespace) -> int:
    msgs = _service(args).broadcast(
        sender=args.sender, subject=args.subject, body=_read_body(args),
        priority=args.priority, message_id=args.message_id,
    )
    _emit(args, [m.to_dict() for m in msgs], f"broadcast to {len(msgs)} agents")
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    msg = _service(args).heartbeat(args.agent, args.note or "")
    _emit(args, msg.to_dict(), f"heartbeat recorded for {args.agent}")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    msgs = _service(args).inbox(args.agent, include_all=args.all, limit=args.limit)
    _emit_messages(args, msgs)
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    msg = _service(args).read(args.message_id, args.agent)
    _emit_messages(args, [msg], full=True)
    return 0


def cmd_ack(args: argparse.Namespace) -> int:
    msg = _service(args).acknowledge(args.message_id, args.agent)
    _emit(args, msg.to_dict(), f"acknowledged\n{_fmt(msg)}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    msg = _service(args).resolve(args.message_id, args.agent)
    _emit(args, msg.to_dict(), f"resolved\n{_fmt(msg)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    info = _service(args).status()
    lines = [
        f"db: {info['db_path']}  journal_mode={info['journal_mode']}  "
        f"schema={info['schema_version']}  total_messages={info['total_messages']}",
        f"{'agent':<20} {'pend':>4} {'read':>4} {'ack':>4} {'res':>4}  last_heartbeat",
    ]
    for a in info["agents"]:
        lines.append(
            f"{a['agent_id']:<20} {a['pending']:>4} {a['read']:>4} {a['acknowledged']:>4} "
            f"{a['resolved']:>4}  {a['last_heartbeat_at'] or '-'}"
        )
    _emit(args, info, "\n".join(lines))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    msgs = _service(args).history(
        agent_id=args.agent, sender=args.sender, recipient=args.recipient,
        correlation_id=args.correlation_id, message_type=args.type,
        after_seq=args.after_seq, limit=args.limit,
    )
    _emit_messages(args, msgs, full=args.full)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Bounded polling: exit 0 as soon as unread messages exist, 10 on timeout."""
    if args.timeout < 0 or args.interval <= 0:
        raise CoordValidationError("--timeout must be >= 0 and --interval > 0")
    service = _service(args)
    deadline = time.monotonic() + args.timeout
    while True:
        msgs = service.inbox(args.agent, limit=args.limit)
        if msgs:
            _emit_messages(args, msgs)
            return 0
        if time.monotonic() >= deadline:
            _emit(args, [], f"(no new messages for {args.agent} after {args.timeout:g}s)")
            return EXIT_WATCH_TIMEOUT
        time.sleep(min(args.interval, max(0.0, deadline - time.monotonic())))


_AGENTS = sorted(AGENT_ROLES)
_TYPES = [t.value for t in MessageType]
_PRIOS = [p.value for p in Priority]


def _content_args(p: argparse.ArgumentParser, *, subject_required: bool) -> None:
    p.add_argument("--subject", required=subject_required, help="short subject (<=200 chars)")
    p.add_argument("--body", help="message body (JSON object for structured types)")
    p.add_argument("--body-file", help="read body from this file instead of --body")
    p.add_argument("--priority", default="NORMAL", choices=_PRIOS)
    p.add_argument("--message-id", help="idempotency key: retrying with the same id is a no-op")


def _add_send_parsers(sub: Any) -> None:
    p = sub.add_parser("send", help="send a message")
    p.add_argument("--sender", required=True)
    p.add_argument("--recipient", required=True)
    p.add_argument("--type", required=True, help=f"one of: {', '.join(_TYPES)}")
    p.add_argument("--correlation-id")
    p.add_argument("--branch", help="related git branch")
    p.add_argument("--commit", help="related git commit SHA (7-40 hex)")
    _content_args(p, subject_required=True)

    p = sub.add_parser("reply", help="reply to a message (inherits its correlation id)")
    p.add_argument("--sender", required=True)
    p.add_argument("--to", required=True, help="message_id being answered")
    p.add_argument("--type", default="RESPONSE", help="default RESPONSE")
    p.add_argument("--branch")
    p.add_argument("--commit")
    _content_args(p, subject_required=False)

    p = sub.add_parser("broadcast", help="announce to all other agents")
    p.add_argument("--sender", required=True)
    _content_args(p, subject_required=True)

    p = sub.add_parser("heartbeat", help="record liveness and notify the coordinator")
    p.add_argument("--agent", required=True)
    p.add_argument("--note", help="what you are doing / recent progress")


def _add_read_parsers(sub: Any) -> None:
    p = sub.add_parser("inbox", help="list messages addressed to an agent (unread by default)")
    p.add_argument("--agent", required=True)
    p.add_argument("--all", action="store_true", help="include READ/ACKNOWLEDGED/RESOLVED")
    p.add_argument("--limit", type=int, default=50)

    for name, helptext in (
        ("read", "show a message in full (PENDING -> READ for the recipient)"),
        ("ack", "acknowledge a message (recipient only)"),
        ("resolve", "mark a message RESOLVED"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--agent", required=True)
        p.add_argument("--message-id", required=True)

    sub.add_parser("status", help="bus summary: per-agent counts and heartbeats")

    p = sub.add_parser("history", help="query message history in send order")
    p.add_argument("--agent", help="messages sent OR received by this agent")
    p.add_argument("--sender")
    p.add_argument("--recipient")
    p.add_argument("--correlation-id")
    p.add_argument("--type")
    p.add_argument("--after-seq", type=int, default=0)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--full", action="store_true", help="include message bodies")

    p = sub.add_parser("watch", help="bounded poll for unread messages (exit 10 on timeout)")
    p.add_argument("--agent", required=True)
    p.add_argument("--timeout", type=float, default=30.0, help="seconds, default 30")
    p.add_argument("--interval", type=float, default=1.0, help="poll seconds, default 1")
    p.add_argument("--limit", type=int, default=50)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m coordination.cli",
        description="Coding-agent coordination bus (SQLite). Set FORENSICS_COORD_DB.",
    )
    parser.add_argument("--db", help="absolute database path (default: $FORENSICS_COORD_DB)")
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create the database, enable WAL, register the 7 identities")
    p = sub.add_parser("register", help="(re)register an agent identity")
    p.add_argument("--agent", required=True, choices=_AGENTS)
    p.add_argument("--role", help="override the role description")
    _add_send_parsers(sub)
    _add_read_parsers(sub)
    return parser


HANDLERS = {
    "init": cmd_init,
    "register": cmd_register,
    "send": cmd_send,
    "reply": cmd_reply,
    "broadcast": cmd_broadcast,
    "heartbeat": cmd_heartbeat,
    "inbox": cmd_inbox,
    "read": cmd_read,
    "ack": cmd_ack,
    "resolve": cmd_resolve,
    "status": cmd_status,
    "history": cmd_history,
    "watch": cmd_watch,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except CoordinationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
