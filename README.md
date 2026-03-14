# flowscript-ldp

**First implementation of LDP Mode 3 (Semantic Graphs) using FlowScript IR.**

Reference implementation for Mode 3 of the [LLM Delegate Protocol](https://arxiv.org/abs/2603.08852) (Prakash, 2026). Mode 3 is "specified but not yet evaluated empirically" in the paper — this package provides the first working implementation.

## What This Does

Coordination between AI agents becomes **computational instead of inferential**:

```python
from flowscript_ldp import FlowScriptPayload, ParserBridge

# Parse FlowScript text to IR
bridge = ParserBridge()
ir = bridge.parse_file("thinking.fs")

# Create Mode 3 payload
payload = FlowScriptPayload(ir)

# Query the semantic graph computationally
blockers = payload.query.blocked()
tensions = payload.query.tensions()
impact = payload.query.what_if("node_id")

# Encode for LDP transport
envelope = payload.encode()

# Graceful degradation
from flowscript_ldp import FallbackChain
fallback = FallbackChain(ir)
mode1 = fallback.to_mode1()  # Semantic frame
mode0 = fallback.to_mode0()  # Natural language
```

## LDP Mode 3: Semantic Graphs

The LLM Delegate Protocol defines 6 payload modes (0-5) for inter-agent communication. Modes 0-1 are evaluated in the paper. Mode 3 (Semantic Graphs) uses "structured relationship representations for planning and formal reasoning."

FlowScript's IR — a typed graph of nodes, relationships, and states with SHA-256 content-addressed deduplication — is a direct implementation of Mode 3.

### Five Query Operations

| Query | What it does |
|-------|-------------|
| `why(node_id)` | Causal ancestry — trace backward through causes |
| `what_if(node_id)` | Impact analysis — trace forward through consequences |
| `tensions()` | Tradeoff mapping — extract all tensions by axis |
| `blocked()` | Blocker tracking — find blocked nodes with impact scores |
| `alternatives(question_id)` | Decision reconstruction — show all options considered |

### Fallback Chain

Per LDP spec, if Mode 3 fails, the protocol degrades gracefully:
- **Mode 3 → Mode 1**: Extract semantic frame (task_type, instruction, labels)
- **Mode 3 → Mode 0**: Render graph as natural language prose
- **Mode 0 → Mode 3**: Parse text through FlowScript CLI (lossy but functional)

## Installation

```bash
pip install flowscript-ldp
```

Requires FlowScript CLI at `~/Documents/flowscript/` (for parser bridge).

## Architecture

```
flowscript_ldp/
├── ir.py              # Pydantic models matching FlowScript IR JSON schema
├── parser_bridge.py   # Subprocess bridge to FlowScript CLI
├── query.py           # Python port of 5 query operations
├── payload.py         # Mode 3 payload encode/decode/envelope
├── fallback.py        # Mode 3 → Mode 1 → Mode 0 conversion
├── adapter.py         # JamJet ProtocolAdapter hook
└── round_trip.py      # Round-trip verification utilities
```

## References

- **LDP Paper**: [arXiv:2603.08852](https://arxiv.org/abs/2603.08852) — Sunil Prakash, March 2026
- **FlowScript**: [github.com/phillipclapham/flowscript](https://github.com/phillipclapham/flowscript) — Semantic notation for cognitive graphs
- **JamJet**: [github.com/jamjet-labs/jamjet](https://github.com/jamjet-labs/jamjet) — Agent-native runtime (Rust core, Python SDK)

## License

MIT
