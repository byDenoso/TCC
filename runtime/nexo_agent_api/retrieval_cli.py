"""Local NEXO evidence CLI and authenticated MCP sidecar."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .memory import Snapshot, SourceError, feedback_proposal
from .retrieval import Retrieval, VERSION, MODES


MEMORY_CACHE_SUFFIX = ".retrieval-1.1-security-20261006"


def memory_cache_path(path: str) -> str:
    """Select a fresh security-patch sidecar without touching older indexes."""
    if path.endswith(MEMORY_CACHE_SUFFIX):
        return path
    old_suffix = ".retrieval-1.1"
    if path.endswith(old_suffix):
        path = path[:-len(old_suffix)]
    return path + MEMORY_CACHE_SUFFIX


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only, versioned NEXO evidence retrieval")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("sync", "search", "context", "get", "trace", "groups", "dream", "diff", "serve"):
        p = sub.add_parser(command)
        p.add_argument("tower"); p.add_argument("cache")
        if command not in {"sync", "serve"}:
            p.add_argument("--role", required=True)
        if command in {"search", "context"}:
            p.add_argument("--query", required=True)
        if command == "search":
            p.add_argument("--mode", choices=sorted(MODES), default="auto")
            p.add_argument("--filters", default="{}", help="JSON exact filters")
            p.add_argument("-k", type=int, default=8)
            p.add_argument("--as-of"); p.add_argument("--include-inactive", action="store_true")
            p.add_argument("--embedding-model"); p.add_argument("--embedding-manifest")
            p.add_argument("--reranker-model"); p.add_argument("--reranker-manifest")
        if command == "context":
            p.add_argument("--budget", type=int, default=8000)
        if command == "groups":
            p.add_argument("--mode", choices=("topic", "semantic"), default="topic")
        if command in {"get", "trace", "diff"}:
            p.add_argument("--entity", required=True)
        if command in {"get", "trace"}:
            p.add_argument("--as-of"); p.add_argument("--include-inactive", action="store_true")
        if command == "trace":
            p.add_argument("--depth", type=int, default=4)
            p.add_argument("--direction", choices=("in", "out", "both"), default="both")
        if command == "diff":
            p.add_argument("--revision-a", required=True); p.add_argument("--revision-b", required=True)
        if command == "serve":
            p.add_argument("--auth-file", required=True)
    p = sub.add_parser("feedback")
    p.add_argument("cache"); p.add_argument("packet")
    p.add_argument("--used", nargs="*", default=[]); p.add_argument("--outcome", required=True)
    p.add_argument("--evidence", nargs="+", required=True); p.add_argument("--proposal-at")
    args = parser.parse_args(argv)
    try:
        encoder = reranker = None
        if getattr(args, "embedding_model", None):
            from .retrieval_models import LocalEmbedding
            if not args.embedding_manifest:
                raise ValueError("A pinned model manifest is required")
            encoder = LocalEmbedding(args.embedding_model, args.embedding_manifest)
        if getattr(args, "reranker_model", None):
            from .retrieval_models import LocalReranker
            if not args.reranker_manifest:
                raise ValueError("A pinned model manifest is required")
            reranker = LocalReranker(args.reranker_model, args.reranker_manifest)
        engine = Retrieval(args.cache, embedding=encoder, reranker=reranker)
        if args.command == "serve":
            from .retrieval_mcp import serve_stdio
            return serve_stdio(engine, args.tower, args.auth_file)
        if args.command == "feedback":
            packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
            result = engine.record_feedback(packet, args.used, args.outcome, args.evidence)
            if args.proposal_at:
                result = feedback_proposal(result, created_at=args.proposal_at)
        else:
            snap = Snapshot.read(args.tower)
            sync = engine.sync(snap)
            if args.command == "sync": result = sync
            elif args.command == "search":
                result = engine.search(args.query, args.role, k=args.k, mode=args.mode,
                    filters=json.loads(args.filters), as_of=args.as_of, include_inactive=args.include_inactive,
                    expected_revision=snap.revision)
            elif args.command == "context":
                result = engine.context(args.query, args.role, budget_chars=args.budget, expected_revision=snap.revision)
            elif args.command == "get":
                result = engine.get(args.entity, args.role, as_of=args.as_of, include_inactive=args.include_inactive)
            elif args.command == "trace":
                result = engine.trace(args.entity, args.role, as_of=args.as_of, include_inactive=args.include_inactive,
                                      depth=args.depth, direction=args.direction)
            elif args.command == "groups": result = engine.groups(args.role, mode=args.mode)
            elif args.command == "dream": result = engine.dreams(args.role)
            else: result = engine.diff(args.entity, args.role, args.revision_a, args.revision_b)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc), "source_mutated": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
