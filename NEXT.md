# flowscript-ldp — Session Handoff

**Status:** Pre-publish review COMPLETE. Ready for README polish → PyPI publish → distribution.
**Repo:** https://github.com/phillipclapham/flowscript-ldp
**Context:** Sunil Prakash (LDP paper, arXiv:2603.08852) confirmed FlowScript = Mode 3. We built the first implementation. Build plan: `~/Documents/flow/contexts/flowscript_ldp_build_plan.md`.

---

## What's Built (Session A+B + Review Session, Mar 14 2026)

### 8 Modules (~2,000 lines source)
| Module | What | Status |
|--------|------|--------|
| `ir.py` | Pydantic models for FlowScript IR schema (12 node types, 10 rel types, 4 state types) | Complete |
| `parser_bridge.py` | Subprocess bridge to FlowScript CLI (PATH-based discovery) | Complete |
| `query.py` | All 5 query operations, 3 formats each. Multi-state index (`_states_by_node`). | Complete |
| `payload.py` | Mode 3 envelope encode/decode + capability negotiation | Complete |
| `fallback.py` | Mode 3 → Mode 1 → Mode 0 degradation chain | Complete |
| `adapter.py` | Sync tool functions (6) + `get_jamjet_tools()` async wrappers + standalone adapter | Complete |
| `round_trip.py` | Verification utilities | Complete |
| `cli.py` | CLI: query/encode/degrade/info commands | Complete |

### 111 Tests (all passing, 0.04s)
- IR models, all 5 query ops with format variants
- Edge cases: cycles, diamond graphs, empty IR, depth limits, multi-parent trees
- Payload encode/decode round-trips
- Fallback chain (both directions)
- Adapter dispatch + all 6 sync tool functions
- JamJet `get_jamjet_tools()` integration (async, Agent creation, tool invocation)
- __repr__ output verification

### Reviews Completed
1. **Multi-agent code review** (build session): 3 software experts + 1 divergent reviewer. Fixed content-matching bug, hash validation, O(n) scans, adapter serialization.
2. **Fresh-eyes code review** (review session): Cross-referenced against TS source (`query-engine.ts`). Fixed: state map multi-state support, CLI path hardcoding, version string duplication, tensions return data, demo node selection.
3. **JamJet integration test** (review session): Verified all 6 tools register, fire through `@tool` async decorator, and Agent constructs. Found/fixed: JamJet requires async tools (added `get_jamjet_tools()`).

### Key Findings
- **JamJet v0.1.2 has NO ProtocolAdapter interface.** Integration is via `get_jamjet_tools()` (works today) + forward-looking `FlowScriptMode3Adapter` class.
- **Python port is MORE correct than TS source** in `_check_decided` — matches on `node_id` instead of TS's `content` comparison.
- **PyPI name "flowscript-ldp" is available.** Package builds clean, twine check passes.

---

## What's Next (in order)

### 1. ~~Fresh-Eyes Code Review~~ ✓ DONE
### 2. ~~JamJet Integration Test~~ ✓ DONE

### 3. README Polish
- Explain FlowScript itself better (what is it, why semantic graphs matter)
- Add badges (tests passing, Python version, license)
- Improve discoverability for GitHub search

### 4. Distribution
- PyPI publish (`twine upload dist/*` — account ready, token needed)
- LinkedIn post announcing the implementation
- Email Sunil with repo link
- Consider reaching out to JamJet team

---

## Post-Publish Roadmap: Reference → Production

**Strategic framing:** v0.1.0 is a correct, tested reference implementation. It proves Mode 3 works. Production-grade means participating in the full LDP session lifecycle, which requires protocol decisions that should be informed by Sunil's and JamJet's feedback.

### What we have vs what's missing

| Layer | v0.1.0 Status | Gap to Production |
|-------|--------------|-------------------|
| **Data** (IR models, validation) | ✓ Complete | None |
| **Query** (5 ops, 3 formats each) | ✓ Complete | None |
| **Payload** (Mode 3 envelope, encode/decode) | ✓ Complete | Minor: envelope versioning strategy |
| **Fallback** (Mode 3→1→0 chain) | ✓ Complete | Mode 0→3 upgrade (requires parser, intentionally lossy) |
| **Session** (LDP lifecycle) | Partial: `negotiate_capabilities()` returns manifest | No session state machine, no session ID tracking, no mid-session fallback triggers |
| **Transport** (wire protocol) | None | No HTTP/WebSocket/gRPC, no message framing, no auth |
| **Runtime** (JamJet integration) | `get_jamjet_tools()` works | No ProtocolAdapter trait (JamJet hasn't built it), no streaming, no cancellation |
| **Observability** | None | No metrics, tracing, error taxonomy |
| **Resilience** | Basic validation errors | No retry, circuit breaker, partial failure handling |

### Production roadmap (flexible — depends on external feedback)

**Phase 1: Session State Machine** (~1-2 days)
- Implement HELLO → CAPABILITY_MANIFEST → SESSION_PROPOSE → SESSION_ACCEPT → TASK flow as Python class
- Implementable from paper spec alone
- Makes the adapter a genuine protocol participant, not just a payload handler
- Mid-session fallback: Mode 3 validation failure → automatic degrade to Mode 1 → retry

**Phase 2: Two-Agent Integration Test** (~1 day)
- Two JamJet agents: one sending Mode 3, one receiving
- Proves bidirectional protocol function, not just unit test correctness
- Requires JamJet agent-to-agent communication (may need JamJet team input)

**Phase 3: Transport Layer** (scope TBD — depends on JamJet/LDP ecosystem direction)
- Wire protocol for Mode 3 payloads
- Authentication and session management
- Likely shaped by ProtocolAdapter when JamJet ships it

**Phase 4: Production Hardening** (scope TBD)
- Observability (OpenTelemetry traces, metrics)
- Resilience patterns (retry, circuit breaker)
- Performance optimization for large graphs
- Error taxonomy and structured error responses

### Why not build all of this now?
- **Session state machine**: Implementable from paper, but Sunil may have opinions on how it should work. Better to ship what's correct, get feedback, then build.
- **Transport**: No wire format spec exists. Building one in isolation risks building the wrong thing.
- **ProtocolAdapter**: JamJet hasn't built the trait. Our adapter class is forward-looking, but the actual interface will come from them.
- **Strategic value of being FIRST and CORRECT > being production-grade before anyone else has started.** v0.1.0 proves the concept. v0.2.0 builds on real-world feedback.

---

## Quick Reference

```bash
# Development
cd ~/Documents/flowscript-ldp
source .venv/bin/activate  # Python 3.14, use `pip install ".[dev]"` (not editable)

# Tests
.venv/bin/python3 -m pytest tests/ -v

# CLI
.venv/bin/flowscript-ldp info examples/sample_ir.json
.venv/bin/flowscript-ldp query tensions examples/sample_ir.json

# Demo
.venv/bin/python3 examples/standalone_demo.py
.venv/bin/python3 examples/basic_usage.py  # requires FlowScript CLI

# Build for PyPI
.venv/bin/python3 -m build
.venv/bin/twine check dist/*
.venv/bin/twine upload dist/*  # username: __token__, password: pypi-...
```

## Key Files to Read on Session Start
1. This file (NEXT.md)
2. `README.md` — what we're presenting to the world
3. `src/flowscript_ldp/query.py` — the core (biggest file, most logic)
4. `src/flowscript_ldp/adapter.py` — JamJet integration surface + `get_jamjet_tools()`
5. `tests/` — coverage picture

*Created: Mar 14, 2026*
*Updated: Mar 14, 2026 — post fresh-eyes review + JamJet integration test*
