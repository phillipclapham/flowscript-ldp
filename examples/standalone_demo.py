"""
flowscript-ldp: Standalone demo — no FlowScript CLI required.

Loads pre-compiled IR from JSON and demonstrates all 5 query operations,
payload encoding, and fallback degradation.
"""

import json
from pathlib import Path

from flowscript_ldp import FlowScriptPayload, FallbackChain, FlowScriptMode3Adapter

# Load sample IR (pre-compiled from design.fs)
sample_path = Path(__file__).parent / "sample_ir.json"
with open(sample_path) as f:
    ir_data = json.load(f)

payload = FlowScriptPayload.from_dict(ir_data)
ir = payload.ir
print(f"Loaded: {len(ir.nodes)} nodes, {len(ir.relationships)} relationships, {len(ir.states)} states")
print()

# === Query 1: tensions ===
tensions = payload.query.tensions()
print(f"=== Tensions ({tensions.metadata['total_tensions']}) ===")
for axis in tensions.metadata["unique_axes"]:
    print(f"  {axis}")
print()

# === Query 2: blocked ===
blocked = payload.query.blocked()
print(f"=== Blockers ({blocked.metadata['total_blockers']}) ===")
for b in blocked.blockers:
    print(f"  {b.node['content']} — reason: {b.blocked_state['reason']}, impact: {b.impact_score}")
print()

# === Query 3: why ===
# Pick a node that has ancestors
if ir.nodes:
    target = ir.nodes[-1]  # Last node usually has causal ancestry
    why = payload.query.why(target.id, format="minimal")
    print(f"=== Why does '{target.content}' exist? ===")
    print(f"  Root cause: {why.root_cause}")
    if why.chain:
        print(f"  Chain: {' → '.join(why.chain)}")
    print()

# === Query 4: what_if ===
if ir.nodes:
    source = ir.nodes[0]
    impact = payload.query.what_if(source.id, format="summary")
    print(f"=== What if '{source.content}' changes? ===")
    print(f"  {impact.impact_summary}")
    if impact.key_tradeoff:
        print(f"  Key tradeoff: {impact.key_tradeoff}")
    print()

# === Query 5: alternatives ===
questions = [n for n in ir.nodes if n.type.value == "question"]
if questions:
    q = questions[0]
    alts = payload.query.alternatives(q.id, format="simple")
    print(f"=== Alternatives for '{q.content}' ===")
    print(f"  Options: {', '.join(alts.options_considered)}")
    print(f"  Chosen: {alts.chosen}")
    print(f"  Reason: {alts.reason}")
    print()

# === Payload encoding ===
envelope = payload.encode()
print("=== Mode 3 Envelope ===")
print(f"  LDP version: {envelope['ldp_version']}")
print(f"  Payload mode: {envelope['payload_mode']}")
print(f"  Format: {envelope['payload_format']}")
print(f"  Capabilities: {envelope['capabilities']}")
print()

# === Fallback chain ===
fallback = FallbackChain(ir)

mode1 = fallback.to_mode1()
print("=== Mode 1 (Semantic Frame) ===")
print(f"  Task type: {mode1['task_type']}")
print(f"  Instruction: {mode1['instruction']}")
print(f"  Labels: {mode1['labels']}")
print()

mode0 = fallback.to_mode0()
print("=== Mode 0 (Natural Language) ===")
print(mode0[:500])
print("...")
print()

# === JamJet Adapter ===
adapter = FlowScriptMode3Adapter()
result = adapter.invoke(envelope, query="tensions")
print("=== JamJet Adapter: tensions query ===")
print(f"  Total: {result['result']['metadata']['total_tensions']}")
print(f"  Axes: {result['result']['metadata']['unique_axes']}")
