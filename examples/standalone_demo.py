"""
flowscript-ldp: Standalone demo — no FlowScript CLI required.

Loads pre-compiled IR from JSON and demonstrates all 5 query operations,
payload encoding, and fallback degradation.
"""

import json
from pathlib import Path

from flowscript_ldp import FlowScriptPayload, FallbackChain, FlowScriptMode3Adapter
from flowscript_ldp.ir import NodeType, RelationType

# Load sample IR (pre-compiled from design.fs)
sample_path = Path(__file__).parent / "sample_ir.json"
with open(sample_path) as f:
    ir_data = json.load(f)

payload = FlowScriptPayload.from_dict(ir_data)
ir = payload.ir
print(f"Loaded: {len(ir.nodes)} nodes, {len(ir.relationships)} relationships, {len(ir.states)} states")
print()


# --- Helper: find nodes by criteria ---

def _find_node_by_content(substring: str):
    return next((n for n in ir.nodes if substring in n.content), None)


def _find_node_with_causal_children():
    """Find a node with outgoing 'causes' relationships (good for what_if)."""
    causes_count = {}
    for r in ir.relationships:
        if r.type == RelationType.CAUSES:
            causes_count[r.source] = causes_count.get(r.source, 0) + 1
    if not causes_count:
        return ir.nodes[0] if ir.nodes else None
    best_id = max(causes_count, key=causes_count.get)
    return next((n for n in ir.nodes if n.id == best_id), None)


def _find_node_with_causal_ancestor():
    """Find a node that has incoming 'causes' relationships (good for why)."""
    for r in ir.relationships:
        if r.type == RelationType.CAUSES:
            node = next((n for n in ir.nodes if n.id == r.target), None)
            if node:
                return node
    return ir.nodes[-1] if ir.nodes else None


# === Query 1: tensions ===
tensions = payload.query.tensions()
print(f"=== Tensions ({tensions.metadata['total_tensions']}) ===")
if tensions.tensions_by_axis:
    for axis, details in tensions.tensions_by_axis.items():
        for d in details:
            print(f"  [{axis}] {d.source['content']} vs {d.target['content']}")
print()

# === Query 2: blocked ===
blocked = payload.query.blocked()
print(f"=== Blockers ({blocked.metadata['total_blockers']}) ===")
for b in blocked.blockers:
    print(f"  {b.node['content']}")
    print(f"    reason: {b.blocked_state['reason']}, days: {b.blocked_state['days_blocked']}, impact: {b.impact_score}")
print()

# === Query 3: why ===
target = _find_node_with_causal_ancestor()
if target:
    why = payload.query.why(target.id, format="minimal")
    print(f"=== Why does '{target.content}' exist? ===")
    print(f"  Root cause: {why.root_cause}")
    if why.chain:
        print(f"  Chain: {' → '.join(why.chain)}")
    print()

# === Query 4: what_if ===
source = _find_node_with_causal_children()
if source:
    impact = payload.query.what_if(source.id, format="summary")
    print(f"=== What if '{source.content}' changes? ===")
    print(f"  {impact.impact_summary}")
    if impact.benefits:
        print(f"  Benefits: {', '.join(impact.benefits[:3])}")
    if impact.risks:
        print(f"  Risks: {', '.join(impact.risks[:3])}")
    if impact.key_tradeoff:
        print(f"  Key tradeoff: {impact.key_tradeoff}")
    print()

# === Query 5: alternatives ===
questions = [n for n in ir.nodes if n.type == NodeType.QUESTION]
if questions:
    q = questions[0]
    alts = payload.query.alternatives(q.id, format="simple")
    print(f"=== Alternatives for '{q.content}' ===")
    print(f"  Options: {', '.join(alts.options_considered)}")
    if alts.chosen:
        print(f"  Chosen: {alts.chosen}")
        print(f"  Reason: {alts.reason}")
    else:
        print("  Decision: not yet decided (no alternative has a 'decided' state)")
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
for t in result["result"]["tensions"]:
    print(f"  [{t['axis']}] {t['source']} vs {t['target']}")
