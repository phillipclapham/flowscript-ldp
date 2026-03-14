"""
flowscript-ldp CLI.

Command-line interface for querying FlowScript IR graphs.
Designed for researchers and developers who want to explore
Mode 3 payloads from the terminal.

Usage:
    flowscript-ldp query tensions graph.json
    flowscript-ldp query blocked graph.json
    flowscript-ldp query why <node_id> graph.json
    flowscript-ldp query what-if <node_id> graph.json
    flowscript-ldp query alternatives <question_id> graph.json
    flowscript-ldp encode graph.json          # Wrap IR in Mode 3 envelope
    flowscript-ldp degrade graph.json --mode 1  # Degrade to Mode 1
    flowscript-ldp degrade graph.json --mode 0  # Degrade to Mode 0
    flowscript-ldp info graph.json            # Show IR stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .fallback import FallbackChain
from .ir import IR
from .payload import FlowScriptPayload
from .query import QueryEngine


def _load_ir(path: str) -> IR:
    """Load IR from JSON file."""
    with open(path) as f:
        data = json.load(f)
    # Accept both raw IR and Mode 3 envelopes
    if "ldp_version" in data:
        payload = FlowScriptPayload.decode(data)
        return payload.ir
    return IR.model_validate(data)


def cmd_query(args: argparse.Namespace) -> None:
    """Run a query operation."""
    ir = _load_ir(args.file)
    engine = QueryEngine(ir)

    if args.operation == "tensions":
        result = engine.tensions()
        print(f"Tensions: {result.metadata['total_tensions']}")
        for axis in result.metadata["unique_axes"]:
            print(f"  [{axis}]")
            if result.tensions_by_axis:
                for t in result.tensions_by_axis.get(axis, []):
                    print(f"    {t.source['content']} vs {t.target['content']}")

    elif args.operation == "blocked":
        result = engine.blocked()
        print(f"Blockers: {result.metadata['total_blockers']}")
        for b in result.blockers:
            print(f"  {b.node['content']}")
            print(f"    reason: {b.blocked_state['reason']}")
            print(f"    days: {b.blocked_state['days_blocked']}, impact: {b.impact_score}")

    elif args.operation == "why":
        if not args.node_id:
            print("Error: why requires a node_id argument", file=sys.stderr)
            sys.exit(1)
        result = engine.why(args.node_id, format="chain")
        print(result)

    elif args.operation == "what-if":
        if not args.node_id:
            print("Error: what-if requires a node_id argument", file=sys.stderr)
            sys.exit(1)
        result = engine.what_if(args.node_id, format="summary")
        print(result)

    elif args.operation == "alternatives":
        if not args.node_id:
            print("Error: alternatives requires a question_id argument", file=sys.stderr)
            sys.exit(1)
        result = engine.alternatives(args.node_id, format="simple")
        print(result)

    else:
        print(f"Unknown operation: {args.operation}", file=sys.stderr)
        sys.exit(1)


def cmd_encode(args: argparse.Namespace) -> None:
    """Encode IR as Mode 3 payload."""
    ir = _load_ir(args.file)
    payload = FlowScriptPayload(ir)
    envelope = payload.encode()
    json.dump(envelope, sys.stdout, indent=2)
    print()


def cmd_degrade(args: argparse.Namespace) -> None:
    """Degrade Mode 3 to Mode 1 or Mode 0."""
    ir = _load_ir(args.file)
    fallback = FallbackChain(ir)

    if args.mode == 0:
        print(fallback.to_mode0())
    elif args.mode == 1:
        json.dump(fallback.to_mode1(), sys.stdout, indent=2)
        print()
    else:
        print(f"Unsupported target mode: {args.mode}", file=sys.stderr)
        sys.exit(1)


def cmd_info(args: argparse.Namespace) -> None:
    """Show IR statistics."""
    ir = _load_ir(args.file)

    type_counts: dict[str, int] = {}
    for node in ir.nodes:
        t = node.type.value
        type_counts[t] = type_counts.get(t, 0) + 1

    rel_counts: dict[str, int] = {}
    for rel in ir.relationships:
        t = rel.type.value
        rel_counts[t] = rel_counts.get(t, 0) + 1

    state_counts: dict[str, int] = {}
    for state in ir.states:
        t = state.type.value
        state_counts[t] = state_counts.get(t, 0) + 1

    print(f"FlowScript IR v{ir.version}")
    print(f"  Nodes: {len(ir.nodes)}")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")
    print(f"  Relationships: {len(ir.relationships)}")
    for t, c in sorted(rel_counts.items()):
        print(f"    {t}: {c}")
    print(f"  States: {len(ir.states)}")
    for t, c in sorted(state_counts.items()):
        print(f"    {t}: {c}")

    # Show questions (useful for alternatives query)
    questions = [n for n in ir.nodes if n.type.value == "question"]
    if questions:
        print(f"\n  Questions ({len(questions)}):")
        for q in questions:
            print(f"    {q.id[:12]}... {q.content}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="flowscript-ldp",
        description="Query FlowScript IR graphs via LDP Mode 3",
    )
    parser.add_argument("--version", action="version", version=f"flowscript-ldp {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # query
    query_parser = subparsers.add_parser("query", help="Run a query operation")
    query_parser.add_argument(
        "operation",
        choices=["tensions", "blocked", "why", "what-if", "alternatives"],
        help="Query operation to run",
    )
    query_parser.add_argument("node_id", nargs="?", help="Node ID (for why/what-if/alternatives)")
    query_parser.add_argument("file", help="IR JSON file path")
    query_parser.set_defaults(func=cmd_query)

    # encode
    encode_parser = subparsers.add_parser("encode", help="Encode IR as Mode 3 envelope")
    encode_parser.add_argument("file", help="IR JSON file path")
    encode_parser.set_defaults(func=cmd_encode)

    # degrade
    degrade_parser = subparsers.add_parser("degrade", help="Degrade to Mode 1 or Mode 0")
    degrade_parser.add_argument("file", help="IR JSON file path")
    degrade_parser.add_argument("--mode", type=int, choices=[0, 1], default=1, help="Target mode")
    degrade_parser.set_defaults(func=cmd_degrade)

    # info
    info_parser = subparsers.add_parser("info", help="Show IR statistics")
    info_parser.add_argument("file", help="IR JSON file path")
    info_parser.set_defaults(func=cmd_info)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
