"""The existing offline Writer is the entry point; this command never writes Tower."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .memory import Memory, Snapshot, evaluate, prepare_pulse, feedback_proposal


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Private NEXO memory and evidence retrieval")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("sync", "context", "search", "dream", "evaluate", "related"):
        p = sub.add_parser(command)
        p.add_argument("tower")
        p.add_argument("cache")
        if command in {"context", "search", "dream", "related"}:
            p.add_argument("--role", required=True)
        if command in {"context", "search"}:
            p.add_argument("--query", required=True)
        if command == "context":
            p.add_argument("--budget", type=int, default=8000)
        if command == "search":
            p.add_argument("--mode", choices=("hybrid", "lexical", "vector"), default="hybrid")
            p.add_argument("--include-inactive", action="store_true")
            p.add_argument("--as-of")
            p.add_argument("-k", type=int, default=8)
        if command == "related":
            p.add_argument("candidate")
        if command == "evaluate":
            p.add_argument("cases")
            p.add_argument("-k", type=int, default=5)
    p = sub.add_parser("feedback")
    p.add_argument("cache")
    p.add_argument("packet")
    p.add_argument("--used", nargs="*", default=[])
    p.add_argument("--outcome", required=True)
    p.add_argument("--evidence", nargs="+", required=True)
    p.add_argument("--proposal-at", help="Export an existing-vocabulary proposal, without applying it")
    p = sub.add_parser("feedback-report")
    p.add_argument("cache")
    args = parser.parse_args(argv)
    memory = Memory(args.cache)
    if args.command == "context":
        output = prepare_pulse(args.tower, args.cache, args.role, args.query, budget_chars=args.budget)
    elif args.command == "feedback":
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        output = memory.record_feedback(packet, args.used, args.outcome, args.evidence)
        if args.proposal_at:
            output = feedback_proposal(output, created_at=args.proposal_at)
    elif args.command == "feedback-report":
        output = memory.feedback_report()
    else:
        snapshot = Snapshot.read(args.tower)
        synced = memory.sync(snapshot)
        if args.command == "sync":
            output = synced
        elif args.command == "dream":
            output = memory.dreams(args.role, expected_revision=snapshot.revision)
        elif args.command == "related":
            output = memory.related_work(json.loads(Path(args.candidate).read_text(encoding="utf-8")),
                                         args.role, expected_revision=snapshot.revision)
        elif args.command == "search":
            output = memory.search(args.query, args.role, expected_revision=snapshot.revision,
                                   include_inactive=args.include_inactive, as_of=args.as_of, k=args.k, mode=args.mode)
        else:
            output = evaluate(memory, json.loads(Path(args.cases).read_text(encoding="utf-8")), k=args.k)
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    return 0
