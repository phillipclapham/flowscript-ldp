# flowscript-ldp

**First implementation of LDP Mode 3 (Semantic Graphs) using FlowScript IR.**

Reference implementation for Mode 3 of the [LLM Delegate Protocol](https://arxiv.org/abs/2603.08852) (Prakash, 2026). Mode 3 is "specified but not yet evaluated empirically" in the paper — this package provides the first working implementation.

## Quick Start

Load a pre-compiled IR graph and start querying — no external tools needed:

```python
import json
from flowscript_ldp import FlowScriptPayload

# Load IR from JSON (see examples/sample_ir.json)
with open("examples/sample_ir.json") as f:
    ir_data = json.load(f)

payload = FlowScriptPayload.from_dict(ir_data)

# Find all tradeoffs in the graph
tensions = payload.query.tensions()
# → 3 tensions: "cost vs control", "latency vs cost", "performance vs freshness"

# Track blockers with impact scores
blockers = payload.query.blocked()
# → 1 blocker: "team capacity for maintenance" (impact_score: 2)

# Trace why something exists
why = payload.query.why(ir_data["nodes"][0]["id"], format="minimal")
# → root_cause: "caching strategy for read-heavy API endpoints"

# Encode for LDP transport
envelope = payload.encode()
# → {"ldp_version": "1.0", "payload_mode": 3, "payload_format": "flowscript-ir", ...}
```

If you have the [FlowScript CLI](https://github.com/phillipclapham/flowscript) installed, you can also parse `.fs` files directly:

```python
from flowscript_ldp import ParserBridge
bridge = ParserBridge()
ir = bridge.parse_file("thinking.fs")
payload = FlowScriptPayload(ir)
```

## What This Does

Coordination between AI agents becomes **computational instead of inferential**. Instead of passing natural language between delegates and hoping they infer the right structure, Mode 3 payloads carry queryable semantic graphs. Five operations make the structure computable:

| Query | What it does | Example output |
|-------|-------------|----------------|
| `why(node_id)` | Causal ancestry — trace backward | `root_cause: "user growth projections"` |
| `what_if(node_id)` | Impact analysis — trace forward | `"affects 4 downstream considerations"` |
| `tensions()` | Tradeoff mapping — extract all tensions | `3 tensions across ["cost vs control", ...]` |
| `blocked()` | Blocker tracking — find blocked nodes | `1 blocker, impact_score: 2, days_blocked: 4` |
| `alternatives(question_id)` | Decision reconstruction | `chosen: "Redis", reason: "latency requirements"` |

### Fallback Chain

Per LDP spec, if Mode 3 fails or the receiver doesn't support it, the protocol degrades gracefully:

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

## LDP Mode 3: Semantic Graphs

The LLM Delegate Protocol defines 6 payload modes (0-5) for inter-agent communication. Modes 0-1 are evaluated in the paper. Mode 3 (Semantic Graphs) uses "structured relationship representations for planning and formal reasoning."

FlowScript's IR — a typed graph of nodes (12 semantic types), relationships (10 types), and states (4 types) with SHA-256 content-addressed deduplication — is a direct implementation of Mode 3.

### Provenance and Quality

The LDP paper's key finding: noisy provenance *degrades* synthesis quality below the no-provenance baseline. Every element in FlowScript IR carries provenance metadata (source file, line number, timestamp, optional author). The IR's temporal graduation model (observations must survive quality gates to persist) acts as a provenance noise filter — only verified patterns carry forward. Mode 3 payloads carrying pre-filtered relational structure sidestep the degradation the paper identifies.

### JamJet Integration

FlowScript query operations are available as tool-compatible functions for JamJet workflows:

```python
from jamjet import tool, Agent
from flowscript_ldp.adapter import flowscript_tensions, flowscript_blocked

agent = Agent(
    "analyst",
    model="claude-haiku-4-5-20251001",
    tools=[tool(flowscript_tensions), tool(flowscript_blocked)],
    instructions="Analyze the semantic graph for tradeoffs and blockers.",
)
result = await agent.run(f"Analyze this: {ir_json}")
```

A standalone `FlowScriptMode3Adapter` dispatcher is also available, designed to be compatible with a future ProtocolAdapter interface as JamJet adds protocol-level extensibility:

```python
from flowscript_ldp import FlowScriptMode3Adapter

adapter = FlowScriptMode3Adapter()
result = adapter.invoke(envelope, query="tensions", fallback_mode=1)
```

See `examples/jamjet_workflow.yaml` for a complete workflow definition.

## CLI

```bash
flowscript-ldp info graph.json                          # IR statistics
flowscript-ldp query tensions graph.json                # Find tradeoffs
flowscript-ldp query blocked graph.json                 # Find blockers
flowscript-ldp query why <node_id> graph.json           # Trace causes
flowscript-ldp query what-if <node_id> graph.json       # Impact analysis
flowscript-ldp query alternatives <question_id> graph.json  # Decision reconstruction
flowscript-ldp encode graph.json                        # Wrap in Mode 3 envelope
flowscript-ldp degrade graph.json --mode 0              # Degrade to natural language
```

## Installation

```bash
pip install flowscript-ldp
```

Or from source:

```bash
pip install git+https://github.com/phillipclapham/flowscript-ldp.git
```

The core package (IR models, query engine, payload, fallback, adapter, CLI) works standalone. The `ParserBridge` optionally requires the [FlowScript CLI](https://github.com/phillipclapham/flowscript) for parsing `.fs` text files.

## Architecture

```
flowscript_ldp/
├── ir.py              # Pydantic models matching FlowScript IR JSON schema
├── parser_bridge.py   # Subprocess bridge to FlowScript CLI (optional)
├── query.py           # Python port of 5 query operations (3 formats each)
├── payload.py         # Mode 3 payload encode/decode/envelope
├── fallback.py        # Mode 3 → Mode 1 → Mode 0 conversion
├── adapter.py         # JamJet tool functions + standalone adapter
├── round_trip.py      # Round-trip verification utilities
└── cli.py             # Command-line interface
```

**105 tests** covering IR models, all 5 query operations with all format variants (including edge cases: cycles, diamond graphs, empty graphs, depth limiting), payload encode/decode, fallback chain, adapter dispatch, tool functions, repr output, and round-trip verification.

## References

- **LDP Paper**: [arXiv:2603.08852](https://arxiv.org/abs/2603.08852) — Sunil Prakash, March 2026
- **FlowScript**: [github.com/phillipclapham/flowscript](https://github.com/phillipclapham/flowscript) — Semantic notation for cognitive graphs
- **JamJet**: [github.com/jamjet-labs/jamjet](https://github.com/jamjet-labs/jamjet) — Agent-native runtime (Rust core, Python SDK)

## License

MIT
