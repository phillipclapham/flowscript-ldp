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

## v0.2.0 Roadmap: Real Integration (Sunil collaboration active)

**Landscape changed Mar 14:** Sunil replied with three infrastructure gifts:
1. **JamJet v0.2.0** — `ProtocolAdapter` ABC shipped (`discover()`, `invoke()`, `stream()`, `status()`, `cancel()`) + `ProtocolRegistry` with URL-prefix dispatch. `pip install jamjet==0.2.0`
2. **ldp-protocol** — Standalone Python LDP SDK (`LdpDelegate`, `LdpClient`, `LdpRouter`). `pip install ldp-protocol`
3. **Co-design invitation** — Session state machine designed together via GitHub issues, not built against spec alone.

### What we have vs what's changed

| Layer | v0.1.0 Status | v0.2.0 Path |
|-------|--------------|-------------|
| **Data** (IR models, validation) | ✓ Complete | No change |
| **Query** (5 ops, 3 formats each) | ✓ Complete | No change |
| **Payload** (Mode 3 envelope, encode/decode) | ✓ Complete | Minor: envelope versioning strategy |
| **Fallback** (Mode 3→1→0 chain) | ✓ Complete | No change |
| **Runtime** (JamJet integration) | `get_jamjet_tools()` workaround | **UNBLOCKED:** Real `ProtocolAdapter` subclass via JamJet v0.2.0 |
| **Transport** (wire protocol) | None | **NEW:** `ldp-protocol` SDK as foundation layer (LdpDelegate, LdpClient, LdpRouter) |
| **Session** (LDP lifecycle) | Partial: capability manifest only | **CO-DESIGN:** GitHub issues with Sunil. Mode renegotiation subtleties. |
| **Observability** | None | Deferred (post-session layer) |
| **Resilience** | Basic validation errors | Deferred (post-session layer) |

### v0.2.0 build plan (in order)

**Step 1: Integrate JamJet v0.2.0 ProtocolAdapter** (~half day)
- Replace forward-looking `FlowScriptMode3Adapter` with real `ProtocolAdapter` subclass
- Implement all ABC methods: `discover()`, `invoke()`, `stream()`, `status()`, `cancel()`
- Register with `ProtocolRegistry` for URL-prefix dispatch
- Keep `get_jamjet_tools()` as alternative entry point (tools still useful standalone)

**Step 2: Layer on ldp-protocol SDK** (~half day)
- `pip install ldp-protocol` — evaluate how LdpDelegate/LdpClient/LdpRouter fit
- Layer flowscript-ldp encode/decode/query on top of LDP transport primitives
- Replace any hand-rolled transport with Sunil's SDK

**Step 3: Co-design Session State Machine** (async, GitHub issues)
- Open first issue on Sunil's repo: present what we have (capability manifest, stubbed lifecycle)
- Ask specifically about mode renegotiation mid-session
- Seed idea: query ops as coordination primitives for Mode 3 spec
- Build implementation AFTER design converges

**Step 4: Two-Agent Integration Test** (~1 day, after session layer)
- Two JamJet agents with real ProtocolAdapter: sender + receiver
- Bidirectional Mode 3 payloads through actual protocol stack
- Validates the full chain: negotiate → establish → send Mode 3 → query on receive

**Step 5: Production Hardening** (scope TBD after above)
- Observability, resilience, performance
- Scoped by what Steps 1-4 reveal

### GitHub Issues Prep (ready to open when Sunil confirms)

**Issue 1: Session State Machine Co-Design**
```
Title: Mode 3 session lifecycle — co-design proposal
Body:
- What flowscript-ldp has today: negotiate_capabilities() returns Mode 3 manifest
- What's stubbed: HELLO → CAPABILITY_MANIFEST → SESSION_PROPOSE → SESSION_ACCEPT
- Specific question: mode renegotiation mid-session — when Mode 3 validation fails,
  what triggers fallback vs error? Is fallback per-message or per-session?
- Our implementation experience: fallback chain works message-level (encode → validate →
  degrade if invalid → retry at lower mode). Should session-level fallback be different?
```

**Issue 2: Query Operations as Mode 3 Coordination Primitives**
```
Title: Formalizing query operations in Mode 3 spec
Body:
- Current: 5 ops (why, whatIf, tensions, blocked, alternatives) as introspection
- Proposal: these are coordination primitives — receiver runs tensions() on incoming
  payload to pre-compute disagreement before doing work
- This is "pre-computation of disagreement" — unique to semantic graph payloads
- Question: should Mode 3 spec define expected query operations, or leave to implementors?
```

---

## Known Debt Register (MUST evaluate at every phase — close or justify keeping)

Items deferred from v0.2.0 code review (3 reviewers: complement, gemini, session-code-review).
**Rule: every item here gets evaluated at every build session. Close it, schedule it, or justify deferral. Nothing rots silently.**

### OPEN — Evaluate at Step 3 (Session State Machine)

**D1: `_extract_ir` validation inconsistency**
- Source: Complement (warning, high confidence)
- Issue: Raw IR dicts pass through `_extract_ir` without Pydantic validation, while envelopes get validated via `FlowScriptPayload.decode()`. Malformed raw dicts produce unclear errors deep in the query engine.
- Fix: Add `IR.model_validate()` in raw IR path for consistent validation depth.
- Why deferred: Query engine catches structural issues; errors are just less clear. Adds overhead for the common (valid IR) case.
- Close condition: When we build the session layer, we'll define the canonical input path. If all inputs come through LDP envelopes (validated), this becomes moot. If raw IR remains a supported path, fix it then.

**D2: Recursion depth vulnerability in QueryEngine traversals**
- Source: Gemini (concern)
- Issue: `why()`, `what_if()`, `blocked()` use recursive DFS. Maliciously deep graphs (1001+ nodes in a chain) crash with `RecursionError`.
- Fix: Convert to iterative traversal with explicit stack, or add configurable depth limit (50-100 is more than enough for real semantic graphs).
- Why deferred: Existing v0.1.0 code, not introduced in v0.2.0. No user-facing exposure yet (all inputs are locally constructed).
- Close condition: Before any deployment where untrusted IR is accepted as input. When session layer exposes the delegate to external callers, this must be fixed.

### OPEN — Evaluate at Step 4 (Two-Agent Test)

**D3: No integration test through `handle_message()` for full LDP flow**
- Source: Code review agent (note)
- Issue: Tests call `handle_task()` directly. The actual LDP flow goes `handle_message()` → `_handle_task_submit()` → `handle_task()`. A round-trip test through `handle_message()` would catch routing issues.
- Fix: Add test that sends `TASK_SUBMIT` envelope through `handle_message()` and verifies the full `TASK_RESULT` envelope.
- Why deferred: `handle_task()` + `_handle_session_propose()` tested independently; base class routing is ldp-protocol's responsibility.
- Close condition: Two-agent integration test (Step 4) exercises this path end-to-end. Add explicit unit test if the integration test reveals issues.

### OPEN — Evaluate at Step 5 (Production Hardening)

**D4: Dependency version upper bounds**
- Source: Complement (warning, high confidence)
- Issue: `jamjet>=0.2.0` and `ldp-protocol>=0.1.0` have no upper bounds. Both are 0.x packages from a single author. Breaking changes could arrive without warning.
- Fix: Pin `jamjet>=0.2.0,<0.3.0` and `ldp-protocol>=0.1.0,<0.2.0`.
- Why deferred: Sunil is actively collaborating. Pinning now could cause friction during co-design. He's unlikely to ship breaking changes without telling us.
- Close condition: Pin when either (a) collaboration stabilizes and APIs are locked, or (b) we publish to a wider audience who might blindly upgrade. Whichever comes first.

### CLOSED (v0.2.0)

- ~~`_run_query` duplicated formatting logic, diverged from tool functions~~ → FIXED: refactored to delegate to tool functions. Single formatting path.
- ~~`_handle_session_propose` crashes on unknown PayloadMode values~~ → FIXED: try/except skips unknown modes.
- ~~Unused imports in delegate.py~~ → FIXED: removed `NegotiatedPayload`, `Provenance`.
- ~~`_require_arg` falsy check~~ → FIXED: changed to `is None`.
- ~~Unbounded result cache in adapter~~ → FIXED: bounded to 1000, FIFO eviction.
- ~~`__all__` lists undefined names~~ → FIXED: dynamic append inside try/except.
- ~~Registry test pollution~~ → FIXED: autouse cleanup fixture.
- ~~`stream()` docstring misleading~~ → FIXED: clarified raises on iteration.

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
*Updated: Mar 14, 2026 — v0.2.0 built (JamJet v0.2.0 + ldp-protocol integration), 3-reviewer code review complete, all findings addressed or tracked in Debt Register*
