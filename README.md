# flowscript-ldp

[![Tests](https://img.shields.io/badge/tests-168%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-≥3.10-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![PyPI](https://img.shields.io/pypi/v/flowscript-ldp)]()

**First implementation of LDP Mode 3 (Semantic Graphs) using FlowScript IR.**

Reference implementation for Mode 3 of the [LLM Delegate Protocol](https://arxiv.org/abs/2603.08852) (Prakash, 2026). Mode 3 — "structured relationship representations for planning and formal reasoning" — is specified but not yet evaluated in the paper. This package provides the first working implementation: a queryable semantic graph format for inter-agent communication.

## What is FlowScript?

[FlowScript](https://github.com/phillipclapham/flowscript) is a semantic notation that compiles to a typed intermediate representation (IR). The IR is a graph with three collections:

- **Nodes** (12 types): statements, questions, thoughts, decisions, blockers, insights, actions, completions, alternatives, exploring, parking, blocks
- **Relationships** (10 types): causes, temporal, derives_from, bidirectional, tension, equivalent, different, alternative, alternative_worse, alternative_better
- **States** (4 types): blocked, decided, exploring, parking

Every element has provenance metadata (source file, line number, timestamp) and SHA-256 content-addressed deduplication. This gives you a queryable graph where you can trace causal chains, map tradeoffs, find blockers, and reconstruct decisions computationally — without parsing natural language.

## Quick Start

Load a pre-compiled IR graph and start querying — no external tools needed:

```python
import json
from flowscript_ldp import FlowScriptPayload

with open("examples/sample_ir.json") as f:
    ir_data = json.load(f)

payload = FlowScriptPayload.from_dict(ir_data)

# Find all tradeoffs in the graph
tensions = payload.query.tensions()
# → 3 tensions: "cost vs control", "latency vs cost", "performance vs freshness"

# Track blockers with impact scores
blocked = payload.query.blocked()
# → 1 blocker: "add cache hit/miss monitoring to Datadog"

# Trace causal ancestry
node_id = "fdc98c25..."  # "centralized cache invalidation"
why = payload.query.why(node_id, format="minimal")
# → root_cause: "Redis cache layer"

# Encode for LDP transport
envelope = payload.encode()
# → {"ldp_version": "1.0", "payload_mode": 3, "payload_format": "flowscript-ir", ...}
```

If you have the [FlowScript CLI](https://github.com/phillipclapham/flowscript) installed, you can also parse `.fs` files directly:

```python
from flowscript_ldp import ParserBridge, FlowScriptPayload
bridge = ParserBridge()
ir = bridge.parse_file("thinking.fs")
payload = FlowScriptPayload(ir)
```

## Why Mode 3?

The LLM Delegate Protocol defines 6 payload modes (0–5) for inter-agent communication:

| Mode | Name | Status |
|------|------|--------|
| 0 | Text | Evaluated in paper |
| 1 | Semantic Frames | Evaluated in paper |
| 2 | Embedding Hints | Specified, unimplemented |
| **3** | **Semantic Graphs** | **Specified, first implementation here** |
| 4 | Latent Capsules | Future work |
| 5 | Cache Slices | Future work |

Modes 0–1 pass text or structured JSON between agents. Mode 3 passes **queryable graphs** — agents can trace causality, find tradeoffs, and reconstruct decisions computationally instead of inferring them from prose. Five operations make the structure computable:

| Query | What it does | Example |
|-------|-------------|---------|
| `why(node_id)` | Trace causal ancestry backward | root_cause: "Redis cache layer" |
| `what_if(node_id)` | Trace downstream impact forward | "affects 4 downstream considerations" |
| `tensions()` | Extract all tradeoffs | "cost vs control", "latency vs cost" |
| `blocked()` | Find blockers with impact scores | "Datadog trial expired" (impact: 0) |
| `alternatives(question_id)` | Reconstruct decisions | 3 options considered, chosen: "Redis" |

Each query supports multiple output formats (chain/tree/minimal for `why`, tree/list/summary for `what_if`, axis/node/flat for `tensions`, comparison/tree/simple for `alternatives`).

### Fallback Chain

Per LDP spec, when Mode 3 fails or the receiver doesn't support it, the protocol degrades gracefully:

```
Mode 3 (Semantic Graph) → Mode 1 (Semantic Frame) → Mode 0 (Natural Language)
```

```python
from flowscript_ldp import FallbackChain

fallback = FallbackChain(ir)

# Mode 3 → Mode 1: Structured semantic frame
mode1 = fallback.to_mode1()
# → {"task_type": "decision_analysis", "instruction": "caching strategy for...", ...}

# Mode 3 → Mode 0: Natural language prose
mode0 = fallback.to_mode0()
# → "Question: caching strategy for read-heavy API endpoints\n  Option: Redis cache layer\n  ..."
```

### Provenance and Quality

The LDP paper's key finding: noisy provenance *degrades* synthesis quality below the no-provenance baseline. FlowScript IR's temporal graduation model — observations must survive quality gates to persist — acts as a provenance noise filter. Mode 3 payloads carrying pre-filtered relational structure sidestep the degradation the paper identifies.

## JamJet + LDP Integration

As of v0.2.0, flowscript-ldp integrates with both [JamJet](https://github.com/jamjet-labs/jamjet) v0.2.0's `ProtocolAdapter` interface and the standalone [ldp-protocol](https://pypi.org/project/ldp-protocol/) SDK.

### LDP Delegate (server-side)

Run a Mode 3 delegate as an HTTP service that any LDP client can discover, negotiate with, and submit tasks to:

```python
from flowscript_ldp.delegate import FlowScriptMode3Delegate

delegate = FlowScriptMode3Delegate()
delegate.run(port=8090)  # HTTP server with /ldp/identity, /ldp/capabilities, /ldp/messages
```

The delegate advertises 6 skills (`flowscript.tensions`, `flowscript.blocked`, `flowscript.why`, `flowscript.what_if`, `flowscript.alternatives`, `flowscript.degrade`) and negotiates Mode 3 (Semantic Graph) payloads during session establishment.

```python
from ldp_protocol import LdpClient

async with LdpClient() as client:
    # Discover delegate capabilities
    identity = await client.discover("http://localhost:8090")

    # Submit a query task
    result = await client.submit_task(
        "http://localhost:8090",
        skill="flowscript.tensions",
        input_data={"ir": ir_json},
    )
    # → {"output": {"tensions": [...], "metadata": {...}}, "provenance": {...}}
```

### JamJet ProtocolAdapter (client-side)

Register flowscript-ldp with JamJet's protocol registry so workflows can route to LDP delegates via `ldp://` URLs:

```python
from flowscript_ldp.adapter import FlowScriptLdpAdapter

FlowScriptLdpAdapter.register()  # registers for ldp:// and ldp+flowscript:// URL prefixes
```

### JamJet @tool integration

FlowScript query operations are also available as JamJet-compatible `@tool` functions for use in agent workflows:

```python
from jamjet import Agent
from flowscript_ldp import get_jamjet_tools

agent = Agent(
    "analyst",
    model="claude-haiku-4-5-20251001",
    tools=get_jamjet_tools(),  # 6 async tools: tensions, blocked, why, what_if, alternatives, degrade
    instructions="Analyze the semantic graph for tradeoffs and blockers.",
)
result = await agent.run(f"Analyze this: {ir_json}")
```

### Standalone use

The sync query functions and adapter work without JamJet or ldp-protocol:

```python
from flowscript_ldp.adapter import flowscript_tensions, FlowScriptMode3Adapter

# Direct function call
result = flowscript_tensions(ir_data)

# Adapter with query dispatch
adapter = FlowScriptMode3Adapter()
result = adapter.invoke(envelope, query="tensions", fallback_mode=1)
```

See `examples/standalone_demo.py` for a runnable demo of all 5 queries.

## CLI

```bash
flowscript-ldp info graph.json                              # IR statistics
flowscript-ldp query tensions graph.json                    # Find tradeoffs
flowscript-ldp query blocked graph.json                     # Find blockers
flowscript-ldp query why <node_id> graph.json               # Trace causes
flowscript-ldp query what-if <node_id> graph.json           # Impact analysis
flowscript-ldp query alternatives <question_id> graph.json  # Decision reconstruction
flowscript-ldp encode graph.json                            # Wrap in Mode 3 envelope
flowscript-ldp degrade graph.json --mode 0                  # Degrade to natural language
```

## Installation

```bash
pip install flowscript-ldp              # core (IR, queries, payload, fallback, CLI)
pip install flowscript-ldp[ldp]         # + LDP delegate (ldp-protocol SDK)
pip install flowscript-ldp[jamjet]      # + JamJet ProtocolAdapter
pip install flowscript-ldp[all]         # everything
```

From source:

```bash
pip install git+https://github.com/phillipclapham/flowscript-ldp.git
```

**Core dependency:** `pydantic>=2.0`. JamJet and ldp-protocol are optional — the core package (IR models, query engine, payload, fallback, adapter, CLI) works standalone. The `ParserBridge` optionally requires the [FlowScript CLI](https://github.com/phillipclapham/flowscript) for parsing `.fs` text files into IR.

## Architecture

```
flowscript_ldp/
├── ir.py              # Pydantic models for FlowScript IR schema
├── parser_bridge.py   # Subprocess bridge to FlowScript CLI (optional)
├── query.py           # 5 query operations, 3 formats each (Python port of TypeScript engine)
├── payload.py         # Mode 3 payload encode/decode/envelope
├── fallback.py        # Mode 3 → Mode 1 → Mode 0 degradation
├── adapter.py         # Sync tools + get_jamjet_tools() + FlowScriptLdpAdapter(ProtocolAdapter)
├── delegate.py        # FlowScriptMode3Delegate(LdpDelegate) — LDP server
├── round_trip.py      # Round-trip verification utilities
└── cli.py             # Command-line interface
```

**168 tests** covering IR models, all 5 query operations with all format variants (edge cases: cycles, diamond graphs, empty graphs, depth limiting), payload round-trips, fallback chain, adapter dispatch, JamJet tool integration, LDP delegate skills/identity/negotiation, ProtocolAdapter client-side bridge, and full HTTP integration round-trips (delegate server + LdpClient + adapter).

## References

- **LDP Paper**: [arXiv:2603.08852](https://arxiv.org/abs/2603.08852) — Sunil Prakash, March 2026
- **ldp-protocol**: [pypi.org/project/ldp-protocol](https://pypi.org/project/ldp-protocol/) — Standalone Python SDK for LDP (LdpDelegate, LdpClient, LdpRouter)
- **FlowScript**: [github.com/phillipclapham/flowscript](https://github.com/phillipclapham/flowscript) — Semantic notation for cognitive graphs
- **JamJet**: [github.com/jamjet-labs/jamjet](https://github.com/jamjet-labs/jamjet) — Agent-native runtime (Rust core, Python SDK)

## License

MIT
