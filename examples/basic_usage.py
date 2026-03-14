"""
flowscript-ldp: Basic usage example.

Demonstrates the thesis in 8 lines — coordination becomes computational
instead of inferential.
"""

from pathlib import Path

from flowscript_ldp import FlowScriptPayload, FallbackChain, ParserBridge

# Parse FlowScript text to IR
bridge = ParserBridge()
ir = bridge.parse_file(Path.home() / "Documents/flowscript/examples/design.fs")

# Create Mode 3 payload
payload = FlowScriptPayload(ir)

# Query the semantic graph computationally
blockers = payload.query.blocked()
tensions = payload.query.tensions()
print(f"Found {blockers.metadata['total_blockers']} blockers")
print(f"Found {tensions.metadata['total_tensions']} tensions across {tensions.metadata['unique_axes']}")

# Run why query on first node
first_node = ir.nodes[0]
why_result = payload.query.why(first_node.id, format="minimal")
print(f"\nWhy does '{first_node.content}' exist?")
print(f"  Root cause: {why_result.root_cause}")

# Encode for LDP transport
envelope = payload.encode()
print(f"\nMode 3 envelope: {envelope['payload_mode']} ({envelope['payload_format']})")
print(f"  Capabilities: {envelope['capabilities']}")

# Graceful degradation
fallback = FallbackChain(ir)
mode1 = fallback.to_mode1()
print(f"\nMode 1 (semantic frame):")
print(f"  Task type: {mode1['task_type']}")
print(f"  Instruction: {mode1['instruction']}")

mode0 = fallback.to_mode0()
print(f"\nMode 0 (natural language): {len(mode0)} chars")
print(mode0[:300] + "...")
